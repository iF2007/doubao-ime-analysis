# 文件功能索引

公开仓库包含 24 个文件。路径相对于仓库根目录；本机解包输出、LuLu 备份、发布工具及缓存不计入。

目录职责与复现命令见 [README.md](README.md)。模型配置属于结构分析证据，未提供完整推理依赖。

## 根目录

入口、环境、依赖和发布范围。

| 文件 | 核心功能 |
| --- | --- |
| [.gitignore](.gitignore) | 排除本机数据、权重、工具和缓存，防止误提交 |
| [FILE_INDEX.md](FILE_INDEX.md) | 列出公开仓库中每个文件的核心功能 |
| [PRIVACY.md](PRIVACY.md) | 公开内容、匿名身份及平台日志边界 |
| [README.md](README.md) | 结论入口、分析范围、环境摘要和可复现命令 |
| [environment.json](environment.json) | 输入法和模型版本、原件指纹及分析环境 |
| [requirements.txt](requirements.txt) | 两个 Python 工具的 NumPy 和 PyCryptodome 分发版本 |

## model-analysis/

有效工具、关键派生产物和验证结果。

| 文件 | 核心功能 |
| --- | --- |
| [model-analysis/FINDINGS.md](model-analysis/FINDINGS.md) | 容器布局、密钥派生、正文恢复、组件大小及校验限制 |
| [model-analysis/directory-key.bin](model-analysis/directory-key.bin) | 已确认的 32 字节目录密钥，用于结果核对 |
| [model-analysis/emulated-directory.bin](model-analysis/emulated-directory.bin) | 1110 字节原指令模拟目录明文，供逐字节参考比较 |
| [model-analysis/extract_model.py](model-analysis/extract_model.py) | 流式恢复全部内部文件，或核对完整本机解包输出 |
| [model-analysis/extraction-report.json](model-analysis/extraction-report.json) | 20 个文件的大小、MD5、SHA-256 及三项清单差异 |
| [model-analysis/generation-verification.json](model-analysis/generation-verification.json) | 真实及合成元数据案例的原分析派生验证记录 |
| [model-analysis/model-seed.bin](model-analysis/model-seed.bin) | 派生工具必需的 32 字节固定种子 |
| [model-analysis/verification.json](model-analysis/verification.json) | 真实模型目录结构、counter 对照和参考一致性结果 |
| [model-analysis/verify_directory.py](model-analysis/verify_directory.py) | 独立派生密钥，解密目录并核对结构与参考产物 |

## model-config/

从主模型提取的当前配置和提示。

| 文件 | 核心功能 |
| --- | --- |
| [model-config/asr/feature_extractor/fbank.conf](model-config/asr/feature_extractor/fbank.conf) | 16 kHz 音频和 80 维 ASR fbank 特征参数 |
| [model-config/config.yaml](model-config/config.yaml) | 主模型当前处理配置，连接 VAD、编码器、解码器和上下文提示 |
| [model-config/prompt_template.txt](model-config/prompt_template.txt) | 包内语音转写提示，包含数字转换、标点和语气词规则 |
| [model-config/vad/config.yaml](model-config/vad/config.yaml) | 包内独立 VAD 链路及语音开始、结束判定参数 |

## comparison/

模型结构对比及对应证据。

| 文件 | 核心功能 |
| --- | --- |
| [comparison/COMPARISON.md](comparison/COMPARISON.md) | 对比 Seed-ASR、LiteASR 和实时语音模型，并区分结构与来源结论 |
| [comparison/model-metadata.json](comparison/model-metadata.json) | 五个模型前 4 MiB 中的图名称、算子字符串及文件偏移 |
| [comparison/public-model-and-papers.json](comparison/public-model-and-papers.json) | 采集的公开 lite-whisper 配置摘录及论文来源元数据 |
| [comparison/runtime-markers.json](comparison/runtime-markers.json) | 与结构结论相关的应用静态算子和 AcLLM 标记 |
| [comparison/sources.json](comparison/sources.json) | 对比使用的 LiteASR 固定提交和官方资料链接 |

用 `git ls-files` 查看本版本的文件清单。该索引与实际提交清单核对，不包含已删除材料的历史路径。
