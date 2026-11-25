# 文件索引

本分支（`main`，对应 macOS `1.1.2`）共包含 **31 个文件**，按目录分组如下。1.1.0 旧版完整文件保留在 Git Tag `macos_1.1.0`。

| 目录 | 文件数 | 用途 |
| :--- | ---: | :--- |
| [根目录](#根目录) | 9 | 入口文档、Agent 指南与 Prompt、CDN 直链与 LuLu 规则、环境与依赖 |
| [scripts/](#scripts) | 2 | 本机版本/二进制盘点与仓库一致性/隐私门禁脚本 |
| [model-analysis/](#model-analysis) | 9 | FLUTE v2/v3 验证与解包脚本、根种子、校验报告 |
| [model-config/](#model-config) | 3 | 专业版 / 通用版配置与 fbank 参数 |
| [diagrams/](#diagrams) | 3 | 架构图与 Graphviz 源码 |
| [comparison/](#comparison) | 5 | 公开模型对比、静态标记与来源链接 |

## 根目录

| 文件 | 职责 |
| :--- | :--- |
| [.gitignore](.gitignore) | 忽略本机解包数据、模型权重文件、LuLu 备份与缓存 |
| [AGENTS.md](AGENTS.md) | AI Agent 版本更新流程、核验门禁与分工规范 |
| [FILE_INDEX.md](FILE_INDEX.md) | 仓库文件职责清单 |
| [OFFLINE_MODEL_DOWNLOAD.md](OFFLINE_MODEL_DOWNLOAD.md) | 离线模型官方 CDN 直链、调度协议与 LuLu 防火墙规则 |
| [PRIVACY.md](PRIVACY.md) | 收录范围、隐私脱敏与合规/反滥用原则 |
| [README.md](README.md) | 仓库入口、核心结论与复现命令 |
| [UPDATE_PROMPT.md](UPDATE_PROMPT.md) | 面向新版发布的一键复制 AI Agent 更新 Prompt |
| [environment.json](environment.json) | 应用指纹、模型元数据与分析环境 |
| [requirements.txt](requirements.txt) | 验证与解包脚本的 Python 依赖 |

## scripts/

| 文件 | 职责 |
| :--- | :--- |
| [scripts/inspect_installation.py](scripts/inspect_installation.py) | 只读盘点本机应用与模型指纹、全包开放式扫描，按需刷新元数据 JSON |
| [scripts/validate_repo.py](scripts/validate_repo.py) | 校验 JSON、文件索引、链接、隐私脱敏、跨文件版本一致性与本地模型 |

## model-analysis/

| 文件 | 职责 |
| :--- | :--- |
| [model-analysis/CONTAINER_AND_DECRYPTION.md](model-analysis/CONTAINER_AND_DECRYPTION.md) | FLUTE v2/v3 容器结构、密钥派生算法、XOR 还原与内部文件清单 |
| [model-analysis/verify_container.py](model-analysis/verify_container.py) | 验证 FLUTE v2/v3 容器头、派生密钥并校验目录表结构 |
| [model-analysis/extract_model.py](model-analysis/extract_model.py) | 4 MiB 流式解包或 `--verify-only` 逐文件校验 |
| [model-analysis/flute-v3-seed.bin](model-analysis/flute-v3-seed.bin) | FLUTE v3 密钥派生所需的 32 字节固定根种子 |
| [model-analysis/container-verify-pro.json](model-analysis/container-verify-pro.json) | 专业版目录解密与结构验证报告 |
| [model-analysis/container-verify-general.json](model-analysis/container-verify-general.json) | 通用版明文目录验证报告 |
| [model-analysis/extraction-report-pro.json](model-analysis/extraction-report-pro.json) | 专业版 6 个内部文件的大小、MD5 与 SHA-256 |
| [model-analysis/extraction-report-general.json](model-analysis/extraction-report-general.json) | 通用版 6 个内部文件的大小、MD5 与 SHA-256 |
| [model-analysis/key-derivation-vectors.json](model-analysis/key-derivation-vectors.json) | 真实及合成元数据案例的密钥派生测试向量与验证记录 |

## model-config/

| 文件 | 职责 |
| :--- | :--- |
| [model-config/pro-config.yaml](model-config/pro-config.yaml) | 专业版完整配置（管道、VAD、Prompt 模板、Metal 调度） |
| [model-config/general-config.yaml](model-config/general-config.yaml) | 通用版完整配置（共享权重、880 维特征复用、跨平台调度） |
| [model-config/asr/feature_extractor/fbank.conf](model-config/asr/feature_extractor/fbank.conf) | 16 kHz / 80 维 ASR fbank 特征参数（专业版与通用版共用） |

## diagrams/

| 文件 | 职责 |
| :--- | :--- |
| [diagrams/README.md](diagrams/README.md) | 架构图图例与重新渲染命令 |
| [diagrams/doubao-asr-architecture.dot](diagrams/doubao-asr-architecture.dot) | 架构图 Graphviz 源码 |
| [diagrams/doubao-asr-architecture.png](diagrams/doubao-asr-architecture.png) | 已渲染架构图 |

## comparison/

| 文件 | 职责 |
| :--- | :--- |
| [comparison/ARCHITECTURE_COMPARISON.md](comparison/ARCHITECTURE_COMPARISON.md) | 双模型架构差异，及与 Seed-ASR / LiteASR / 实时语音模型的对比 |
| [comparison/packed-mnn-layers.json](comparison/packed-mnn-layers.json) | 专业版与通用版 `.packed` 内嵌 `.mnn` 子模型与层索引扫描记录 |
| [comparison/public-references.json](comparison/public-references.json) | 公开 `lite-whisper-large-v3-turbo` 配置摘录与论文元数据 |
| [comparison/runtime-markers.json](comparison/runtime-markers.json) | 主程序静态算子、MNN 与 AcLLM 相关标记 |
| [comparison/sources.json](comparison/sources.json) | LiteASR 固定提交与官方资料链接 |
