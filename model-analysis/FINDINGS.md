# 豆包输入法离线模型格式、密钥派生与验证分析

本文档汇总豆包输入法 macOS 版（`1.1.0` 与 `1.1.1`）离线语音识别模型的容器格式、密钥派生算法、混淆还原机制与多版本结构对比。

---

## 核心结论

1. **双模型分化与架构演进（1.1.1）**：
   * 1.1.0 仅提供单一主识别大模型（`acllm_main_model_mac` 1.8，约 825 MB，内含 20 个解离文件）。
   * 1.1.1 升级为双模型架构：**专业版**（`acllm_pro_model_mac` 1.5，1.48 GB）与 **通用版**（`acllm_general_model_mac` 1.8，463 MB）。
   * 两款新模型均将原本分散的 20 个权重文件重构聚合为 **6 个内部核心文件**（含打包的 `.packed` 引擎图）。
2. **容器与加密机制**：
   * **专业版（FLUTE v3）**：沿用确定性密钥派生算法，目录使用 ChaCha20 加密（Counter 1），密钥由固定种子、包内 12 字节 Nonce 和 Header Size 实时派生。
   * **通用版（FLUTE v2）**：降级为未加密明文目录，从偏移 21 处直接读取目录项，无需 ChaCha20 解密。
   * **正文混淆（统一）**：无论是 FLUTE v2 还是 v3，所有内部文件正文均统一使用基于相对字节位置的 `symphony` XOR 掩码混淆。
3. **验证与完整性**：
   * 专业版与通用版的全部 6 个内部文件均已通过流式解包与源包内容 100% 一致性校验。
   * 两个新模型的 VAD 语音活动检测权重（`vad_v4.pth.pthlite`）实现 **逐字节完全一致（SHA-256 完全相同）**。

---

## 多版本模型规格与容器对比

| 属性 | 1.1.1 专业版 (`acllm_pro_model_mac`) | 1.1.1 通用版 (`acllm_general_model_mac`) | 1.1.0 旧版主模型 (`acllm_main_model_mac`) |
| :--- | :--- | :--- | :--- |
| **模型版本** | `1.5` | `1.8` | `1.8` |
| **内部配置标签** | `LiteASRP_v1.2.0_7` | `LiteASRm_v1.0.1_5` | `LiteASRP_v1.1.2_6` |
| **源包大小** | 1,487,023,817 字节 (~1.48 GB) | 463,455,256 字节 (~463 MB) | 824,999,405 字节 (~825 MB) |
| **源包 MD5** | `4f19c90670291b502a4dd34b936e5f2f` | `a6846b0a91ac8a9579468e252c1da2e5` | `c31bdfbd138e9beac48e02672f98f1e8` |
| **容器格式** | `FLUTE v3` | `FLUTE v2` | `FLUTE v3` |
| **Header Size** | 343 字节 | 331 字节 | 1143 字节 |
| **内部文件数** | 6 个 | 6 个 | 20 个 |
| **目录加密** | ChaCha20（Counter 1） | **无加密（明文目录）** | ChaCha20（Counter 1） |
| **正文混淆** | `symphony` XOR | `symphony` XOR | `symphony` XOR |
| **权重特点** | 流式/非流式解耦，非流式支持 GPU | 流式/非流式共享权重，体积紧凑 | 20 个解离文件，CPU/NPU 混合 |
| **报告索引** | [verification-pro.json](verification-pro.json) | [verification-general.json](verification-general.json) | [verification.json](verification.json) |

---

## 容器布局规范

### 1. FLUTE v3 容器布局（专业版 1.5 及旧版 1.8）

| 文件偏移 (零起始) | 长度 (字节) | 含义与结构 |
| :--- | :--- | :--- |
| `0` - `4` | 5 | Magic 标识：`FLUTE`（ASCII） |
| `5` - `8` | 4 | 小端 uint32：格式主版本号 `3` |
| `9` - `16` | 8 | 小端 uint64：Header 头部总大小（专业版为 343，旧版为 1143） |
| `17` - `20` | 4 | 小端 uint32：内部文件计数（专业版为 6，旧版为 20） |
| `21` - `32` | 12 | 12 字节随机 Nonce，用于 ChaCha20 解密 |
| `33` - `HeaderSize - 1` | HeaderSize - 33 | ChaCha20 加密的目录表密文 |
| `HeaderSize` 起 | 剩余字节 | 各内部文件的 XOR 混淆正文（数据区紧随头部末尾） |

### 2. FLUTE v2 容器布局（通用版 1.8）

| 文件偏移 (零起始) | 长度 (字节) | 含义与结构 |
| :--- | :--- | :--- |
| `0` - `4` | 5 | Magic 标识：`FLUTE`（ASCII） |
| `5` - `8` | 4 | 小端 uint32：格式主版本号 `2` |
| `9` - `16` | 8 | 小端 uint64：Header 头部总大小（331 字节） |
| `17` - `20` | 4 | 小端 uint32：内部文件计数（6 个） |
| `21` - `HeaderSize - 1` | 310 | **未加密明文目录表**（无 Nonce，直接存放文件名与偏移元数据） |
| `331` 起 | 剩余字节 | 各内部文件的 XOR 混淆正文 |

### 3. 目录项序列化结构（解密/解析后）

每个目录项由以下四部分连续拼接而成：
1. **文件名**：以 `\x00`（NUL）结尾的 UTF-8/ASCII 字符串（如 `/config.yaml\x00`）。
2. **Offset**：小端 int64（8 字节），内部文件在整个源包中的绝对字节起始位置。
3. **Size**：小端 int64（8 字节），内部文件原始字节大小。
4. **Mtime**：小端 int64（8 字节），修改时间戳。

---

## 密钥派生算法（FLUTE v3）

FLUTE v3 目录使用确定性派生算法，密钥不直接硬编码在二进制中，也不依赖网络鉴权或用户环境：

### 1. 派生输入
* **固定根种子（Root Seed）**：内置于客户端算法库 `libPantherLite.dylib` / `libflute.dylib` 中的 32 字节常量：
  ```text
  00112233445566778899aabbccddeefffedcba98765432100123456789abcdef
  ```
  （保存于仓库 [model-seed.bin](model-seed.bin)）
* **包内 12 字节 Nonce**：读取源包 `[21:33]`。
* **Header Size**：读取源包 `[9:17]` 的 64 位无符号小端整数。

### 2. 派生步骤
1. 复制 32 字节根种子得到初始工作缓冲区 `M`。
2. 将 12 字节 Nonce 逐字节异或到 `M[0:12]`。
3. 将 Header Size 的小端 8 字节序列逐字节异或到 `M[24:32]`。
4. 使用变换后的 `M` 作为初始密钥、该 Nonce 作为 IV、初始计数器 Counter 0 初始化 ChaCha20 生成器。
5. 生成密钥流并截取前 32 字节，得到最终解密密钥 `K`。
6. 使用 `K` 与相同的 Nonce，**初始化计数器设置为 1（即 seek 64 字节）** 解密目录密文 `[33:HeaderSize]`。

### 3. 各模型派生参数实测值

| 模型 | Nonce (12B hex) | Header Size | 派生最终密钥 `K` (32B hex) | 目录明文 SHA-256 |
| :--- | :--- | :--- | :--- | :--- |
| **专业版 1.5** | `39a12d5e7dc541b5c5106c3f` | 343 | `b876b031394e176de4789c155f4059f92743b30f60e550a46a0d4b0c07113f6e` | `6481271d61f2aa15a2264fb909e10d560c48019abec71bcfb435a5139e9ee627` |
| **旧版主模型 1.8** | `45189cedd063abfc8f2ab7cc` | 1143 | `8ddd3bb3a2606cfa71d1cb9a63da0290627c238aef49dbaaf9ae0d7cf5fe2238` | `07e0a4590ced10d7fc0b094ea8ca948f1df61fb4e9e80f218373b5f67985b991` |

> [!NOTE]
> 通用版 1.8 采用 FLUTE v2，目录头明文存储，目录明文 SHA-256 为 `4870a7b6f419a32066fb06b3b0d8461bc0f0a32e205d3ac80739b9adfca24392`。

---

## 正文混淆还原算法（Payload Deobfuscation）

所有模型内部文件正文的混淆算法保持严格一致：

```python
P[i] = C[i] ^ b"symphony"[i % 8] ^ (i & 255)
```

* `C[i]` 为源包中内部文件的第 `i` 个密文字节。
* `P[i]` 为还原后的明文字节。
* `i` 是 **当前内部文件内的相对偏移量（从 0 开始递增）**。每个内部文件切换时 `i` 归零重置。
* 脚本工具 [extract_model.py](extract_model.py) 采用 4 MiB 块流式计算，避免全量读入内存。

---

## 1.1.1 内部文件清单与组件对比

### 1. 专业版 1.5（合计 6 个文件，1,487,023,474 字节）

| 内部文件路径 | 文件大小 (字节) | MD5 | SHA-256 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `/config.yaml` | 9,622 | `0d4cef50f2a6460f072fa34d96707a60` | `5c062c1e6608...` | 引擎管道配置与模型调度入口 |
| `/asr/feature_extractor/cmvn.txt` | 1,584 | `753b9da691401b5694be8d47942f721e` | `ff7a5df4fbf2...` | 80 维声学特征均值与方差归一化矩阵 |
| `/asr/feature_extractor/fbank.conf` | 89 | `1decd7a0c7dc66febe0b68cabf0dde90` | `33447b195117...` | 16 kHz 采样率、80 通道 Mel-filterbank 配置 |
| `/asr/models/nonstream.packed` | 1,150,638,349 | `d7695a61ae081e4af308f332c0f6409b` | `2c0b532831ea...` | 非流式高精度上下文识别引擎（解耦独立权重） |
| `/asr/models/stream.packed` | 335,218,766 | `6d9d4ad5f953a78b1841aadd9649b8c6` | `b9b85632a4fa...` | 低延迟流式实时听写引擎 |
| `/vad/encoder/vad_v4.pth.pthlite` | 1,155,064 | `7da957917de54fe653bb5a2bb1fd713f` | `6ce875345309...` | VAD 语音静音切分神经网络模型 |

### 2. 通用版 1.8（合计 6 个文件，463,454,925 字节）

| 内部文件路径 | 文件大小 (字节) | MD5 | SHA-256 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| `/config.yaml` | 10,300 | `2fed8577b91659563960167cf4031d1f` | `c3f4c0f0a96a...` | 共享权重调度配置（声明 `share_weight: true`） |
| `/asr/feature_extractor/cmvn.txt` | 1,584 | `753b9da691401b5694be8d47942f721e` | `ff7a5df4fbf2...` | 与专业版完全相同（SHA-256 一致） |
| `/asr/feature_extractor/fbank.conf` | 89 | `1decd7a0c7dc66febe0b68cabf0dde90` | `33447b195117...` | 与专业版完全相同（SHA-256 一致） |
| `/asr/models/no_stream.packed` | 280,716,560 | `24fad19d686c68c67a62ef97a1054bf1` | `ce1314c1fce1...` | 非流式轻量上下文修正引擎 |
| `/asr/models/stream.packed` | 181,571,328 | `9aee5616ddc31b5c19540c67ad7456c4` | `1bbd1dabaf66...` | 流式实时听写引擎 |
| `/vad/encoder/vad_v4.pth.pthlite` | 1,155,064 | `7da957917de54fe653bb5a2bb1fd713f` | `6ce875345309...` | 与专业版完全相同（SHA-256 一致） |

> [!IMPORTANT]
> **VAD 模型逐字节跨版本一致性**：
> 专业版与通用版内的 `vad_v4.pth.pthlite` 具有完全一致的大小（1,155,064 字节）以及完全一致的 SHA-256：
> `6ce875345309f4dc3488b39fd311c662e48eea2dc9e4eff4a001e4b2d10ccb07`。
> 这证明豆包输入法跨模型复用了同一套离线语音端点检测（Voice Activity Detection）网络。

---

## 验证与复现工具用法

更新后的工具已原生支持自适应检测激活模型、FLUTE v2/v3 双协议及指定模型路径：

### 1. 验证模型目录及派生密钥

```sh
# 验证当前正在激活的模型（从 offline_model_active_layout.json 自动检测）
python3 model-analysis/verify_directory.py

# 显式验证专业版模型
python3 model-analysis/verify_directory.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model"

# 显式验证通用版模型
python3 model-analysis/verify_directory.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model"
```

### 2. 流式提取全部内部文件

```sh
# 提取专业版文件到本地目录
python3 model-analysis/extract_model.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model" \
  .local-data/extracted-pro

# 提取通用版文件到本地目录
python3 model-analysis/extract_model.py \
  --model "$HOME/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model" \
  .local-data/extracted-general
```
