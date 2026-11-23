# 1.1.1 离线模型官方直链与 LuLu 防火墙配置

本文档提供豆包输入法 macOS `1.1.1` 离线模型的官方 CDN 下载直链、客户端下载调度机制，以及在阻断遥测和云端语音的前提下只放行离线模型下载的 LuLu 防火墙最小规则。

> 1.1.0 旧版主模型（`acllm_main_model_mac` 1.8，825 MB）的直链与路径见 Git Tag `macos_1.1.0`。

## 官方 CDN 直链速查（1.1.1）

所有模型文件托管在 `byteeffecttos.com` CDN，URI 路径即文件 32 位 MD5：

| 模型 | 版本 / 标签 | 大小 | MD5 | 本地安装路径（相对 `~/Library/Application Support/DoubaoIme/`） |
| :--- | :--- | ---: | :--- | :--- |
| **专业版 ASR** (`acllm_pro_model_mac`) | `1.5` / `LiteASRP_v1.2.0_7` | 1.48 GB | `4f19c90670291b502a4dd34b936e5f2f` | `ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model` |
| **通用版 ASR** (`acllm_general_model_mac`) | `1.8` / `LiteASRm_v1.0.1_5` | 463 MB | `a6846b0a91ac8a9579468e252c1da2e5` | `ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model` |
| **上下文辅助** (`acllm_context_model_mac`) | `1.1` | 108 MB | `32c387bc13445d1b020077c168c0d2c9` | `ContextAuxModel/versions/1_1/context_aux_model/`（ZIP 解压，含 `cppjieba_dict` / `ner_model` / `pinyin_dict`） |

**直链地址**（将 `<MD5>` 替换为上表对应值）：
- 主节点：`https://lf26-effect-aweme.byteeffecttos.com/obj/ies.fe.effect/<MD5>?module=model`
- 备用节点：`https://n98-lf-effect-aweme-302-ncdn.byteeffecttos.com/obj/ies.fe.effect/<MD5>?module=model`

---

## LuLu 防火墙最小放行规则

**适用进程**：
- `/Library/Input Methods/DoubaoIme.app/Contents/MacOS/DoubaoIme`
- `/Library/Input Methods/DoubaoIme.app/Contents/Applications/DoubaoImeSettings.app/Contents/MacOS/DoubaoImeSettings`

### 仅需放行（Allow）

| 主机 | 端口 | 协议 | 用途 |
| :--- | :--- | :--- | :--- |
| `effect.snssdk.com` | `443` | TCP | 查询离线模型版本与 CDN 下载地址 |
| `*.byteeffecttos.com` | `443` | TCP | 下载离线模型与辅助词典 |

> 阻断私有 HTTPDNS（如 `dig.zjurl.cn`）后，TTNet 会自动回退到 macOS 系统 DNS，上述两条规则即可正常下载。

### 建议阻断（Block）

其余外联全部默认 Block，重点包括：

| 域名 | 用途 |
| :--- | :--- |
| `pc-mon.zijieapi.com` / `*.zijieapi.com` | 行为与性能打点（`OimeReport` 击键提交记录 `reportKeyboardCommitEvent`、体验改进数据 `reportUserExpImprovementData`） |
| `frontier*-audio-ime-*.doubao.com` | 实时云端语音转文字通道（WebSocket / QUIC 音频流） |
| `speech.bytedance.com` | 云端语音识别接口 |
| `api-normal.doubao.com` | 账号鉴权与心跳（`/passport/token/beat/v2/`） |
| `ime.doubao.com` / `ime.oceancloudapi.com` | 云端词库同步与配置下发 |

### 完全断网离线运行

模型下载完成后，**无需保留任何放行规则**：确认本地已有 `ASRModel/versions/.../asr_model.model` 和 `ContextAuxModel/versions/1_1/context_aux_model/`，在 LuLu 中将 `DoubaoIme` 与 `DoubaoImeSettings` 全部设为 Block，本地离线语音转写和键盘输入均正常工作。

---

## 下载调度协议（静态逆向）

模型下载模块位于 `OimeOfflineModel` 命名空间，调用链如下：

```text
DoubaoImeSettings / IPC
  └─> startOfflineModelDownloadNotification
        └─> ASROfflineModelManager
              ├─> ASROfflineModelMetaInfoService
              │     └─> GET https://effect.snssdk.com/model/api/arithmetics
              ├─> populateFileSizeByHEAD (HEAD *.byteeffecttos.com 获取 Content-Length)
              ├─> libTTNetDownloaderCrossPlatform.dylib (分块写入 OfflineModelDownloads/)
              └─> MD5 校验与安装 -> ASRModel/versions/ & ContextAuxModel/versions/
```

**元数据接口参数**（`GET https://effect.snssdk.com/model/api/arithmetics`）：
- `sdk_version`：内置算法 SDK 版本（`2.9.115`，缺失返回 400）
- `device_platform`：`mac`
- `aid`：应用 ID（如 `843934` / `685343`）

服务端在 `data.arithmetics` 中返回每个模型的 `name`、`version`、`uri`（MD5）和 `url_list` / `zip_url_list`。安装完成后客户端写入两份状态文件：
- `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_manifest.json`（Schema v2，已安装清单）
- `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_active_layout.json`（Schema v1，当前激活模型，如 `selectedMainModelName: acllm_pro_model_mac`）
