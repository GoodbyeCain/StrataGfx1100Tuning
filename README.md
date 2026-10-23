# Strata gfx1100：v0.2.2 单卡 / 双卡实测与运行包

在 Linux 上用 **RX 7900 XTX 24 GB**，或 **7900 XTX + 7900 XT 20 GB**，运行 Qwen3.8-Flash-Next GSQ-RCO IQ3_S。本仓库提供已实测版本的补丁、两份启动配置模板、构建与运行步骤，以及脱敏后的性能数据。

**仅覆盖 Strata v0.2.2，engine 0.1.47**，上游提交固定为 [`011c9e6`](https://github.com/Niko1221/Strata/tree/011c9e600a93bbc9fd451c563501b5831c32bbca)。采用 FP16 select 和 Chat tools+schema 两项本地修改，不跟随 `main` 或 `latest` 自动升级。本仓库是社区运行记录，不是上游发行版；不包含模型、ROCm或编译好的引擎。

## 实测结果

2026-10-23，Ryzen 7 9700X、约59 GiB可见RAM、相同v0.2.2补丁版，两轮反向顺序对照。PP是输入读取吞吐，TG/TT是生成吞吐，单位tok/s。fresh输出256tokens，cached输出1024tokens；每项取两轮中位数。

| 场景 | 单XTX PP | 双卡PP | 单XTX TG/TT | 双卡TG/TT | 单XTX秒 | 双卡秒 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 8K fresh | 1528.45 | 1410.40 | 73.05 | 90.80 | 8.888 | 8.650 |
| 128K fresh | 2127.75 | 2983.75 | 73.65 | 81.65 | 65.132 | 47.113 |
| 近256K fresh | 2069.80 | 3073.20 | 67.95 | 85.00 | 129.468 | 87.699 |
| 128K cached | 119.90 | 167.20 | 78.90 | 98.20 | 13.836 | 11.149 |

单卡实际261034-token首/中/尾检索及缓存续聊通过。双卡长输入与续聊更快，因此实测环境继续采用双卡。单卡未独立调优，存在额外Lt形状回退、显存余量较小；本结果不代表所有7900配置的最优值。

完整方法、同版本补丁对照、资源与局限见[测试报告](docs/report-v0.2.2.md)。[原始数值](results/)可用[配对分析器](scripts/compare.py)复核；不含原始服务日志、私人聊天或个人部署配置。

## 文件入口

| 路径 | 内容 |
| --- | --- |
| [configs/strata-single-xtx.json](configs/strata-single-xtx.json) | 单XTX配置模板，GPU序号可在生成时指定 |
| [configs/strata-dual.json](configs/strata-dual.json) | XTX+XT配置模板，layer_split28 |
| [patches/strata-v0.2.2-gfx1100.patch](patches/strata-v0.2.2-gfx1100.patch) | 两项修改的完整合并补丁，包含新增parity测试源码 |
| [docs/runbook.md](docs/runbook.md) | 从固定源码、模型准备到运行、验收、停止和复测 |
| [docs/patches.md](docs/patches.md) | 补丁范围、开关、数值边界与回归命令 |
| [scripts/](scripts/) | 应用补丁、构建、配置生成、前台启动及测试工具 |
| [tuning/gfx1100-hipblaslt-100401.txt](tuning/gfx1100-hipblaslt-100401.txt) | 实测43行Lt表，只适用于gfx1100 / hipBLASLt100401 |
| [results/manifest.json](results/manifest.json) | 上游提交、依赖、工具链和实测二进制/补丁/表哈希 |
| [docs/privacy.md](docs/privacy.md) | 公开材料范围、脱敏与本地生成文件 |

## 快速启动：已有同版引擎和模型

需要已经准备好的HIP引擎、CPU视觉引擎、IQ3_S两分片、pack、MTP和mmproj。从零开始请先读[完整运行步骤](docs/runbook.md)。配置中的 `@...@` 是占位符，必须先生成本地JSON，Strata不会展开它们。

在Linux终端执行，先将路径换成自己的实际路径：

```bash
git clone https://github.com/GoodbyeCain/StrataGfx1100Tuning.git
cd StrataGfx1100Tuning

python3 scripts/configure.py \
  --strata-root /path/to/Strata-v0.2.2 \
  --data-root /path/to/strata-data \
  --rocm-root /path/to/rocm \
  --xtx-gpu 0 --xt-gpu 1

# 确认其他模型实例已停止，下面两种选择其一：
bash scripts/run.sh runtime/strata-single-xtx.local.json
# 或：bash scripts/run.sh runtime/strata-dual.local.json
```

默认使用源码下 `build-gfx1100/strata` 和 `build-vision/bin/strata-vision`；其他位置通过 `--engine` / `--vision-engine` 指定。两份本地配置均为262144容量、int8 KV、16384 prefill、32768 KV resident、MTP spec4、CPU视觉和代码快模式。

接口为 `http://127.0.0.1:18080/v1`，模型名 `qwen3.8-flash-next-iq3_s`；默认无API密钥，只监听本机。按Ctrl+C停止。脚本不修改systemd、不停止其他服务、不设置开机启动。启用远程访问时需要自行在忽略的本地配置中设置认证和监听范围；不要将凭据提交到Git。

## 使用范围

实测为Linux、gfx1100、指定模型与工具链的单请求负载。未验证Windows、其他GPU、不同Lt版本、长时间并发或完整代码评测。256K标记检索是有限功能检查，不等于任意长文档都能正确理解。公开脚本是本次整理的可迁移入口；其本地检查与原硬件实测分开记录，不把新包装脚本写成已在另一台机器完整部署通过。

引擎和GGUF准备方式来自[上游Strata](https://github.com/Niko1221/Strata/tree/v0.2.2)；模型由Qwen与ISTA-DASLab提供。补丁及随附Lt表保留上游MIT许可，见[LICENSE](LICENSE)与[来源说明](NOTICE.md)。模型权重及依赖遵守各自许可。
