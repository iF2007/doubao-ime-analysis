# 豆包输入法 macOS 离线语音模型分析

> [!NOTE]
> `main` 分支记录豆包输入法 macOS `1.1.2` 的静态分析结果与验证工具。旧版归档在 Git Tag（例如 `git checkout tags/macos_1.1.0`）。本项目仅用于技术学习以及安全与架构研究，使用前请先阅读[合规与使用边界](#合规与使用边界)。

## 核心结论

豆包输入法 macOS `1.1.2` 包含专业版（1.48 GB）和通用版（463 MB）两套离线 ASR 模型，以及 108 MB 上下文辅助词典。

- 每套 ASR 模型只包含 6 个内部文件。ASR 权重采用 MNN 格式，打包在 `stream.packed` 与 `nonstream.packed`（通用版文件名为 `no_stream.packed`）中；VAD 网络继续使用 `vad_v4.pth.pthlite`。两套模型的 VAD 网络、fbank 参数和 CMVN 矩阵完全一致。
- 专业版（`LiteASRP_v1.2.0_7`）将流式和非流式权重分开保存（`share_weight: false`），非流式路径独立提取特征并在 Apple Metal GPU 上运行。
- 通用版（`LiteASRm_v1.0.1_5`）共享流式和非流式骨干权重（`share_weight: true`），非流式路径直接复用流式输出的 880 维音频特征，体积不到专业版的三分之一。
- 专业版使用 FLUTE v3 容器，通过固定 32 字节根种子、包内 12 字节 Nonce 和 Header Size 本地派生密钥，再用 ChaCha20（Counter 1）解密目录表，整个过程不联网也不读取账号信息。通用版使用 FLUTE v2 容器，目录表从偏移 21 字节起明文存储。
- FLUTE v2 与 v3 的内部文件正文采用同一条 XOR 公式还原：`P[i] = C[i] ^ b"symphony"[i % 8] ^ (i & 255)`，其中 `i` 是每个内部文件内的相对字节偏移。
- 官方离线包托管在 `byteeffecttos.com` CDN。在 LuLu 防火墙中仅放行 `effect.snssdk.com:443` 和 `*.byteeffecttos.com:443` 即可下载模型；下载完成后，断网状态下本地离线转写仍然正常。

## 1.1.2 模型清单

下表列出豆包输入法 macOS `1.1.2` 离线语音功能的 3 个组件。

| 属性 | 专业版（`acllm_pro_model_mac`） | 通用版（`acllm_general_model_mac`） | 上下文辅助（`acllm_context_model_mac`） |
| :--- | :--- | :--- | :--- |
| 版本与配置标签 | `1.5` · `LiteASRP_v1.2.0_7` | `1.8` · `LiteASRm_v1.0.1_5` | `1.1` |
| 源包大小 | 1,487,023,817 B（约 1.48 GB） | 463,455,256 B（约 463 MB） | 108,300,553 B（约 108 MB） |
| 源包 MD5 | `4f19c90670291b502a4dd34b936e5f2f` | `a6846b0a91ac8a9579468e252c1da2e5` | `32c387bc13445d1b020077c168c0d2c9` |
| 容器格式 | FLUTE v3（343 B Header，6 个文件） | FLUTE v2（331 B Header，6 个文件） | ZIP 归档（词典、NER 与拼音） |
| 目录加密方式 | ChaCha20（种子与 Nonce 本地派生密钥） | 明文存储 | 无 |
| 权重与特征策略 | 流式与非流式独立权重；非流式运行于 Metal | 共享骨干权重；复用 880 维音频特征 | 静态词典与辅助模型 |
| 校验与解包报告 | [专业版容器校验报告](model-analysis/container-verify-pro.json) · [专业版解包文件清单](model-analysis/extraction-report-pro.json) | [通用版容器校验报告](model-analysis/container-verify-general.json) · [通用版解包文件清单](model-analysis/extraction-report-general.json) | 见[离线模型直链与防火墙配置](OFFLINE_MODEL_DOWNLOAD.md) |

> 1.1.0 旧版单模型（`acllm_main_model_mac` 1.8，825 MB，20 个内部文件）的分析与产物保留在 Git Tag `macos_1.1.0`。

## 文档导航

下列文档分别记录容器格式、网络规则与模型结构分析。

- [FLUTE 容器格式、密钥派生与内部文件清单](model-analysis/CONTAINER_AND_DECRYPTION.md)：FLUTE v2 与 v3 二进制布局、密钥派生步骤、XOR 还原算法和全部内部文件哈希。
- [离线模型直链与 LuLu 防火墙配置](OFFLINE_MODEL_DOWNLOAD.md)：官方 CDN 下载直链、客户端调度接口参数以及最小放行和阻断规则。
- [双模型与公开语音模型架构对比](comparison/ARCHITECTURE_COMPARISON.md)：专业版与通用版的配置差异，以及与 Seed-ASR、LiteASR 和实时语音模型的对比。
- [仓库文件索引](FILE_INDEX.md) · [发布范围、隐私与合规声明](PRIVACY.md) · [架构图说明与渲染方法](diagrams/README.md)

## 模型架构图

下图基于 [专业版配置](model-config/pro-config.yaml)、[通用版配置](model-config/general-config.yaml) 以及 `.packed` 内部图结构绘制，展示 VAD 与尾静音快检、流式实时路径，以及专业版独立权重与通用版共享骨干的差异。

![豆包输入法 1.1.2 离线语音识别架构](diagrams/doubao-asr-architecture.png)

[查看架构图原图](diagrams/doubao-asr-architecture.png) · [Graphviz 源码](diagrams/doubao-asr-architecture.dot) · [架构图说明与重新渲染步骤](diagrams/README.md)

## 复现容器校验与模型提取

仓库不提供模型源包或权重。运行下列命令前，先在本地豆包输入法中下载离线语音模型。工具支持 `1.1.2` 专业版、通用版和 `1.1.0` 旧版模型。

1. 安装 Python 依赖（需要 Python 3.11 或更高版本）：

   ```sh
   python3 -m pip install -r requirements.txt
   ```

2. 校验本地模型容器头、目录解密与 XOR 掩码：

   - 校验本机已下载的全部离线模型：

     ```sh
     python3 model-analysis/verify_container.py --all
     ```

   - 只校验当前激活模型（脚本会读取 `offline_model_active_layout.json`）：

     ```sh
     python3 model-analysis/verify_container.py
     ```

   - 校验指定路径的源包：

     ```sh
     python3 model-analysis/verify_container.py \
       --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model"
     ```

   命令会在终端输出 JSON 格式的校验结果。确认每套模型都包含 `"candidate_verified": true` 和 `"payload_xor_verified": true`。

3. 以 4 MiB 分块流式提取内部文件并回读校验（默认输出到 `.local-data/extracted-<variant>/`）：

   - 提取本机全部已下载模型（专业版需约 1.5 GB 空间，通用版需约 500 MB 空间）：

     ```sh
     python3 model-analysis/extract_model.py --all
     ```

   - 只提取当前激活模型：

     ```sh
     python3 model-analysis/extract_model.py
     ```

   - 只校验已提取目录与源包是否逐字节一致（不写入磁盘）：

     ```sh
     python3 model-analysis/extract_model.py --all --verify-only
     ```

   提取完成后，脚本会在目标目录生成 `extraction-report.json`，并在末尾打印 `Verified all 6 files ... against decrypted source payloads.`。

## 目录结构

下表列出仓库顶层目录分工；完整文件列表见[仓库文件索引](FILE_INDEX.md)。

```text
doubao-ime-analysis/
├── README.md                   仓库入口、核心结论与复现步骤
├── AGENTS.md                   AI Agent 维护规范与更新门禁
├── UPDATE_PROMPT.md            新版发布时的复用更新 Prompt
├── OFFLINE_MODEL_DOWNLOAD.md   官方 CDN 直链、调度接口与 LuLu 规则
├── FILE_INDEX.md               仓库全部文件的职责索引
├── PRIVACY.md                  收录范围、隐私脱敏与合规边界
├── environment.json            应用指纹、模型元数据与分析环境
├── requirements.txt            Python 运行依赖
├── scripts/                    本机安装盘点与仓库一致性门禁脚本
├── model-analysis/             FLUTE v2 和 v3 验证解包脚本、根种子与校验报告
├── model-config/               专业版与通用版配置及 fbank 参数
├── diagrams/                   架构图与 Graphviz 源码
└── comparison/                 模型结构对比、运行时标记与公开资料索引
```

## 分析环境

下表记录本次静态分析所核对的目标应用指纹与本地验证环境，完整信息见 [environment.json](environment.json)。

| 项目 | 详情 |
| :--- | :--- |
| 目标应用 | 豆包输入法 macOS `1.1.2`（Build `1`，Wave `1.1.2.2`，Build Number `1010202`） |
| 主程序 SHA-256 | `c36348f714eb4e9883487d1b7b96e1ad5e57d1d13545da084173b4785173df7b` |
| 测试环境 | macOS 27.2.1 (`26B131`) · MacBook Air Apple M5 (16 GB) · Python 3.12.12 |
| 运行依赖 | `numpy==2.3.5` · `pycryptodome==3.23.0` |

## 合规与使用边界

以下条款约定本仓库的分析范围与使用约束，详情见[发布范围、隐私与合规声明](PRIVACY.md)。

- 本仓库只记录本地客户端和离线语音模型的技术结构分析，不代表官方立场，也不构成法律或安全背书。
- 仓库只公开分析文档、配置结构和验证脚本，不提供、不镜像也不二次分发模型权重、加密源包或应用程序二进制。
- 请勿将仓库内容用于商业集成、绕过授权限制、批量抓取官方 CDN、篡改软件或任何违反适用法律和原软件服务条款的行为。使用方需自行承担合规责任。
- 文中提及的商标、产品名称和协议结构归原权利人所有。如果权利方认为仓库存在侵权或不当内容，请通过 Issue 联系，我们核实后会及时处理或移除。
