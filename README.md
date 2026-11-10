# 豆包输入法离线语音模型分析

分析基于豆包输入法 **1.1.0，build 1**，主模型 **`acllm_main_model_mac` 1.8**。目录密钥的确定性派生公式、FLUTE v3 目录解密和全部 20 个内部文件的正文恢复均已验证。模型结构与 Seed-ASR / AcLLM 的公开路线更接近，现有证据不支持它直接基于 efeslab/LiteASR。

仓库保留有效工具、关键验证产物、当前配置和对比结论。**不提供加密源包、解密权重、应用二进制、内存快照或 LuLu 备份。** 两个脚本只适用于这次检查的主模型 1.8，不是通用模型解包器。精确参数量、训练权重来源和包内三项 MD5 差异的原因仍未确认。

## 结论与证据

| 项目 | 结果 | 证据 |
| --- | --- | --- |
| 主模型大小 | 824999405 字节，约 825 MB | [环境记录](environment.json) |
| 容器 | FLUTE v3，1143 字节头部，20 个内部文件 | [目录验证](model-analysis/verification.json) |
| 密钥 | 固定种子、12 字节 nonce 和 header size 确定性派生 | [格式与密钥](model-analysis/FINDINGS.md) |
| 正文 | 每个内部文件独立重置偏移的 XOR 混淆 | [解包工具](model-analysis/extract_model.py) |
| 提取完整性 | 20 个文件与源包解码内容一致 | [提取校验报告](model-analysis/extraction-report.json) |
| 包内 MD5 清单 | 5 项匹配、3 项不匹配，原因未明 | [格式与密钥](model-analysis/FINDINGS.md) |
| 可见结构 | 两套 24 层 Conformer 编码器图，12 层流式解码路径、28 层上下文解码路径、64000 词表 | [模型结构与来源对比](comparison/COMPARISON.md) |
| 来源判断 | 与 Seed-ASR / AcLLM 在结构和上下文设计上相似，具体血缘未确认 | [模型结构与来源对比](comparison/COMPARISON.md) |

## 目录职责

```text
doubao-ime-analysis/
├── README.md                    入口、结论与复现命令
├── FILE_INDEX.md                每个文件的核心功能
├── PRIVACY.md                   发布内容和身份信息范围
├── environment.json            分析对象指纹与环境
├── requirements.txt            两个工具的 Python 依赖
├── model-analysis/              密钥与解包代码、关键产物、验证报告
├── model-config/                主模型当前配置与提示模板，供结构分析
└── comparison/                  公开模型对比、选定结构证据与来源链接
```

逐文件说明见 [FILE_INDEX.md](FILE_INDEX.md)。`model-config/` 只保留分析需要的配置和提示，不是完整推理目录。配置中的权重、CMVN 和 tokenizer 路径指向原模型包，不由仓库提供。

## 复现目录验证与解包

从仓库根目录执行。需要 Python 3.11 或更新版本；本次验证使用 Python 3.12.12。还需要本机已有对应版本的源包，默认位置为：

```text
~/Library/Application Support/DoubaoIme/ASRModel/versions/1_8/asr_model.model
```

先安装依赖。公开仓库不需要 Git LFS、Unicorn 或 Capstone。

```sh
python3 -m pip install -r requirements.txt
```

重新派生密钥，并与分析时原指令模拟生成的目录逐字节比较：

```sh
python3 model-analysis/verify_directory.py \
  --reference-directory model-analysis/emulated-directory.bin
```

预期 `candidate_verified=true`，counter 1 的 `valid` 和 `matches_reference` 为 `true`。counter 0 失败是对照结果。目录 SHA-256 应为 `07e0a4590ced10d7fc0b094ea8ca948f1df61fb4e9e80f218373b5f67985b991`。

提取到新的本机目录。目标目录必须不存在，提取需要约 825 MB 空间：

```sh
mkdir -p .local-data
python3 model-analysis/extract_model.py .local-data/extracted-model
```

重新核对完整输出：

```sh
python3 model-analysis/extract_model.py --verify-only .local-data/extracted-model
```

预期全部 20 个文件通过源包一致性核对，同时报告包内 MD5 清单的 5 项匹配和 3 项差异。`--verify-only` 会更新输出目录的 `extraction-report.json`；成功退出不表示全部包内 MD5 项都匹配。不能对不含权重的 `model-config/` 运行全量核对。

`.local-data/` 和所有 `.pthlite` 文件均由 `.gitignore` 排除。仓库中的校验报告是分析结果，不会因上述命令自动覆盖。

## 分析环境与范围

分析时间为 2026-11-09 至 2026-11-10。环境为 macOS 27.2，build `26B123`，MacBook Air，Apple M5，ARM64，16 GB 内存。使用 Miniforge Python 3.12.12、NumPy 2.3.5 和 PyCryptodome 3.23.0。完整应用指纹和分析工具版本见 [environment.json](environment.json)。`LiteASRP_v1.1.2_6` 是包内配置标签，与输入法应用版本不同。

密钥来源通过独立分析进程及 ARM64 模拟检查，再用标准 ChaCha20 和源包正文核对。原安装应用和模型保持只读，没有附加或修改原输入法进程。公开仓库支持独立目录验证和解包，不包含保护虚拟机或原指令模拟的重放材料。[生成验证记录](model-analysis/generation-verification.json) 保存真实和合成元数据案例的原分析结果。

对比基于当前模型配置、五个模型文件前 4 MiB 的字符串证据、应用静态算子标记，以及分析时采集的公开资料。可见图名称和配置不能证明精确参数量、实际识别性能或训练来源。上下文辅助模型 `acllm_context_model_mac` 1.1 不在本次解包范围内。

用户名路径和提交身份的处理见 [PRIVACY.md](PRIVACY.md)。
