#!/usr/bin/env python3
"""Local visible-answer, sampling, tools+schema and Responses SSE smoke checks."""
import json
import urllib.request
from benchmark import request

BASE = 'http://127.0.0.1:18080'


def main():
    health = request(BASE,'/health')
    assert health['loaded'] and health['images'] and health['max_context'] == 262144
    params = request(BASE,'/props')['default_generation_settings']['params']
    assert params['presence_penalty'] == params['frequency_penalty'] == 0 and params['repeat_penalty'] == 1
    def body(messages, **extra):
        return dict(model='strata',messages=messages,max_tokens=256,temperature=0,top_k=1,top_p=1,
                    min_p=0,seed=42,reasoning_effort='none',**extra)
    response = request(BASE,'/v1/chat/completions',body([{'role':'user','content':'Reply exactly STRATA_022_OK'}]))
    assert response['choices'][0]['message']['content'].strip() == 'STRATA_022_OK'
    tool = {'type':'function','function':{'name':'read_marker','parameters':{'type':'object',
        'properties':{'path':{'type':'string'}},'required':['path'],'additionalProperties':False}}}
    schema = {'type':'json_schema','json_schema':{'name':'marker','strict':True,'schema':{'type':'object',
        'properties':{'marker':{'type':'string'}},'required':['marker'],'additionalProperties':False}}}
    messages = [{'role':'user','content':'Read verify.txt with read_marker, then return its marker as a JSON object.'}]
    response = request(BASE,'/v1/chat/completions',body(messages,tools=[tool],response_format=schema,
        tool_choice={'type':'function','function':{'name':'read_marker'}}))
    choice = response['choices'][0]
    call = choice['message']['tool_calls'][0]
    assert choice['finish_reason'] == 'tool_calls' and call['function']['name'] == 'read_marker'
    assert json.loads(call['function']['arguments']) == {'path':'verify.txt'}
    expected = {'marker':'STRATA_022_SYNTHETIC_8271'}
    messages += [choice['message'],{'role':'tool','tool_call_id':call['id'],'content':json.dumps(expected)}]
    response = request(BASE,'/v1/chat/completions',body(messages,tools=[tool],response_format=schema,tool_choice='auto'))
    assert json.loads(response['choices'][0]['message']['content']) == expected
    req = urllib.request.Request(BASE+'/v1/responses',headers={'Content-Type':'application/json'},data=json.dumps({
        'model':'strata','input':'Reply exactly STRATA_022_SSE_OK','max_output_tokens':64,
        'reasoning':{'effort':'none'},'stream':True}).encode())
    text,completed = [],False
    with urllib.request.urlopen(req,timeout=120) as stream:
        for line in stream:
            if not line.startswith(b'data: ') or line[6:].strip() == b'[DONE]':
                continue
            event = json.loads(line[6:])
            assert event.get('type') not in ('error','response.failed')
            if event.get('type') == 'response.output_text.delta':
                text.append(event['delta'])
            completed |= event.get('type') == 'response.completed'
    assert completed and 'STRATA_022_SSE_OK' in ''.join(text)
    print('Passed: loaded 256K + images flag, sampling, visible answer, tools+schema, visible Responses SSE')
    print('This smoke does not evaluate image content, long retrieval, concurrency or general answer quality.')


if __name__ == '__main__':
    main()
