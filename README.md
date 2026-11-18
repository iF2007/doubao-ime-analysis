> [!NOTE]
> 仅供学习分析使用。

# 豆包输入法离线语音模型分析

## 核心结论

分析对象涵盖豆包输入法 **1.1.0** 与 **1.1.1**，重点分析 1.1.1 架构升级后的双离线模型：**专业版（`acllm_pro_model_mac` 1.5，约 1.48 GB）** 与 **通用版（`acllm_general_model_mac` 1.8，约 463 MB）**，同时向下兼容 1.1.0 历史主模型（`acllm_main_model_mac` 1.8，约 825 MB）。最重要的分析结果如下：

- **1.1.1 双模型架构与打包演进**：
  * 由原先单一大模型拆分为 **专业版**（高精度独立权重，非流式计算调度 Metal GPU 加速）与 **通用版**（流式/非流式共享权重，体积精简适合低显存环境）。
  * 摒弃了 1.1.0 的 20 个解离 `.pthlite` 权重文件布局，升级重构为 **6 个内部聚合文件**（包含核心的 `stream.packed` 与 `nonstream.packed` 引擎图）。
  * 两款新模型内置的 VAD 语音静音切分权重（`vad_v4.pth.pthlite`）实现 **跨模型 100% 逐字节完全一致（SHA-256 完全相同）**。
- **FLUTE v2 / v3 容器机制与密钥派生**：
  * **FLUTE v3（专业版 1.5 / 旧版 1.8）**：目录密钥由固定种子、包内 12 字节 Nonce 和 Header Size 确定性派生，目录使用 ChaCha20 加密（Counter 1 偏移 64 字节）。公式不读取账号、钥匙串或服务器。
  * **FLUTE v2（通用版 1.8）**：头部为未加密的明文目录（从偏移 21 处直接连续存储文件元数据），无需 ChaCha20 解密。
- **统一的相对位置 XOR 正文混淆**：
  * 无论是 FLUTE v2 还是 v3，所有内部文件正文均统一使用 `P[i] = C[i] ^ b"symphony"[i % 8] ^ (i & 255)` 进行流式还原。
- **离线模型下载直链与 LuLu 防火墙放行**：
  * 逆向出官方模型分发接口与对象存储 CDN 规则，通过配置最小白名单（`effect.snssdk.com:443` 与 `*.byteeffecttos.com:443`）即可在阻断所有隐私打点与云端音频流的前提下正常下载并更新离线模型。

> [!IMPORTANT]
> 仓库提供的分析工具已全面支持自适应识别本地激活模型、解析 FLUTE v2/v3 容器。仓库不提供受版权保护的加密源包、解密权重、输入法二进制或 LuLu 配置文件。

阅读入口按用途划分：

- [格式、密钥与校验](model-analysis/FINDINGS.md) 说明 FLUTE v2/v3 容器布局、派生公式、内部组件与多版本对比。
- [离线模型下载与防火墙放行](OFFLINE_MODEL_DOWNLOAD.md) 说明离线模型官方 CDN 直链、下载调度协议分析及 LuLu 最小防火墙放行规则。
- [模型结构与来源对比](comparison/COMPARISON.md) 区分本机证据、公开路线和未知血缘。
- [文件功能索引](FILE_INDEX.md) 列出每个文件的职责，[发布范围](PRIVACY.md) 说明身份信息和数据边界。
- [复现步骤](#复现目录验证与解包) 给出目录验证、流式解包和完整输出核对命令。

## 模型架构

主模型离线语音识别架构包含 VAD、流式识别和上下文识别路径：

![豆包输入法离线语音识别架构，包含 VAD、流式识别和上下文识别路径](diagrams/doubao-asr-architecture.png)

蓝色表示流式路径，紫色表示上下文路径，橙色虚线表示 draft 的配置引用。图依据静态配置和模型图标记绘制。

[查看原图](diagrams/doubao-asr-architecture.png) · [可编辑源码](diagrams/doubao-asr-architecture.dot) · [图例、证据范围与渲染命令](diagrams/README.md)

## 结论与证据

| 项目 | 1.1.1 专业版 (`acllm_pro_model_mac`) | 1.1.1 通用版 (`acllm_general_model_mac`) | 1.1.0 旧版主模型 (`acllm_main_model_mac`) |
| :--- | :--- | :--- | :--- |
| **源包大小** | 1,487,023,817 字节 (~1.48 GB) | 463,455,256 字节 (~463 MB) | 824,999,405 字节 (~825 MB) |
| **源包 MD5** | `4f19c90670291b502a4dd34b936e5f2f` | `a6846b0a91ac8a9579468e252c1da2e5` | `c31bdfbd138e9beac48e02672f98f1e8` |
| **容器格式** | FLUTE v3（343 字节 Header，6 文件） | FLUTE v2（331 字节 Header，6 文件） | FLUTE v3（1143 字节 Header，20 文件） |
| **目录密钥** | 根种子 + 12B Nonce 确定性派生 | **明文无加密**（直接解析） | 根种子 + 12B Nonce 确定性派生 |
| **正文混淆** | 相对偏移 `symphony` XOR 混淆 | 相对偏移 `symphony` XOR 混淆 | 相对偏移 `symphony` XOR 混淆 |
| **内部组成** | 6 个聚合文件（含 `nonstream.packed`） | 6 个聚合文件（含 `no_stream.packed`） | 20 个解离 `.pthlite` 权重文件 |
| **VAD 模型** | SHA-256: `6ce8753453...` (100% 一致) | SHA-256: `6ce8753453...` (100% 一致) | SHA-256: `d9e761d710...` (旧版) |
| **验证报告** | [verification-pro.json](model-analysis/verification-pro.json) | [verification-general.json](model-analysis/verification-general.json) | [verification.json](model-analysis/verification.json) |
| **解包报告** | [extraction-report-pro.json](model-analysis/extraction-report-pro.json) | [extraction-report-general.json](model-analysis/extraction-report-general.json) | [extraction-report.json](model-analysis/extraction-report.json) |

## 目录职责

```text
doubao-ime-analysis/
├── README.md                    入口、结论与复现命令
├── FILE_INDEX.md                每个文件的核心功能（32 个文件）
├── OFFLINE_MODEL_DOWNLOAD.md    离线语音模型官方 CDN 直链与 LuLu 防火墙放行策略
├── PRIVACY.md                   发布内容和身份信息范围
├── environment.json            分析对象指纹与环境配置（1.1.0/1.1.1）
├── requirements.txt            两个工具的 Python 依赖
├── model-analysis/              自适应验证与流式解包工具、验证报告、密钥产物
├── model-config/                主模型当前配置与提示模板，供结构分析
├── diagrams/                    模型架构图、可编辑源码与图例
└── comparison/                  公开模型对比、选定结构证据与来源链接
```

## 复现目录验证与解包

### 1. 准备源包与依赖

从仓库根目录执行命令。运行前需要：
- Python 3.11 或更新版本（本次验证使用 Python 3.12.12）。
- 本机已通过输入法设置下载了离线模型（支持专业版、通用版或旧版主模型）。
- 若执行完整提取，需预留足够的磁盘空间（专业版约 1.5 GB，通用版约 500 MB）。

安装依赖（无需 Git LFS、Unicorn 或 Capstone）：

```sh
python3 -m pip install -r requirements.txt
```

### 2. 验证目录与派生密钥

工具会自动读取 `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_active_layout.json` 检测当前激活的模型：

```sh
# 自动检测当前激活模型并验证
python3 model-analysis/verify_directory.py

# 或显式指定模型路径验证（如专业版）
python3 model-analysis/verify_directory.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model"

# 或显式指定通用版模型验证
python3 model-analysis/verify_directory.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model"
```

### 3. 流式提取全部内部文件

流式解包至指定目录（若目录不存在将自动创建）：

```sh
# 提取专业版
mkdir -p .local-data
python3 model-analysis/extract_model.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model" \
  .local-data/extracted-pro

# 提取通用版
python3 model-analysis/extract_model.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model" \
  .local-data/extracted-general
```

### 4. 核对完整输出

对已解包目录进行源包与哈希一致性比对：

```sh
python3 model-analysis/extract_model.py --verify-only \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model" \
  .local-data/extracted-pro
```

## 分析环境与范围

| 项目 | 本次分析环境 |
| --- | --- |
| **分析时间** | 2026-11-09 至 2026-11-18 |
| **输入法** | 豆包输入法 macOS 版 `1.1.1`（Build `1`，Wave `1.1.1.3`，Build Number `1010103`）及 `1.1.0`（Build `1`） |
| **主程序 SHA-256** | `8544564ffffae4abfe64df721a71b971408fb4a124512138d040c992456435b3` |
| **测试系统** | macOS 27.2.1，Build `26B131` |
| **测试硬件** | MacBook Air，Apple M5，ARM64，16 GB 内存 |
| **Python** | Miniforge Python 3.12.12 |
| **运行依赖** | NumPy 2.3.5、PyCryptodome 3.23.0 |

完整应用指纹和分析工具版本见 [environment.json](environment.json)。
用户名路径和提交身份的处理见 [PRIVACY.md](PRIVACY.md)。
