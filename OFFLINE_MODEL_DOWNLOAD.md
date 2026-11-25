# 1.1.2 离线模型直链与 LuLu 防火墙配置

本文档提供豆包输入法 macOS `1.1.2` 离线模型的官方 CDN 下载地址、LuLu 防火墙配置步骤和客户端下载调度参数。

> `1.1.0` 旧版主模型（`acllm_main_model_mac` 1.8，825 MB）的直链与路径见 Git Tag `macos_1.1.0`。
>
> 以下接口参数与 CDN 地址只用于个人本地离线部署和网络审计，不要用于自动化批量抓取、镜像分发或商业调用。

## 官方 CDN 直链参考（1.1.2）

官方模型托管在 `byteeffecttos.com` CDN，URI 路径使用文件 32 位 MD5 命名。

| 模型 | 版本与配置标签 | 大小 | MD5 | 本地安装路径（相对 `~/Library/Application Support/DoubaoIme/`） |
| :--- | :--- | ---: | :--- | :--- |
| 专业版 ASR（`acllm_pro_model_mac`） | `1.5` · `LiteASRP_v1.2.0_7` | 1.48 GB | `4f19c90670291b502a4dd34b936e5f2f` | `ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model` |
| 通用版 ASR（`acllm_general_model_mac`） | `1.8` · `LiteASRm_v1.0.1_5` | 463 MB | `a6846b0a91ac8a9579468e252c1da2e5` | `ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model` |
| 上下文辅助（`acllm_context_model_mac`） | `1.1` | 108 MB | `32c387bc13445d1b020077c168c0d2c9` | `ContextAuxModel/versions/1_1/context_aux_model/`（ZIP 解压目录，包含 `cppjieba_dict`、`ner_model` 和 `pinyin_dict`） |

将下面模板中的 `<MD5>` 替换为上表对应值，即可直接访问模型文件：

- 主节点：`https://lf26-effect-aweme.byteeffecttos.com/obj/ies.fe.effect/<MD5>?module=model`
- 备用节点：`https://n98-lf-effect-aweme-302-ncdn.byteeffecttos.com/obj/ies.fe.effect/<MD5>?module=model`

## 配置 LuLu 防火墙步骤

按下列步骤配置后，你可以在阻断遥测和云端语音接口的同时只放行离线模型下载。以下规则作用于两个可执行文件：

- `/Library/Input Methods/DoubaoIme.app/Contents/MacOS/DoubaoIme`
- `/Library/Input Methods/DoubaoIme.app/Contents/Applications/DoubaoImeSettings.app/Contents/MacOS/DoubaoImeSettings`

1. 如果你要从零下载或更新离线模型，先为上述两个进程添加以下两条 **Allow** 规则。

   | 主机 | 端口 | 协议 | 用途 |
   | :--- | :--- | :--- | :--- |
   | `effect.snssdk.com` | `443` | TCP | 查询离线模型版本和 CDN 下载地址 |
   | `*.byteeffecttos.com` | `443` | TCP | 下载离线模型和辅助词典 |

   > 阻断私有 HTTPDNS（例如 `dig.zjurl.cn`）后，TTNet 会自动回退到 macOS 系统 DNS，这两条规则即可完成下载。

2. 保持其余所有外联域名为 **Block**，重点包括下表列出的主机。

   | 域名 | 用途 |
   | :--- | :--- |
| `pc-mon.zijieapi.com` 与 `*.zijieapi.com` | 行为与性能打点（`OimeReport` 击键记录 `recordKeyboardCommitEvent` 与体验改进数据 `reportUserExpImprovementData`） |
   | `frontier*-audio-ime-*.doubao.com` | 实时云端语音转文字通道（WebSocket 和 QUIC 音频流） |
   | `speech.bytedance.com` | 云端语音识别接口 |
   | `api-normal.doubao.com` | 账号鉴权与心跳（`/passport/token/beat/v2/`） |
   | `ime.doubao.com` 与 `ime.oceancloudapi.com` | 云端词库同步与配置下发 |

3. 当本地目录已存在 `ASRModel/versions/.../asr_model.model` 和 `ContextAuxModel/versions/1_1/context_aux_model/` 后，在 LuLu 中将 `DoubaoIme` 和 `DoubaoImeSettings` 全部设为 **Block**。此后无需保留任何放行规则，本地离线语音转写和键盘输入仍正常工作。

## 客户端下载调度参考

模型下载逻辑位于 `OimeOfflineModel` 命名空间，调用链路如下：

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

请求 `GET https://effect.snssdk.com/model/api/arithmetics` 时，客户端携带下列查询参数：

- `sdk_version`：内置算法 SDK 版本，当前为 `2.9.115`（缺失时服务端返回 HTTP 400）。
- `device_platform`：固定值 `mac`。
- `aid`：应用 ID（例如 `843934` 或 `685343`）。

服务端在 `data.arithmetics` 中按分组返回模型条目，包含 `name`、加密名称字段 `name_sec`（客户端调用 `resolvedModelName(from:context:)` 解密）、`version`、`uri`（MD5）以及 `url_list` 和 `zip_url_list`。安装完成后，客户端写入两份本地状态文件：

- `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_manifest.json`（Schema v2，已安装模型清单）
- `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_active_layout.json`（Schema v1，当前激活模型，例如 `selectedMainModelName: acllm_pro_model_mac`）
