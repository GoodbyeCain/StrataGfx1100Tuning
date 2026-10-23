# v0.2.2 完整运行说明

以下命令在Linux Bash执行。只使用固定的v0.2.2源码和同版Python server。不要将补丁应用到当前生产目录，也不要用下载的纯上游二进制冒充已编译的补丁引擎。

## 1. 前置条件与GPU顺序

- 7900 XTX 24GB；双卡加7900 XT 20GB，均gfx1100。实测CPU为9700X、物理64GB RAM（系统可见约59GiB）。模型和PLE表需要SSD；下载、转换、源码和依赖建议预留约200GB空间。
- 工作正常的amdgpu、HIP编译器、hipBLAS、hipBLASLt及rocWMMA开发头文件。实测HIP版本7.16.26385、Lt版本100401；SDK目录的名称不等于已确认的发行包版本。这里不提供驱动升级或网络配置脚本。
- C++20编译器、Git、Python3.10+及venv。构建依赖以固定源码的requirements文件为准。实测host编译器GCC15.2、HIP Clang24；换工具链后的数值与性能需重新验证。
- 运行前停止其他模型服务，确认GPU没有待执行任务。这里不通过宽泛pkill或脚本自动停止外部进程。

用ROCm设备列表以及之后编译出的 `strata-device --list-devices` 核对HIP序号。**不要把Linux的card0、card1直接当作HIP0、HIP1**，有核显时尤其容易混淆。实测HIP0=XTX、HIP1=XT；在自己的机器上通过 `configure.py --xtx-gpu N --xt-gpu M` 指定。

## 2. 获取固定源码并应用补丁

选择新的工作目录，例如 `$HOME/strata-lab`；下面变量在同一终端后续使用。

```bash
mkdir -p "$HOME/strata-lab"
cd "$HOME/strata-lab"
git clone https://github.com/GoodbyeCain/StrataGfx1100Tuning.git
export TUNING_ROOT="$PWD/StrataGfx1100Tuning"
git clone --branch v0.2.2 --depth 1 https://github.com/Niko1221/Strata.git Strata-v0.2.2
export STRATA_ROOT="$PWD/Strata-v0.2.2"
test "$(git -C "$STRATA_ROOT" rev-parse HEAD)" = 011c9e600a93bbc9fd451c563501b5831c32bbca
bash "$TUNING_ROOT/scripts/apply-patch.sh" "$STRATA_ROOT"

# 单独获取上游固定的llama.cpp依赖，不使用最新main。
git init llama.cpp
git -C llama.cpp remote add origin https://github.com/ggml-org/llama.cpp.git
git -C llama.cpp fetch --depth 1 origin 3cf03257f219afbe7334045ff7c6a06ac68c627d
git -C llama.cpp checkout --detach FETCH_HEAD
export LLAMA_ROOT="$PWD/llama.cpp"
```

补丁脚本拒绝非指定提交或有改动的源码目录。它只应用本仓库的补丁，不下载模型、启停服务或更改旧安装。

## 3. Python、HIP引擎与CPU视觉

```bash
cd "$STRATA_ROOT"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-build.txt
.venv/bin/python -m pip install jsonschema==4.26.0
export PATH="$STRATA_ROOT/.venv/bin:$PATH"
export ROCM_ROOT=/path/to/rocm
test -f "$ROCM_ROOT/include/rocwmma/rocwmma.hpp"
bash "$TUNING_ROOT/scripts/build-hip.sh" "$STRATA_ROOT" "$LLAMA_ROOT" "$ROCM_ROOT"
export LD_LIBRARY_PATH="$ROCM_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
"$STRATA_ROOT/build-gfx1100/strata" --version
"$STRATA_ROOT/build-gfx1100/strata-device" --list-devices
```

`ROCM_ROOT`必须换成真实SDK目录。脚本使用同一SDK的编译器、bitcode和库；当前入口要求bitcode位于SDK的 `lib/llvm/amdgcn/bitcode`。其他发行布局需按[上游AMD说明](https://github.com/Niko1221/Strata/blob/v0.2.2/docs/AMD_HIP.md#build)调整编译参数，不能因此声称复现了同一工具链。

两个构建目录必须是新目录。CPU视觉使用native CPU指令集，不应直接把编译产物分发给指令集不同的CPU。完整编译在原实测机器已通过；本次公开包装的构建脚本没有再次执行整套GPU编译，见[验证记录](publication-validation.md)。

## 4. 下载并准备模型

模型来源：[ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF)。以下锁定v0.2.2 setup使用的模型仓库revision；不会下载整个BF16主模型。大文件下载与MTP准备可能耗时较长。

```bash
export DATA_ROOT="$HOME/strata-data"
mkdir -p "$DATA_ROOT/models/IQ3_S" "$DATA_ROOT/mtp"
export MODEL_URL=https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF/resolve/ed59f92082b1e93c0e96d60a8b11aab089b52f09
for shard in 00001 00002; do
  filename="Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-${shard}-of-00002.gguf"
  curl -fL --retry 3 -C - "$MODEL_URL/IQ3_S/$filename" -o "$DATA_ROOT/models/IQ3_S/$filename"
done
curl -fL --retry 3 -C - "$MODEL_URL/mmproj-Qwen3.8-Flash-Next-BF16.gguf" \
  -o "$DATA_ROOT/models/mmproj-Qwen3.8-Flash-Next-BF16.gguf"

# 下面三条SHA256来自固定上游setup.py；不是本次重新hash了全部模型。
cd "$DATA_ROOT/models"
sha256sum -c "$TUNING_ROOT/configs/model-files.sha256"

cd "$STRATA_ROOT"
export STRATA_GGUF_PY="$LLAMA_ROOT/gguf-py"
.venv/bin/python tools/iq_pack.py \
  --gguf "$DATA_ROOT/models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf" \
  --out "$DATA_ROOT/packs/iq3_s"
.venv/bin/python tools/mtp_fetch.py fetch --out "$DATA_ROOT/mtp"
.venv/bin/python tools/mtp_fetch.py verify --out "$DATA_ROOT/mtp"
.venv/bin/python tools/mtp_pack.py --src "$DATA_ROOT/mtp" --experts q2_0 --out "$DATA_ROOT/mtp/mtp-q2_0.gguf"
.venv/bin/python tools/mtp_rt.py --gguf "$DATA_ROOT/mtp/mtp-q2_0.gguf" --out "$DATA_ROOT/mtp/rt"
cp "$STRATA_ROOT/data/draft_vocab.bin" "$DATA_ROOT/mtp/rt/draft_vocab.bin"
```

两份IQ3_S分片必须在同一目录，保持原文件名。pack使用该模型自己的tokenizer与dense数据，不借用其他量化的pack。默认直接从GGUF加载专家；`experts.bin`不是必要前置文件。MTP fetch只取固定checkpoint的所需tensor范围，遇到Range校验或hash失败应先修正下载，不能跳过校验。

预期目录：

```text
strata-data/
  models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00001-of-00002.gguf
  models/IQ3_S/Qwen3.8-Flash-Next-GSQ-RCO-IQ3_S-00002-of-00002.gguf
  models/mmproj-Qwen3.8-Flash-Next-BF16.gguf
  packs/iq3_s/{index.txt,dense.bin,native_experts.txt,tokenizer/}
  mtp/rt/{experts.bin,dense.bin,dense.txt,draft_vocab.bin}
```

## 5. 生成两份本地JSON

```bash
cd "$TUNING_ROOT"
python3 scripts/configure.py --strata-root "$STRATA_ROOT" --data-root "$DATA_ROOT" \
  --rocm-root "$ROCM_ROOT" --xtx-gpu 0 --xt-gpu 1
```

生成 `runtime/strata-single-xtx.local.json` 和 `runtime/strata-dual.local.json`，目录/文件默认权限700/600；它们被Git忽略。已有同名文件时脚本拒绝覆盖，改用新的 `--out-dir`。

| 参数 | 单卡 | 双卡 |
| --- | --- | --- |
| GPU | 仅指定XTX | 指定XTX、XT，顺序保持 |
| layer_split | 无 | 28：前28层在XTX，余下20层在XT |
| pipeline-windows | 参数保留2，引擎因单卡自动关闭 | 2，具体请求是否使用还受请求条件影响 |
| 上下文 / KV / resident | 262144 / int8 / 32768 | 相同 |
| prefill / MTP | 16384 / spec4、min-p0.5 | 相同 |
| sampling默认 | presence0 / frequency0 / repetition1 | 相同 |
| CPU视觉 | 8线程、300视觉tokens，args含--vision | 相同 |

`STRATA_HIP_WMMA=1`、`STRATA_SELECT_WMMA=1`、`STRATA_RESIDENT_PIN=0`、`STRATA_STAGE_PIN=0`沿用实测。`STRATA_HIPBLASLT_VERBOSE=1`保留诊断日志。

Lt表只适用于gfx1100和hipBLASLt **100401**。检查启动日志的 `hipBLASLt tuning enabled (43 rows, gfx1100, version 100401)`。若本机Lt版本不同，移除本地JSON的 `STRATA_HIPBLASLT_TUNING` 并另测，或针对本机重新校准；不要改表头强制复用solution IDs。

## 6. 启动、请求、停止

先停止自己现有的推理实例并确认GPU空闲。此运行包不会替你控制已有systemd服务。两份配置共用同一端口、同一组资源，只能运行其一。

```bash
cd "$TUNING_ROOT"
bash scripts/run.sh runtime/strata-single-xtx.local.json
# 或：bash scripts/run.sh runtime/strata-dual.local.json
```

在另一个终端检查加载状态，然后发请求：

```bash
curl -fsS http://127.0.0.1:18080/health
curl -fsS http://127.0.0.1:18080/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"qwen3.8-flash-next-iq3_s","messages":[{"role":"user","content":"请用一句话介绍你自己"}],"max_tokens":128,"temperature":0,"reasoning_effort":"none"}'
python3 scripts/smoke.py
```

健康接口应为loaded=true、max_context=262144、images=true。`smoke.py`验证默认采样、实际可见文本、客户端工具轮次与最终schema、Responses SSE可见文本及completed；工具结果是客户端合成值，不实际读业务文件。images=true只表示配置能力，不能代替识图测试。

前台终端按Ctrl+C停止，确认Python server及其引擎退出、显存释放和端口关闭后，再换另一份配置。若原来暂停了其他服务，按其原管理方式恢复。发生OOM、GPU reset或服务故障时保留本地日志并停止该组，不重复启动同一失败配置或提高watchdog掩盖问题。

## 7. 数值与Python回归

测试时也要保持GPU空闲：

```bash
export LD_LIBRARY_PATH="$ROCM_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
cd "$STRATA_ROOT"
.venv/bin/python -m unittest serve.test_structured serve.test_responses serve.test_effort

# 逐卡执行；把0/1改为已核对的HIP序号。
for gpu in 0 1; do
  HIP_VISIBLE_DEVICES="$gpu" STRATA_SCORES_THREAD=1 STRATA_SCORES_THREAD_TRACE=1 \
    build-gfx1100/qsa_scores_gfx1100_parity --full
  HIP_VISIBLE_DEVICES="$gpu" build-gfx1100/qsa_select_wmma_parity --selftest
  HIP_VISIBLE_DEVICES="$gpu" build-gfx1100/hip_prompt_attn_wmma 32768 2048 3
done
```

只有一张卡时只测该卡。这里列的是相关测试，不是上游全部ctest；部分上游测试需要独立fixture，不能以未注册/未运行当作通过。

## 8. 重跑吞吐对照

每一组开始前重启所测配置。两轮推荐顺序：dual trial0 → single-xtx trial0 → single-xtx trial1 → dual trial1。每次启动加载完成后，在另一个终端执行相应命令，例如：

```bash
cd "$TUNING_ROOT"
python3 scripts/benchmark.py --arm dual --trial 0 --out runtime/dual-0.jsonl
# 停止、换单卡并加载完成后：
python3 scripts/benchmark.py --arm single-xtx --trial 0 --out runtime/single-0.jsonl
# 重启单卡、加载完成后：
python3 scripts/benchmark.py --arm single-xtx --trial 1 --out runtime/single-1.jsonl
# 停止、换双卡并加载完成后：
python3 scripts/benchmark.py --arm dual --trial 1 --out runtime/dual-1.jsonl

python3 scripts/compare.py runtime/dual-0.jsonl runtime/single-0.jsonl \
  runtime/single-1.jsonl runtime/dual-1.jsonl --baseline dual --candidate single-xtx
```

每次4条计时，完成两轮共16条。脚本检查fresh无缓存、输出达到256/1024tokens，比较器核对提示词hash、实际输入/输出和缓存量。提示词按长度/轮次在首部区分；缓存续聊使用固定合成历史，不带入不同配置各自生成的答案。失败结果留下 `.partial`，不输出完整文件，不计入吞吐对照。

计时脚本不负责重启、恢复生产或收集系统资源，不会自动证明GPU编号正确。应另行保存进程HIP_VISIBLE_DEVICES、引擎启动日志、RAM/swap/各卡显存、Lt实际模型回退和内核故障。公开历史资源表来自当时0.5秒采样，不能与新测量混为同一轮。近满容量的标记检索也应单独执行，不能仅凭吞吐输入长度宣称理解能力通过。

纯上游/补丁对照使用两个独立同提交checkout，各自运行自己的 `serve/server.py` 和引擎，保持共同配置。仅替换exe而继续用补丁server不构成纯上游对照。复核仓库自带历史数值无需GPU：

```bash
python3 scripts/compare.py results/2026-10-22-v022/measurements.jsonl --baseline clean --candidate patched
python3 scripts/compare.py results/2026-10-23-single-dual/measurements.jsonl --baseline dual --candidate single-xtx
```

## 9. 回退

本流程使用独立checkout、独立build及忽略的runtime配置，未改旧安装。停止新实例，再按旧安装自身方式启动即可回退。需要重新构建纯上游时，新建相同提交的干净checkout；不要对后续已修改源码执行强制reset或盲目反向应用补丁。
