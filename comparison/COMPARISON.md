# 1.1.1 模型结构与公开语音模型对比

## 核心判断

基于 1.1.1 两款本地模型的配置文件（[专业版](../model-config/pro-config.yaml)、[通用版](../model-config/general-config.yaml)）、`.packed` 图字符串及应用静态标记：

- **技术路线接近 Seed-ASR / AcLLM**：同为 Conformer 声学编码器 + 上下文音频条件 LLM 解码器（支持对话历史、光标上下文、热词与纠错提示），面向端侧离线转写裁剪。
- **与 efeslab/LiteASR 明显不同**：LiteASR 面向 Whisper 编码器做 SVD 低秩压缩，而本地模型是 80 维 fbank + 24 层 Conformer + GPT 风格解码器 + MNN / Panther 推理栈。包内代号 `LiteASRP_*` / `LiteASRm_*` 只是命名巧合。
- **不同于豆包实时语音模型**：包内只有转写链路（VAD + ASR 编码/解码 + Prompt），没有语音合成声码器。

> 注：以上结论基于静态配置、模型图字符串和公开论文/源码对比；具体训练权重来源与识别指标无法仅靠静态分析确认。

---

## 1.1.1 专业版 vs 通用版架构对比

1.1.1 将引擎统一迁至 `AsrContextExecutor` + `IntegrationEngineCreator`，用 MNN `.packed` 包取代 1.1.0 的 20 个散装 `.pthlite` 文件，并分化为两条规格：

| 维度 | 专业版 (`acllm_pro_model_mac` 1.5) | 通用版 (`acllm_general_model_mac` 1.8) |
| :--- | :--- | :--- |
| **配置代号** | `LiteASRP_v1.2.0_7` | `LiteASRm_v1.0.1_5` |
| **源包大小** | 1.48 GB（FLUTE v3） | 463 MB（FLUTE v2） |
| **权重共享** | `share_weight: false`（流式与非流式完全独立） | `share_weight: true`（共享骨干参数） |
| **非流式音频输入** | 独立 `nonstream_feature_extractor`，直接吃 `fbank` | 复用流式输出的 880 维音频投影（`audio_proj`，4 倍下采样） |
| **硬件调度** | 流式 `cpu`；非流式 `metal`（Apple GPU） | 拆到编/解码级：macOS 流式编码 `metal`、解码 `cpu`，非流式全 `metal`；Android 配 `hexagon` |
| **解码器与图标记** | `stream.packed` 12 层、`nonstream.packed` 29 层（含 `.mnn`、RoPE） | `stream.packed` 12 层、`no_stream.packed` 含 24 层 Macaron Conformer 编码器 |
| **非流式最大 Token** | `256` | `1000` |
| **Prompt 模板** | `lr_context`、`default` | `lr_context`、`default`、`bot_context` |
| **1.1.1 共同新增** | `tail_vad_probe`（10 帧尾静音快检）、`rag_words`（热词注入）、18.5 s 分段上限 | 同左 |

---

## 与 efeslab/LiteASR 的差异

对比对象固定在 [LiteASR 提交 `da5be85`](https://github.com/efeslab/LiteASR/tree/da5be85382a6fc22245803c18c820b5c1b049ef8) 与公开模型 `lite-whisper-large-v3-turbo`（配置摘录见 [public-model-and-papers.json](public-model-and-papers.json)）：

| 维度 | 豆包输入法本地模型（1.1.1） | LiteASR (`lite-whisper-large-v3-turbo`) |
| :--- | :--- | :--- |
| **声学特征** | 16 kHz / 80 维 fbank + CMVN | 128 维 mel |
| **音频编码器** | 24 层 Conformer（Macaron FFN + Depthwise Conv + RoPE） | 32 层 Whisper Transformer 编码器 |
| **解码器** | 双路径：12 层流式 + 29 层非流式上下文（1.1.1 专业版） | 4 层 Whisper 解码器 |
| **压缩手段** | 量化（QW4 / W4A8）、融合算子、跨路径共享权重（通用版） | 校准激活 PCA/SVD 低秩分解（`weight1` / `weight2` 替换线性层） |
| **上下文能力** | 内置对话历史、光标前后文、热词、纠错记录、ITN 与语气词标注 | 标准 Whisper 转写，主要压缩编码器 |
| **推理运行时** | `flute` + MNN（`.mnn` 打包于 `.packed`）+ Panther Lite（VAD） | PyTorch / Transformers / Triton |

---

## 与 Seed-ASR / AcLLM 的对应与差异

[Seed-ASR 论文 v1](https://arxiv.org/html/2407.04675v1) 提出 Audio-conditioned LLM（AcLLM）架构，论文摘要提到已用于字节豆包语音识别产品；[官方演示页](https://bytedancespeech.github.io/seedasr_tech_report/) 展示的上下文字段与本地 `config.yaml` 里的 Prompt 占位符高度吻合：

| 概念 / 能力 | Seed-ASR 论文 / 演示 | 豆包输入法 1.1.1 本地模型 |
| :--- | :--- | :--- |
| **音频编码器** | LUISE（约 2B 参数、32 层 Conformer） | 24 层 Conformer（端侧轻量版） |
| **语言模型** | 数百亿参数 MoE | 端侧小模型（专业版整包 1.48 GB，通用版 463 MB） |
| **对话与角色上下文** | 对话历史、智能体名称与设定、修改记录 | `@@DIALOG@@`、`@@BOT_NAME@@`、`@@BOT_DESC@@`、`@@USER_MODIFY@@` |
| **输入法专属上下文** | 音频 + 上下文共同转写 | 额外加入光标前后文 `@@CUR_CONTEXT@@`、`@@HOTWORDS@@` 与 `rag_words` |

---

## 与豆包实时语音模型的区别

[豆包实时语音模型](https://seed.bytedance.com/en/blog/doubao-realtime-voice-model-is-available-upon-release-high-eq-and-iq)是端到端语音对话模型（支持 S2S / T2S 语音生成）。本机离线包内只有 VAD、特征提取、ASR 编解码和转写 Prompt，不含任何声码器或音频合成模块，定位纯粹是语音转文字。

---

## 证据索引

- 1.1.1 配置：[pro-config.yaml](../model-config/pro-config.yaml) · [general-config.yaml](../model-config/general-config.yaml) · [fbank.conf](../model-config/asr/feature_extractor/fbank.conf)
- 静态算子与历史图标记：[runtime-markers.json](runtime-markers.json) · [model-metadata.json](model-metadata.json)（1.1.0 `.pthlite` 扫描记录）
- 公开资料来源：[sources.json](sources.json) · [public-model-and-papers.json](public-model-and-papers.json)
