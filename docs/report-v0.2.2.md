# Strata v0.2.2 gfx1100 实测报告

本公开版只保留v0.2.2的纯上游/补丁对照与单卡/双卡对照。2026-10-22与10月23日分别统计，不跨日期拼接计时。原始运维报告中的个人路径、网络、服务标识、配置备份与旧版本材料未纳入。

## 环境与配置

Ryzen7 9700X、约59GiB可见RAM、RX7900 XTX 24GB + RX7900 XT 20GB（gfx1100）、SSD。Ubuntu Linux，kernel7.0.0-38-generic，amdgpu7.1.9.31600000，HIP7.16.26385，hipBLASLt100401。具体源码、二进制、补丁、Lt表哈希见[manifest](../results/manifest.json)。SDK目录名不能替代发行包版本，未确认某个ROCm发行包修订号。

固定上游提交011c9e600a93bbc9fd451c563501b5831c32bbca（v0.2.2，engine0.1.47），llama.cpp依赖3cf03257f219afbe7334045ff7c6a06ac68c627d。引擎HIP Release只编译gfx1100；两项修改为FP16 select及客户端工具轮次与最终schema兼容。单卡/双卡均为相同补丁引擎与server。

模型为Qwen3.8-Flash-Next GSQ-RCO IQ3_S；容量262144，prefill16384，int8 KV，KV resident32768，resident专家缓存auto，spec4/min-p0.5，CPU视觉8线程/300tokens。默认presence0/frequency0/repetition1。双卡按XTX→XT顺序，layer_split28；单卡只暴露XTX并移除split。pipeline-windows2参数保留，单卡引擎自动关闭，双卡受请求条件控制。因检测到核显，引擎nice为5，未另作覆盖。

## 方法

每组独立重启、短暖机，三档fresh为8192/131072/260000目标输入，每条规定输出256tokens；128K后接固定合成历史续聊，规定输出1024tokens，不把各配置生成结果带入历史。temperature0、top_k1、top_p1、min_p0、seed42、reasoning none，惩罚参数继承共同默认。

提示词首部按轮次/长度变化，所有fresh要求cache_n=0；配对检查提示词SHA256、实际输入/输出tokens、缓存量与finish_reason。四场景分别取两轮中位数，不做混合总分。请求墙钟与引擎PP/TG分别统计；加载、提示词准备和独立功能验收不计入吞吐请求。零KV复用不代表冷文件缓存。

PP=prompt_per_second，TG/TT=predicted_per_second，单位tok/s。cached PP只覆盖新增67/128tokens。实际fresh输入为8215/8216、131081、259994/259995；cached输入131141/131202、缓存131074。256token短生成不能代表长生成收益或完整代码任务质量。

## 10月22日：同版本纯上游与补丁

原三组实验中只导出v0.2.2的clean/patched两组，16条计时全部有效，未剔除失败。原实验顺序中两组为clean→patched及patched→clean，每组使用自己的同版server与引擎。此表不包含旧版本数据。

| 场景 | clean PP | patched PP | clean TG/TT | patched TG/TT | clean秒 | patched秒 | 补丁减少耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8K fresh | 1409.15 | 1409.35 | 88.05 | 90.85 | 8.745 | 8.653 | +1.06% |
| 128K fresh | 2926.50 | 2958.45 | 86.65 | 83.45 | 47.789 | 47.422 | +0.77% |
| 近256K fresh | 2974.15 | 3076.00 | 84.10 | 84.55 | 90.546 | 87.641 | +3.21% |
| 128K cached | 164.00 | 165.40 | 99.10 | 100.40 | 11.060 | 10.923 | +1.23% |

两项补丁组合在本次长输入有收益，也保留客户端tools+schema行为；没有单独消融两项修改，不能把全部差异归因于FP16 select。补丁源码中的较早阶段速度注释不等于本次端到端提速数据。

| 10月22日资源 | clean | patched |
| --- | ---: | ---: |
| 最低可用RAM（GiB） | 19.06 | 19.05 |
| XTX峰值VRAM（GiB） | 23.929 | 23.947 |
| XT峰值VRAM（GiB） | 19.679 | 19.708 |
| swap使用/新增swap-out | 0 / 0 | 0 / 0 |

模型Lt上下文没有回退；各次启动另有临时暖机上下文的f16/bf16 T64/N64/K320/ldy64回退，见按上下文保留的[资源与Lt汇总](../results/2026-10-22-v022/resources.json)。不将暖机回退隐藏或混作实际模型回退。

## 10月23日：单XTX与XTX+XT

16/16条计时有效，四组无错误。两轮顺序dual→single、single→dual，源码、补丁、模型与提示词完全相同。单卡未另做缓存或Lt参数寻优。

| 场景 | 单卡PP | 双卡PP | 单卡TG/TT | 双卡TG/TT | 单卡秒 | 双卡秒 | 单卡多耗时 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8K fresh | 1528.45 | 1410.40 | 73.05 | 90.80 | 8.888 | 8.650 | +2.76% |
| 128K fresh | 2127.75 | 2983.75 | 73.65 | 81.65 | 65.132 | 47.113 | +38.25% |
| 近256K fresh | 2069.80 | 3073.20 | 67.95 | 85.00 | 129.468 | 87.699 | +47.63% |
| 128K cached | 119.90 | 167.20 | 78.90 | 98.20 | 13.836 | 11.149 | +24.10% |

单卡8K PP高8.37%，但生成低19.55%，请求总耗时多2.76%；128K和近256K PP分别低28.69%和32.65%。近256K单卡两轮129.366/129.569秒，双卡87.470/87.927秒。缓存续聊的单卡生成低19.65%，总耗时多24.10%。在本次工作负载下，继续使用双卡更合适。

| 10月23日资源 | 双卡 | 单XTX |
| --- | ---: | ---: |
| 最低可用RAM（GiB） | 19.01 | 12.43 |
| XTX峰值VRAM（GiB） | 23.922 | 23.971 |
| XT峰值VRAM（GiB） | 19.698 | 0.025 |
| swap使用/新增swap-out | 0 / 0 | 0 / 0 |

当时核对实际引擎子进程的HIP_VISIBLE_DEVICES以及逐卡显存，两轮单卡只见XTX，XT维持约0.025GiB。个人机器的具体PCI地址与进程ID不公开。单卡日志提示显存余量约500MiB，本次未改变reserve或降低上下文；未观察到OOM、swap或GPU reset/fault/timeout，不保证长期高负载稳定性。

相同43行gfx1100/version100401 Lt表。双卡模型上下文两轮2,212,732次launches，回退0。单卡模型上下文首轮20次、第二轮30次回退，均为FP16 N2560/K2560/ldy2560、不同T尺寸；第二轮汇总还包括独立长检索与续聊，次数不是等量负载的回退率。启动临时暖机另有双卡共8次、单卡共4次回退。单卡仍有独立Lt调优空间，没有测量其潜在收益，也不把差异全部归因于回退。

## 功能与数值验收

| 验收 | 10月22日结果 |
| --- | --- |
| structured/responses/effort Python回归 | clean62/62，patched64/64 |
| 新版相关Python回归 | clean37/37，patched37/37；与前批不重复计数 |
| 两卡exact scorer --full | 2/2通过，各35个case，scores与ids逐位一致 |
| 两卡FP16 select --selftest | 2/2通过，含界限、canary与负对照 |
| 两卡clean/patched prompt-attention | 4/4通过，FAILURES=0 |
| patched六个可执行Python任务 | 6/6通过 |
| 客户端工具名/参数和工具结果后最终schema | 通过 |
| CPU视觉 | 正确读出合成图片中的文字、红方块和蓝圆 |
| 原生Responses SSE | 有可见文本与completed |

六个代码任务为末次去重、clamp、连续游程计数、计数字典合并、括号平衡和最左二分位置；在AST限制、CPU/内存受限子进程中检查多个边界输入与不修改输入。它们不是完整HumanEval/MBPP，也不代表跨文件工程任务。

10月22日补丁双卡正式验收：实际261036-token三标记检索全对，cache_n=0，85.867秒；续聊复用261086tokens，0.404秒。候选本机接口也通过同类验收，两者不混入吞吐表。

10月23日单卡：实际261034-token输入、50token输出，首/中/尾标记全对，cache_n=0，126.638秒；续聊复用261085tokens，中部标记正确，0.437秒。本次没有重跑单卡完整代码、工具、视觉和SSE验收；images=true只确认能力标志。

对照结束后已恢复原双卡运行状态，实际回答通过、测试端口释放；源码、tracked diff、引擎和原配置未变。可读内核日志没有匹配到GPU reset/fault/timeout或OOM。公开版只保留结论字段，排除网络接入与个人服务信息。

## 数据与复核边界

- [10月22日逐请求计时](../results/2026-10-22-v022/measurements.jsonl)、[比较](../results/2026-10-22-v022/comparison.json)、[验收](../results/2026-10-22-v022/acceptance.json)。
- [10月23日逐请求计时](../results/2026-10-23-single-dual/measurements.jsonl)、[比较](../results/2026-10-23-single-dual/comparison.json)、[资源](../results/2026-10-23-single-dual/resources.json)、[验收](../results/2026-10-23-single-dual/acceptance.json)。
- [合成提示词](../tests/prompts/)保留原字节，可据hash复核。发布的逐请求数值与原测量一致，移除生成文本预览，不公开原始系统/服务日志、认证、私人路径和部署快照。
- [运行说明](runbook.md)与新包装脚本的检查见[发布验证记录](publication-validation.md)。原实测完成不等于新读者的驱动、编译器、依赖和完整部署已验证。

未验证长时间并发、完整代码基准、长生成质量、任意长文档理解或其他GPU/OS/工具链。数值测试通过不等于跨路径输出逐token相同；单卡未调优。所有速度结论只针对上述单请求负载。
