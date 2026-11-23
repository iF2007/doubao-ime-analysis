# 豆包输入法 macOS 离线语音模型分析

> [!NOTE]
> 仅供学习与技术分析。**本分支（`main`）对应最新版本 macOS `1.1.1`**；如需查看旧版分析结果与原始产物，请切换到对应 Git Tag（如 `git checkout macos_1.1.0`）。

## 核心结论

豆包输入法 macOS `1.1.1` 将离线语音识别拆分为 **专业版**（1.48 GB）和 **通用版**（463 MB）两套模型，另配 108 MB 上下文辅助词典：

- **打包方式大改**：不再像 1.1.0 那样散放 20 个 `.pthlite` 文件，而是收拢为 **6 个文件**。核心 ASR 引擎改用 MNN（`.mnn`），打包进 `stream.packed` 与 `nonstream.packed` / `no_stream.packed`；只有 VAD 仍保留 `vad_v4.pth.pthlite`，且专业版与通用版的 VAD、fbank、CMVN 三个文件完全相同。
- **双模型架构分工**：
  - **专业版（`LiteASRP_v1.2.0_7`）**：流式与非流式权重完全独立（`share_weight: false`），非流式独立抽特征并走 Apple Metal GPU 加速。
  - **通用版（`LiteASRm_v1.0.1_5`）**：流式与非流式共享骨干权重（`share_weight: true`），非流式直接复用流式输出的 880 维音频特征，体积不到专业版三分之一。
- **容器与还原算法**：
  - **专业版用 FLUTE v3**：目录表使用 ChaCha20（Counter 1）加密，密钥由客户端固定 32 字节种子、包内 12 字节 Nonce 和 Header Size 确定性算出，不联网也不读账号信息。
  - **通用版用 FLUTE v2**：目录表**明文存储**，从偏移 21 字节起直接读取。
  - **正文混淆统一**：v2 与 v3 的内部文件正文都用同一条按文件内相对偏移计算的 XOR 公式还原：`P[i] = C[i] ^ b"symphony"[i % 8] ^ (i & 255)`。
- **离线下载与断网运行**：官方模型托管在 `byteeffecttos.com` CDN，配置 LuLu 防火墙仅放行 `effect.snssdk.com:443` 和 `*.byteeffecttos.com:443` 即可正常下载更新；下完后彻底断网，离线转写照常工作。

## 1.1.1 模型速览

| 项目 | 专业版 (`acllm_pro_model_mac`) | 通用版 (`acllm_general_model_mac`) | 上下文辅助 (`acllm_context_model_mac`) |
| :--- | :--- | :--- | :--- |
| **版本 / 标签** | `1.5` / `LiteASRP_v1.2.0_7` | `1.8` / `LiteASRm_v1.0.1_5` | `1.1` |
| **源包大小** | 1,487,023,817 B (~1.48 GB) | 463,455,256 B (~463 MB) | 108,300,553 B (~108 MB) |
| **源包 MD5** | `4f19c90670291b502a4dd34b936e5f2f` | `a6846b0a91ac8a9579468e252c1da2e5` | `32c387bc13445d1b020077c168c0d2c9` |
| **容器格式** | FLUTE v3（343 B Header，6 文件） | FLUTE v2（331 B Header，6 文件） | ZIP（词典 / NER / 拼音） |
| **目录加密** | ChaCha20（种子 + Nonce 派生） | 明文无加密 | 无 |
| **权重策略** | 流式 / 非流式独立；非流式走 Metal | 共享骨干权重；复用 880 维音频特征 | 静态词典与辅助模型 |
| **验证 / 解包报告** | [验证](model-analysis/verification-pro.json) · [解包](model-analysis/extraction-report-pro.json) | [验证](model-analysis/verification-general.json) · [解包](model-analysis/extraction-report-general.json) | 见 [下载文档](OFFLINE_MODEL_DOWNLOAD.md) |

> 1.1.0 旧版单模型（`acllm_main_model_mac` 1.8，825 MB，20 个文件）的完整分析与产物保留在 Tag `macos_1.1.0`。

## 文档导航

- [格式、密钥与内部文件清单](model-analysis/FINDINGS.md)：FLUTE v2/v3 二进制结构、密钥派生步骤、XOR 还原与 1.1.1 全部内部文件哈希。
- [离线模型直链与 LuLu 规则](OFFLINE_MODEL_DOWNLOAD.md)：官方 CDN 下载直链、调度接口参数与防火墙最小放行/阻断清单。
- [模型架构与公开路线对比](comparison/COMPARISON.md)：1.1.1 双模型配置差异，以及与 Seed-ASR / LiteASR / 实时语音模型的对比。
- [文件索引](FILE_INDEX.md) · [发布范围与隐私处理](PRIVACY.md) · [架构图说明](diagrams/README.md)

## 模型架构图

下图绘制自 1.1.0 主模型静态配置，展示了 VAD、流式与上下文双路径的整体骨架；1.1.1 延续了该双路径设计，并新增尾部静音探测（`tail_vad_probe`）、热词检索（`rag_words`）及 `.packed` 引擎封装（详见 [架构图说明](diagrams/README.md) 与 [1.1.1 配置文件](model-config/pro-config.yaml)）：

![豆包输入法离线语音识别架构](diagrams/doubao-asr-architecture.png)

[查看原图](diagrams/doubao-asr-architecture.png) · [Graphviz 源码](diagrams/doubao-asr-architecture.dot) · [图例与 1.1.1 演进](diagrams/README.md)

## 复现步骤

仓库不提供模型源包或权重，需先在本机豆包输入法中下载离线模型。工具同时兼容 1.1.1 专业版、通用版和 1.1.0 旧版模型。

### 1. 安装依赖（Python 3.11+）

```sh
python3 -m pip install -r requirements.txt
```

### 2. 验证容器目录与密钥派生

不传 `--model` 时会自动读取 `offline_model_active_layout.json` 检测当前激活的模型：

```sh
# 自动检测当前激活模型
python3 model-analysis/verify_directory.py

# 显式验证 1.1.1 专业版
python3 model-analysis/verify_directory.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model"

# 显式验证 1.1.1 通用版
python3 model-analysis/verify_directory.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model"
```

### 3. 流式解包并校验

工具以 4 MiB 分块流式还原，解包后自动逐文件回读核对大小与 SHA-256：

```sh
# 解包专业版（约需 1.5 GB 空间）
python3 model-analysis/extract_model.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model" \
  .local-data/extracted-pro

# 解包通用版（约需 500 MB 空间）
python3 model-analysis/extract_model.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model" \
  .local-data/extracted-general

# 仅核对已解包目录与源包是否逐字节一致（不写入）
python3 model-analysis/extract_model.py --verify-only \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model" \
  .local-data/extracted-pro
```

## 目录结构

```text
doubao-ime-analysis/
├── README.md                   入口、核心结论与复现命令
├── OFFLINE_MODEL_DOWNLOAD.md   1.1.1 官方 CDN 直链、调度接口与 LuLu 规则
├── FILE_INDEX.md               全部 27 个文件的职责索引
├── PRIVACY.md                  公开范围与身份脱敏说明
├── environment.json            1.1.1 应用指纹与分析环境
├── requirements.txt            Python 依赖（numpy / pycryptodome）
├── model-analysis/             FLUTE v2/v3 验证与解包脚本、种子、1.1.1 校验报告
├── model-config/               1.1.1 专业版 / 通用版配置与 fbank 参数
├── diagrams/                   架构图与 Graphviz 源码
└── comparison/                 1.1.1 结构对比、模型标记与公开资料链接
```

## 分析环境

| 项目 | 详情 |
| :--- | :--- |
| **目标应用** | 豆包输入法 macOS `1.1.1`（Build `1`，Wave `1.1.1.3`，Build Number `1010103`） |
| **主程序 SHA-256** | `8544564ffffae4abfe64df721a71b971408fb4a124512138d040c992456435b3` |
| **测试环境** | macOS 27.2.1 (`26B131`) · MacBook Air Apple M5 (16 GB) · Python 3.12.12 |
| **运行依赖** | `numpy==2.3.5` · `pycryptodome==3.23.0` |

完整指纹见 [environment.json](environment.json)。
