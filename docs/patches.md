# v0.2.2 补丁说明

完整补丁：[strata-v0.2.2-gfx1100.patch](../patches/strata-v0.2.2-gfx1100.patch)。基线为Strata v0.2.2提交 `011c9e600a93bbc9fd451c563501b5831c32bbca`，与实测采用补丁字节一致，哈希见[manifest](../results/manifest.json)。只有这一版补丁，不附带旧版本适配。

## FP16 select

修改 `src/kernels/cuda/qsa_select.cu` 和 `include/strata/kernels/qsa_select.hpp`，加入gfx1100使用的rocWMMA FP16输入、FP32累加评分路径。保留已有回退，几何/架构/构建条件不满足时拒绝该路径；没有rocWMMA头文件会编译掉该分支，因此构建脚本要求头文件存在，并应实际运行selftest核对。

配置沿用 `STRATA_SELECT_WMMA=1`。若要在本机关闭select WMMA另测，将忽略的本地JSON中该值改成0并重启；这不是纯上游对照，也没有在本次同版本报告里单独测量这种消融。

新增 `src/kernels/qsa_select_wmma_parity.cpp` 及CMake目标 `qsa_select_wmma_parity`。测试用float64参考量化误差界限，用warp算术host模型检查参考路径逐位一致，覆盖ragged、canary、尾部、放大量级和负对照。FP16近似和累加顺序不同，不能宣称与原路径模型输出逐token相同。源码较早测量注释保留原上下文，不用它计算本次端到端收益。

## 客户端tools与最终schema

修改 `serve/server.py` 与 `serve/test_structured.py`。Chat Completions同时携带客户端 `tools` 和 `response_format` 时，工具调用轮次保留原tool deltas、参数、reasoning与finish_reason；工具返回后的最终文本仍按schema验证。服务内部自行执行的 `strata_mcp=true` 循环保持已有拒绝限制。

新测试覆盖普通和streaming工具调用，以及客户端合成工具结果后的最终schema。工具结果来自调用者，不等于服务自行执行文件读取或其他业务动作。

## 应用、回归和撤销

按[运行说明](runbook.md)在新的同提交checkout执行 `scripts/apply-patch.sh`。先做 `git apply --check`；不在有未保存修改的生产目录强制应用，不重复应用。

原硬件上同版Python回归clean62+37、patched64+37通过；两卡FP16 selftest、exact scorer及prompt-attention通过，详见[报告](report-v0.2.2.md)。只验证了HIP/gfx1100；未构建或验收本补丁的CUDA/SYCL版本，本包也不宣称支持这些路径。

需要干净上游时使用新的同提交checkout并重新构建。已有本地修改或后续版本变更时，不自动执行 `git reset --hard` 或反向应用补丁。
