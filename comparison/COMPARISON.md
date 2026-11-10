# 主模型结构与公开语音模型的比较

本机主模型与字节 Seed-ASR / AcLLM 的公开技术路线更接近，尤其是 Conformer 编码器和上下文识别设计。与 efeslab/LiteASR 的 Whisper 编码器低秩压缩方案存在明显结构差异。现有证据不能确认本机权重来自某个公开模型，也不能确认它是 Seed-ASR 的压缩、蒸馏或微调版本。

对象是 `acllm_main_model_mac` 1.8，包内配置标签为 `LiteASRP_v1.1.2_6`。名称相似不能证明与 efeslab/LiteASR 的关系。本次未运行公共代码、下载公共模型权重或测量识别性能。

## 本机与 LiteASR 的结构差异

| 项目 | 本机主模型 1.8 | 采集的公开 lite-whisper-large-v3-turbo |
| --- | --- | --- |
| 编码器 | 两套模型图都有 24 层 Conformer 标记 | Whisper Transformer 编码器，32 层 |
| 音频特征 | ASR 配置为 80 维 fbank | 配置为 128 维 mel |
| 解码路径 | 12 层流式路径、28 层上下文路径 | 4 层 Whisper 解码器 |
| 词表 | 配置为 64000，使用 vocab 和 merges | 配置为 51866，使用 Whisper tokenizer |
| 可见优化 | QW4、W4A8 量化及融合算子、chunk 和 RoPE 状态、2 层 draft 配置 | 激活校准、PCA/SVD、低秩线性层、低维注意力计算 |
| 上下文 | 音频、热词、对话及光标周围文本共同参与提示 | LiteASR 主要压缩 Whisper 编码器 |
| 运行接口 | `flute.nn.PantherInference` 和 Panther Lite | PyTorch、Transformers 和 Triton 等公开实现 |

右侧描述的是本次采集的具体 Turbo 模型，不代表 LiteASR 支持的所有 Whisper 变体。[公开配置摘录](public-model-and-papers.json) 保存维度和逐层 `low_rank_config`。

LiteASR 的比较固定在提交 `da5be85382a6fc22245803c18c820b5c1b049ef8`，依据以下源码：

- [README](https://github.com/efeslab/LiteASR/blob/da5be85382a6fc22245803c18c820b5c1b049ef8/README.md) 将方法定义为利用激活低秩性质的 ASR 压缩，公开模型基于 Whisper。
- [compress.py](https://github.com/efeslab/LiteASR/blob/da5be85382a6fc22245803c18c820b5c1b049ef8/src/compress.py) 加载 Whisper，对校准激活执行 `torch.linalg.svd`，构建低秩层。
- [modeling_lite_whisper.py](https://github.com/efeslab/LiteASR/blob/da5be85382a6fc22245803c18c820b5c1b049ef8/src/lite_whisper/modeling_lite_whisper.py) 继承 Whisper 类，以带 `weight1`、`weight2` 的低秩层替换编码器投影和 FFN。

本机模型没有提供对应的 Whisper 结构或逐层低秩配置。算子编译和融合可能隐藏名称，因此结构差异比单独未检出某个字符串更能支撑判断。

## 本机证据与含义

[当前配置](../model-config/config.yaml) 描述两个 ASR 路径，包含以下字段：

- 两个编码器的 `fbank_length: 80`，`encoder_out_t: 1024`。
- 流式解码器的 `layer_num: 12`、`token_counts: 64000` 和 CIF 状态字段。
- 上下文解码器的 `layer_num: 28`、`kv_heads: 8`、`draft_layer_num: 2` 和 `draft_len: 2`。
- `flute.asr.acllm.HFTokenizer`、音频提示和上下文提示。

[模型图字符串](model-metadata.json) 保存五个权重文件各自前 4 MiB 中的名称及文件偏移。流式编码器有 `encoders.0` 至 `encoders.23` 的 `QW4ConformerLayerRopeChunk` 标记；另一编码器有同类算子的 24 层标记。流式解码器有 12 个 `W4A8GPT2TransformerBlock` 标记，上下文解码器有 `h.27.attn.query_layernorm.weight` 等名称。

[应用静态标记](runtime-markers.json) 保留相关 Conformer、W4A8、AcLLM 和上下文处理名称，用于交叉核对。主程序可能包含多种模型实现；静态标记不证明每个算子都在当前识别路径中启用。`GPT2` 类算子名称也不证明使用 OpenAI GPT-2 的预训练权重，`HFTokenizer` 不证明模型由 Hugging Face 公开权重微调而来。

配置和图名称支持结构判断，不足以计算精确参数量、确定全部执行路径、推导识别性能或证明训练来源。包内 MD5 的三项差异仍未解释，见 [格式与校验结果](../model-analysis/FINDINGS.md)。

## 与 Seed-ASR / AcLLM 的对应

[Seed-ASR 论文 v1](https://arxiv.org/html/2407.04675v1) 将框架称为 Audio conditioned LLM，即 AcLLM。连续语音表示和上下文共同输入 LLM，语音编码器 LUISE 基于 Conformer。[官方演示页](https://bytedancespeech.github.io/seedasr_tech_report/) 展示对话历史、智能体名字、智能体设定和修改记录。

| 公开能力 | 本机配置中的对应 |
| --- | --- |
| Conformer 音频编码器 | 24 层 `QW4ConformerLayerRopeChunk` 图标记 |
| Audio conditioned LLM | `flute.asr.acllm.HFTokenizer`、语音 embedding 输入上下文解码器 |
| 对话历史 | `@@DIALOG@@` |
| 智能体名字与设定 | `@@BOT_NAME@@`、`@@BOT_DESC@@` |
| 修改记录 | `@@USER_MODIFY@@`，实际生成方式未验证 |
| 语音和上下文共同转写 | `@@AUDIO@@`、热词及光标前后文 |

论文摘要脚注明确说明 Seed-ASR 已用于字节产品，并以 Doubao speech recognition models 提供商业服务。这个公开产品关系和具体上下文字段支持路线相似性，不能替代权重来源证据。

论文的 LUISE 音频编码器接近 2B 参数并有 32 层，LLM 为数百亿参数的 MoE。本机图层数、解码器配置及包大小不同，说明规模和部署形态不同。论文第 3.3 节的 converter 使用帧拼接和线性投影，本机配置则包含 CIF 路径；论文引用 CIF 不能证明它与本机使用相同实现。

目前没有将 `LiteASRP_v1.1.2_6` 映射到某个公开 Seed-ASR 权重版本的来源声明、训练记录或可对应指纹。

## 与豆包实时语音模型的区别

[Seed 团队官方介绍](https://seed.bytedance.com/en/blog/doubao-realtime-voice-model-is-available-upon-release-high-eq-and-iq) 将实时语音模型描述为集成语音理解和生成的端到端对话模型，支持 S2S、S2T、T2S 和 T2T。

本次主模型包的目标是转写，包含 ASR、VAD、tokenizer、编码器、解码器和提示。已检查的包内没有用于合成输出的声码器文件。因此 Seed-ASR 比实时语音对话模型更接近本次对象；这一判断不覆盖整个输入法或其他模型包。

来源链接和固定提交见 [sources.json](sources.json)。以上结论区分可见结构、路线相似性和未知训练血缘，不能将三者视为同一证明。
