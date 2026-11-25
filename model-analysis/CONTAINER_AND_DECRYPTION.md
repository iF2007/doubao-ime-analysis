# 1.1.2 离线模型容器格式、密钥派生与文件清单

本参考文档记录豆包输入法 macOS `1.1.2` 离线 ASR 模型（专业版 `acllm_pro_model_mac` 1.5 和通用版 `acllm_general_model_mac` 1.8）的容器布局、目录表解密、正文还原公式与内部文件校验值。

> `1.1.0` 旧版单模型（`acllm_main_model_mac` 1.8，含 20 个内部文件与 `model_md5s.txt` 清单）的记录保留在 Git Tag `macos_1.1.0`。

## 双模型容器规格

下表对比 `1.1.2` 两款离线 ASR 模型的源包属性、容器格式和报告链接。

| 属性 | 专业版（`acllm_pro_model_mac`） | 通用版（`acllm_general_model_mac`） |
| :--- | :--- | :--- |
| 版本与配置标签 | `1.5` · `LiteASRP_v1.2.0_7` | `1.8` · `LiteASRm_v1.0.1_5` |
| 源包大小 | 1,487,023,817 B（约 1.48 GB） | 463,455,256 B（约 463 MB） |
| 源包 MD5 | `4f19c90670291b502a4dd34b936e5f2f` | `a6846b0a91ac8a9579468e252c1da2e5` |
| 容器版本 | `FLUTE v3`（Header 343 B） | `FLUTE v2`（Header 331 B） |
| 目录表加密 | ChaCha20（Counter 1） | 明文无加密 |
| 正文混淆 | `symphony` 相对偏移 XOR | `symphony` 相对偏移 XOR |
| 内部文件数 | 6 | 6 |
| 权重共享策略 | `share_weight: false`（独立权重，非流式运行于 Metal） | `share_weight: true`（共享骨干，复用 880 维音频特征） |
| 校验与解包报告 | [专业版容器校验报告](container-verify-pro.json) · [专业版解包报告](extraction-report-pro.json) | [通用版容器校验报告](container-verify-general.json) · [通用版解包报告](extraction-report-general.json) |

## 容器二进制布局

### FLUTE v3（专业版 `1.5`）

下表按 0 起始字节偏移列出 FLUTE v3 的二进制布局。

| 偏移（字节） | 长度 | 说明 |
| :--- | :--- | :--- |
| `0..4` | 5 | Magic：`FLUTE`（ASCII） |
| `5..8` | 4 | uint32 LE：版本号 `3` |
| `9..16` | 8 | uint64 LE：Header 总字节数（专业版为 `343`） |
| `17..20` | 4 | uint32 LE：内部文件数（`6`） |
| `21..32` | 12 | ChaCha20 Nonce |
| `33..HeaderSize-1` | `HeaderSize - 33` | ChaCha20 加密后的目录表 |
| `HeaderSize..EOF` | 剩余全部 | 内部文件正文（顺序紧邻排列，经 XOR 混淆） |

### FLUTE v2（通用版 `1.8`）

下表按 0 起始字节偏移列出 FLUTE v2 的二进制布局。

| 偏移（字节） | 长度 | 说明 |
| :--- | :--- | :--- |
| `0..4` | 5 | Magic：`FLUTE`（ASCII） |
| `5..8` | 4 | uint32 LE：版本号 `2` |
| `9..16` | 8 | uint64 LE：Header 总字节数（通用版为 `331`） |
| `17..20` | 4 | uint32 LE：内部文件数（`6`） |
| `21..HeaderSize-1` | `HeaderSize - 21` | 明文目录表（无 Nonce；通用版为 `310` B） |
| `HeaderSize..EOF` | 剩余全部 | 内部文件正文（顺序紧邻排列，经 XOR 混淆） |

### 目录项格式

解密（v3）或读取（v2）目录表后，每条目录项按以下 4 个字段紧密拼接：

1. 文件名：以 `\x00` 结尾的 ASCII 路径（例如 `/config.yaml\x00`）。
2. Offset：int64 LE（8 B），该内部文件在 `asr_model.model` 内的绝对起始偏移。
3. Size：int64 LE（8 B），该内部文件的原始字节数。
4. Mtime：int64 LE（8 B），修改时间戳（`1.1.2` 打包值均为 `1`）。

## FLUTE v3 目录密钥派生

目录密钥仅由客户端常量根种子与文件头元数据本地算出，不依赖网络、账号或钥匙串。计算步骤如下：

1. 读取 32 字节根种子 `S`（保存在 [flute-v3-seed.bin](flute-v3-seed.bin)）：

   ```text
   00112233445566778899aabbccddeefffedcba98765432100123456789abcdef
   ```

2. 将 `S` 复制到 32 字节缓冲区 `M`。
3. 将包内 12 字节 `Nonce`（偏移 `21..32`）逐字节异或到 `M[0:12]`。
4. 将 8 字节小端 `HeaderSize`（偏移 `9..16`）逐字节异或到 `M[24:32]`。
5. 以 `key=M`、`nonce=Nonce`、`counter=0` 初始化 ChaCha20，加密 32 个 `0x00` 字节得到最终密钥 `K`。
6. 以 `key=K`、`nonce=Nonce`、`counter=1`（seek 64 字节）解密目录密文 `header[33:]`。

下表记录 `1.1.2` 两款模型的目录密钥派生与明文哈希实测值。

- 专业版 `1.5`（FLUTE v3）：
  - Nonce：`39a12d5e7dc541b5c5106c3f`
  - Header Size：`343`
  - 派生密钥 `K`：`b876b031394e176de4789c155f4059f92743b30f60e550a46a0d4b0c07113f6e`
  - 目录明文 SHA-256：`6481271d61f2aa15a2264fb909e10d560c48019abec71bcfb435a5139e9ee627`
- 通用版 `1.8`（FLUTE v2，无加密）：
  - 目录明文 SHA-256：`4870a7b6f419a32066fb06b3b0d8461bc0f0a32e205d3ac80739b9adfca24392`

真实及合成测试向量的独立验证记录见[密钥派生测试向量](key-derivation-vectors.json)。

## 正文混淆还原

FLUTE v2 和 v3 的所有内部文件正文使用同一还原公式，其中 `i` 是当前内部文件内的相对字节偏移（每个文件从 `0` 重新计数）：

```python
P[i] = C[i] ^ b"symphony"[i % 8] ^ (i & 255)
```

使用 [extract_model.py](extract_model.py) 可将 `asr_model.model` 按 4 MiB 分块流式还原并校验 SHA-256。执行命令见[复现容器校验与模型提取](../README.md#复现容器校验与模型提取)。

## 1.1.2 内部文件清单

两款模型的 `vad_v4.pth.pthlite`、`fbank.conf` 与 `cmvn.txt` 完全一致，差异仅在 `.packed` 权重与 `config.yaml` 配置。完整 64 位 SHA-256 见[专业版解包文件清单](extraction-report-pro.json)和[通用版解包文件清单](extraction-report-general.json)。

### 专业版 `1.5`（6 个文件，正文合计 1,487,023,474 B）

| 内部路径 | 大小 (B) | MD5 | SHA-256（前 12 位） | 说明 |
| :--- | ---: | :--- | :--- | :--- |
| `/config.yaml` | 9,622 | `0d4cef50f2a6460f072fa34d96707a60` | `5c062c1e6608` | 管道配置、VAD 参数、Prompt 模板与调度策略 |
| `/asr/feature_extractor/cmvn.txt` | 1,584 | `753b9da691401b5694be8d47942f721e` | `ff7a5df4fbf2` | 80 维声学特征 CMVN 均值与方差（与通用版相同） |
| `/asr/feature_extractor/fbank.conf` | 89 | `1decd7a0c7dc66febe0b68cabf0dde90` | `33447b195117` | 16 kHz、80 维 fbank 配置（与通用版相同） |
| `/asr/models/nonstream.packed` | 1,150,638,349 | `d7695a61ae081e4af308f332c0f6409b` | `2c0b532831ea` | 非流式高精度上下文引擎（含 `.mnn` 与 29 层解码器） |
| `/asr/models/stream.packed` | 335,218,766 | `6d9d4ad5f953a78b1841aadd9649b8c6` | `b9b85632a4fa` | 流式实时听写引擎（含 `.mnn` 与 12 层解码器） |
| `/vad/encoder/vad_v4.pth.pthlite` | 1,155,064 | `7da957917de54fe653bb5a2bb1fd713f` | `6ce875345309` | VAD 端点检测网络（与通用版相同） |

### 通用版 `1.8`（6 个文件，正文合计 463,454,925 B）

| 内部路径 | 大小 (B) | MD5 | SHA-256（前 12 位） | 说明 |
| :--- | ---: | :--- | :--- | :--- |
| `/config.yaml` | 10,300 | `2fed8577b91659563960167cf4031d1f` | `c3f4c0f0a96a` | 共享权重配置（`share_weight: true`）与 3 套 Prompt 模板 |
| `/asr/feature_extractor/cmvn.txt` | 1,584 | `753b9da691401b5694be8d47942f721e` | `ff7a5df4fbf2` | 与专业版相同 |
| `/asr/feature_extractor/fbank.conf` | 89 | `1decd7a0c7dc66febe0b68cabf0dde90` | `33447b195117` | 与专业版相同 |
| `/asr/models/no_stream.packed` | 280,716,560 | `24fad19d686c68c67a62ef97a1054bf1` | `ce1314c1fce1` | 非流式轻量上下文引擎（复用流式音频特征） |
| `/asr/models/stream.packed` | 181,571,328 | `9aee5616ddc31b5c19540c67ad7456c4` | `1bbd1dabaf66` | 流式实时听写引擎 |
| `/vad/encoder/vad_v4.pth.pthlite` | 1,155,064 | `7da957917de54fe653bb5a2bb1fd713f` | `6ce875345309` | 与专业版相同 |
