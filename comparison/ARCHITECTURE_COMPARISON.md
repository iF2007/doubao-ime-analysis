# 1.1.2 模型结构与公开语音模型对比

本文档基于 `1.1.2` 的[专业版配置](../model-config/pro-config.yaml)、[通用版配置](../model-config/general-config.yaml)、`.packed` 图字符串和应用二进制静态标记，说明本地离线模型的架构选择以及它与公开语音模型的差异。

## 核心结论

- 本地模型与 Seed-ASR 或 AcLLM 同属一条技术路线，采用 Conformer 声学编码器搭配上下文音频条件 LLM 解码器（支持对话历史、光标上下文、热词与纠错提示），并裁剪到端侧离线运行。
- 本地模型与 `efeslab/LiteASR` 架构不同。LiteASR 针对 Whisper 编码器做 SVD 低秩压缩，而本地模型运行 80 维 fbank、24 层 Conformer、GPT 风格解码器以及 MNN 和 Panther 推理栈。配置中的 `LiteASRP_*` 和 `LiteASRm_*` 只是命名相似。
- 本地模型不同于豆包实时语音模型，包内只包含 VAD、特征提取、ASR 编解码与转写 Prompt，没有语音合成声码器。

## 专业版与通用版架构对比

相比 `1.1.0` 的 20 个散装 `.pthlite` 文件，`1.1.2` 将推理引擎统一迁移到 `AsrContextExecutor` 与 `IntegrationEngineCreator`，改用 MNN `.packed` 打包，并新增 `tail_vad_probe`（10 帧尾静音快检）、`rag_words`（热词注入）和 18.5 s 分段上限。下表列出专业版与通用版的具体配置差异。

| 维度 | 专业版（`acllm_pro_model_mac` 1.5） | 通用版（`acllm_general_model_mac` 1.8） |
| :--- | :--- | :--- |
| 配置代号 | `LiteASRP_v1.2.0_7` | `LiteASRm_v1.0.1_5` |
| 源包大小 | 1.48 GB（FLUTE v3） | 463 MB（FLUTE v2） |
| 权重共享 | `share_weight: false`（流式与非流式完全独立） | `share_weight: true`（共享骨干参数） |
| 非流式音频输入 | 独立 `nonstream_feature_extractor`，直接输入 `fbank` | 复用流式输出的 880 维音频投影（`audio_proj`，4 倍下采样） |
| 硬件调度 | 流式运行于 `cpu`，非流式运行于 `metal` | macOS 流式编码用 `metal`、解码用 `cpu`，非流式全用 `metal`；Android 配置 `hexagon` |
| 解码器与图标记 | `stream.packed` 12 层、`nonstream.packed` 29 层（均内嵌 `.mnn` 与 RoPE） | `stream.packed` 12 层解码与编码器 `0..15` 层，`no_stream.packed` 含编码器 `16..23` 层（共 24 层 Macaron Conformer） |
| 非流式最大 Token | `256` | `1000` |
| Prompt 模板 | `lr_context`、`default` | `lr_context`、`default`、`bot_context` |
| 相比 1.1.0 新增 | `tail_vad_probe`（10 帧尾静音快检）、`rag_words`（热词注入）、18.5 s 分段上限 | `tail_vad_probe`、`rag_words`、18.5 s 分段上限 |

## 与 efeslab/LiteASR 的差异

下表将 `1.1.2` 本地模型与 [LiteASR 提交 `da5be85`](https://github.com/efeslab/LiteASR/tree/da5be85382a6fc22245803c18c820b5c1b049ef8) 以及公开模型 `lite-whisper-large-v3-turbo`（配置摘录见[公开模型与论文参考](public-references.json)）做对照。

| 维度 | 豆包输入法本地模型（`1.1.2`） | LiteASR（`lite-whisper-large-v3-turbo`） |
| :--- | :--- | :--- |
| 声学特征 | 16 kHz 采样率、80 维 fbank 与 CMVN | 128 维 mel |
| 音频编码器 | 24 层 Conformer（Macaron FFN、Depthwise Conv 与 RoPE） | 32 层 Whisper Transformer 编码器 |
| 解码器 | 双路径：12 层流式与 29 层非流式上下文（专业版） | 4 层 Whisper 解码器 |
| 压缩手段 | 量化（QW4 与 W4A8）、融合算子，以及跨路径共享权重（通用版） | 校准激活 PCA 与 SVD 低秩分解（用 `weight1` 和 `weight2` 替换线性层） |
| 上下文能力 | 内置对话历史、光标前后文、热词、纠错记录、ITN 与语气词标注 | 标准 Whisper 转写，主要压缩编码器 |
| 推理运行时 | `flute`、MNN（`.mnn` 打包于 `.packed`）与 Panther Lite（VAD） | PyTorch、Transformers 与 Triton |

## 与 Seed-ASR 及 AcLLM 的对应关系

[Seed-ASR 论文 v1](https://arxiv.org/html/2407.04675v1) 提出 Audio-conditioned LLM（AcLLM）架构，论文摘要提到该架构已用于豆包语音识别产品；[Seed-ASR 官方演示页](https://bytedancespeech.github.io/seedasr_tech_report/)展示的上下文字段与本地 `config.yaml` 中的 Prompt 占位符一致。下表对比云端与端侧配置。

| 概念与能力 | Seed-ASR 论文与演示 | 豆包输入法 `1.1.2` 本地模型 |
| :--- | :--- | :--- |
| 音频编码器 | LUISE（约 2B 参数，32 层 Conformer） | 24 层 Conformer（端侧轻量版本） |
| 语言模型 | 数百亿参数 MoE | 端侧小模型（专业版整包 1.48 GB，通用版 463 MB） |
| 对话与角色上下文 | 对话历史、智能体名称与设定、修改记录 | `@@DIALOG@@`、`@@BOT_NAME@@`、`@@BOT_DESC@@`、`@@USER_MODIFY@@` |
| 输入法专属上下文 | 音频与上下文共同转写 | 额外加入光标前后文 `@@CUR_CONTEXT@@`、`@@HOTWORDS@@` 与 `rag_words` |

## 与豆包实时语音模型的区别

[豆包实时语音模型](https://seed.bytedance.com/en/blog/doubao-realtime-voice-model-is-available-upon-release-high-eq-and-iq)是端到端语音对话模型，支持语音到语音以及文本到语音生成。豆包输入法本地模型只包含 VAD、特征提取、ASR 编解码与转写 Prompt，不含声码器或音频合成模块，只负责语音转文字。

## 证据索引

以下文件提供本页结论的原始配置与二进制扫描数据：

- `1.1.2` 模型配置：[专业版配置](../model-config/pro-config.yaml) · [通用版配置](../model-config/general-config.yaml) · [ASR fbank 参数](../model-config/asr/feature_extractor/fbank.conf)
- 静态算子与 `.packed` 扫描记录：[主程序运行时标记](runtime-markers.json) · [`.packed` 内嵌 `.mnn` 与层索引](packed-mnn-layers.json)
- 公开资料来源：[公开仓库与论文链接](sources.json) · [LiteASR 与论文摘录](public-references.json)
