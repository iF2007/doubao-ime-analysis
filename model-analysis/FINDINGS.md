# 主模型 1.8 的格式、密钥和验证结果

已对豆包输入法 1.1.0 的 `acllm_main_model_mac` 1.8 验证目录和全部 20 个内部文件。关键结果如下：

- 目录密钥由固定种子、源包 nonce 和 header size 确定性派生，最终密钥不是直接写死的常量。
- 目录使用 ChaCha20，内部文件正文使用按相对字节位置计算的 XOR 混淆。
- 全部解出文件与源包解码内容一致，包内 MD5 清单仍有三项差异。

| 源包属性 | 值 |
| --- | --- |
| 大小 | 824999405 字节，约 825 MB |
| MD5 | `c31bdfbd138e9beac48e02672f98f1e8` |

阅读顺序为 [文件布局](#文件布局)、[密钥派生](#密钥派生)、[正文恢复](#正文恢复)、[验证依据](#验证依据) 和 [MD5 清单差异](#包内-md5-清单差异)。复现命令见 [README](../README.md#复现目录验证与解包)。

## 文件布局

下表使用零起始偏移，区间包含两端。

| 文件偏移 | 内容 |
| --- | --- |
| 0 至 4 | `FLUTE` 标识 |
| 5 至 8 | 小端 uint32，格式版本 3 |
| 9 至 16 | 小端 uint64，header size 1143 |
| 17 至 20 | 小端 uint32，文件数 20 |
| 21 至 32 | 12 字节 nonce，Python 切片 `[21:33]` |
| 33 至 1142 | 1110 字节 ChaCha20 目录密文 |
| 1143 起 | 各内部文件的 XOR 混淆正文 |

每个目录项包含：

1. NUL 结尾的文件名。
2. 小端 int64 的绝对 offset。
3. 小端 int64 的 size。
4. 小端 int64 的 mtime。

全部文件连续覆盖数据区，最后一个文件结束于源包末尾。目录明文 SHA-256 为 `07e0a4590ced10d7fc0b094ea8ca948f1df61fb4e9e80f218373b5f67985b991`。

## 密钥派生

固定种子为以下 32 个字节，以十六进制表示：

```text
00112233445566778899aabbccddeefffedcba98765432100123456789abcdef
```

本次派生使用的包内元数据如下：

| 输入 | 值 |
| --- | --- |
| nonce | `45189cedd063abfc8f2ab7cc`，12 字节 |
| header size | 1143 |
| header size 的小端 8 字节 | `7704000000000000` |

派生和目录解密按以下顺序进行：

1. 复制种子得到 32 字节缓冲区 `M`。
2. 将 nonce XOR 到 `M[0:12]`。
3. 将 header size 的小端 8 字节 XOR 到 `M[24:32]`。
4. 使用 `M`、该 nonce 和 counter 0 生成 ChaCha20 密钥流。
5. 取密钥流前 32 字节得到目录密钥 `K`。
6. 使用 `K`、同一个 nonce 和 counter 1 解密目录密文。

最终目录密钥为：

```text
8ddd3bb3a2606cfa71d1cb9a63da0290627c238aef49dbaaf9ae0d7cf5fe2238
```

[verify_directory.py](verify_directory.py) 的 `derive_key` 独立实现该公式。不同 nonce 或 header size 会产生不同密钥。

| 产物 | 内容 |
| --- | --- |
| [model-seed.bin](model-seed.bin) | 32 字节固定种子 |
| [directory-key.bin](directory-key.bin) | 32 字节派生目录密钥 |

两个 `.bin` 文件均保存原始字节，不是十六进制文本。

## 正文恢复

正文公式为：

```python
P[i] = C[i] ^ b"symphony"[i % 8] ^ (i & 255)
```

字节位置与处理范围如下：

- `i` 是每个内部文件的相对字节位置。
- `i` 在文件之间重置为 0，在读取分块之间连续累加。
- 目录头使用 ChaCha20，正文使用 XOR 混淆，因此源包在目录区以外也经过处理。

[extract_model.py](extract_model.py) 以 4 MiB 分块恢复文件，再核对输出大小和 SHA-256，并检查源包 MD5。

| 使用方式 | 行为 |
| --- | --- |
| 提取 | 输出路径需为不存在的新目录，工具采用排他创建 |
| `--verify-only` | 核对已存在的完整解包目录并更新其中的报告 |

两个工具的命令见 [README](../README.md#复现目录验证与解包)。

## 验证依据

| 验证 | 结果 | 记录 |
| --- | --- | --- |
| 标准 ChaCha20 解密真实目录 | counter 1 产生合法目录，counter 0 对照失败 | [verification.json](verification.json) |
| 目录逐字节比较 | 全部 20 个目录项与原指令模拟结果一致 | [emulated-directory.bin](emulated-directory.bin) |
| 原分析的派生检查 | 真实元数据和合成元数据案例均与模拟 cipher key 一致 | [generation-verification.json](generation-verification.json) |

合成案例使用 nonce `000102030405060708090a0b`、header size 1144，并改变保护校验随机挑战，派生结果仍与当时模拟的 cipher key 一致。

> [!NOTE]
> 生成验证记录保存原分析结果。公开仓库可独立验证密码算法与真实源包，但不包含保护虚拟机和原指令模拟的重放材料。

原应用的保护回调还处理签名、进程状态及随机挑战。这些保护校验材料与目录密钥不同。已验证的派生公式不读取账号、钥匙串或服务器。原应用指纹和分析环境见 [environment.json](../environment.json)。原安装文件及源模型保持只读。

## 模型组件大小

全部 20 个文件正文合计 824998262 字节。以下九项为权重文件，仓库不提供其内容。

| 内部文件 | 字节数 |
| --- | --- |
| `asr/models/llm_decoder_embeding_logit.pthlite` | 33089600 |
| `asr/models/encoder.opt.stream.pthlite` | 208533328 |
| `asr/models/llm_decoder.pthlite` | 76644680 |
| `asr/models/non_s_draft.pthlite` | 32627552 |
| `asr/models/non_s_encoder.opt.stream.pthlite` | 206124592 |
| `asr/models/non_s_llm_embedding_logit.pthlite` | 33025424 |
| `asr/models/llm_decoder_embeding_wpe.pthlite` | 2106368 |
| `asr/models/non_s_llm_decoder.pthlite` | 230098144 |
| `vad/encoder/vad_v4.pth.pthlite` | 1155400 |

编码器、解码器图和配置的结构判断见 [模型对比](../comparison/COMPARISON.md)。文件大小包含量化权重、图结构和其他序列化信息，不能直接换算精确参数量。

## 包内 MD5 清单差异

[提取报告](extraction-report.json) 记录全部 20 个文件与源包解码内容一致。包内八项 MD5 清单中有五项匹配，以下三项不匹配：

| 内部文件 | 清单 MD5 | 解出内容 MD5 |
| --- | --- | --- |
| `asr/models/non_s_encoder.opt.stream.pthlite` | `453cd5e0eee1c1350e5dce8f540b90a1` | `f838d414b5f3f465fb3ed165cf3f5dc7` |
| `asr/models/non_s_llm_decoder.pthlite` | `ab0c38ed97f55dfdee20c3f64a829a79` | `083d4717b9648369083c42cf72cb3a15` |
| `asr/models/non_s_llm_embedding_logit.pthlite` | `18e804822a3fe5767e71c21da898e68c` | `9beee631e16a50672e62c69bbb71e55a` |

> [!IMPORTANT]
> 差异原因未明。源包和落盘文件的一致性不能证明清单有效，也不能据此认定清单过期、文件损坏或派生算法错误。工具记录这些差异并正常结束，成功退出只表示提取及落盘核对通过。

## 未验证事项

本次结论不覆盖以下事项：

- 上下文辅助模型 1.1 或其他输入法版本。
- nonce 在打包端的生成方式。
- 精确参数量、训练来源或识别性能。
