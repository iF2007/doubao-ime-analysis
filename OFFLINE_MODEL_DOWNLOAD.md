# 豆包输入法离线模型下载地址与 LuLu 防火墙放行策略

本文档记录豆包输入法 macOS 版离线语音识别（ASR）模型的官方下载直链、调度接口机制、分发流程与 LuLu 防火墙最小放行配置方案。

---

## 针对版本与分析环境

| 项目 | 属性 / 值 |
| --- | --- |
| **目标应用** | 豆包输入法 macOS 版（`DoubaoIme.app`） |
| **应用版本** | `1.1.1`（Build `1`，Wave Build Version `1.1.1.3`，版本号 `1010103`）<br>*注：分析结论与模型资源同样向下兼容 `1.1.0`（Build `1`）* |
| **主程序路径** | `/Library/Input Methods/DoubaoIme.app/Contents/MacOS/DoubaoIme` |
| **主程序 SHA-256** | `8544564ffffae4abfe64df721a71b971408fb4a124512138d040c992456435b3` |
| **设置程序路径** | `/Library/Input Methods/DoubaoIme.app/Contents/Applications/DoubaoImeSettings.app/Contents/MacOS/DoubaoImeSettings` |
| **离线识别模型（专业版）** | `acllm_pro_model_mac` `1.5`（1,487,023,817 字节） |
| **离线识别模型（通用版）** | `acllm_general_model_mac` `1.8`（463,455,256 字节） |
| **上下文辅助模型** | `acllm_context_model_mac` `1.1`（108,300,553 字节） |
| **旧版单一大模型（1.1.0）** | `acllm_main_model_mac` `1.8`（824,999,405 字节） |
| **本地数据目录** | `~/Library/Application Support/DoubaoIme/` |

---

## 离线模型官方 CDN 直链与文件信息

在豆包输入法 `1.1.1` 中，离线语音引擎由原先的单一大模型拆分为 **专业版** 与 **通用版** 两种规格，搭配 **上下文辅助与分词模型**。实体文件托管在字节跳动的算法资源对象存储 CDN（`byteeffecttos.com`）。

### 1. 专业版离线识别大模型 (`acllm_pro_model_mac`)

* **模型版本**：`1.5`
* **配置标签**：`LiteASRP_v1.2.0_7`
* **容器格式**：FLUTE v3（ChaCha20 加密目录头 + 6 内部文件 + 独立权重）
* **目标文件名**：`asr_model.model`
* **本地激活路径**：`~/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model`
* **文件大小**：`1,487,023,817` 字节（约 1.48 GB）
* **MD5 / ETag**：`4f19c90670291b502a4dd34b936e5f2f`
* **官方 CDN 下载直链**：
  * 主节点：`https://lf26-effect-aweme.byteeffecttos.com/obj/ies.fe.effect/4f19c90670291b502a4dd34b936e5f2f?module=model`
  * 备用节点：`https://n98-lf-effect-aweme-302-ncdn.byteeffecttos.com/obj/ies.fe.effect/4f19c90670291b502a4dd34b936e5f2f?module=model`

### 2. 通用版离线识别模型 (`acllm_general_model_mac`)

* **模型版本**：`1.8`
* **配置标签**：`LiteASRm_v1.0.1_5`
* **容器格式**：FLUTE v2（明文目录头 + 6 内部文件 + 流式/非流式共享权重）
* **目标文件名**：`asr_model.model`
* **本地激活路径**：`~/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model`
* **文件大小**：`463,455,256` 字节（约 463 MB）
* **MD5 / ETag**：`a6846b0a91ac8a9579468e252c1da2e5`
* **官方 CDN 下载直链**：
  * 主节点：`https://lf26-effect-aweme.byteeffecttos.com/obj/ies.fe.effect/a6846b0a91ac8a9579468e252c1da2e5?module=model`
  * 备用节点：`https://n98-lf-effect-aweme-302-ncdn.byteeffecttos.com/obj/ies.fe.effect/a6846b0a91ac8a9579468e252c1da2e5?module=model`

### 3. 上下文辅助与词典模型 (`acllm_context_model_mac`)

* **模型版本**：`1.1`
* **目标文件名**：`context_aux_model.zip`（本地解压为 `context_aux_model` 目录，含 `cppjieba_dict`、`ner_model`、`pinyin_dict`）
* **本地激活路径**：`~/Library/Application Support/DoubaoIme/ContextAuxModel/versions/1_1/context_aux_model/`
* **文件大小**：`108,300,553` 字节（约 108 MB）
* **MD5 / ETag**：`32c387bc13445d1b020077c168c0d2c9`
* **官方 CDN 下载直链**：
  * 主节点：`https://lf26-effect-aweme.byteeffecttos.com/obj/ies.fe.effect/32c387bc13445d1b020077c168c0d2c9?module=model`
  * 备用节点：`https://n98-lf-effect-aweme-302-ncdn.byteeffecttos.com/obj/ies.fe.effect/32c387bc13445d1b020077c168c0d2c9?module=model`

### 4. 历史 1.1.0 版主识别大模型 (`acllm_main_model_mac`)

* **模型版本**：`1.8`
* **配置标签**：`LiteASRP_v1.1.2_6`
* **容器格式**：FLUTE v3（ChaCha20 加密目录头 + 20 个解离文件）
* **目标文件名**：`asr_model.model`
* **本地激活路径**：`~/Library/Application Support/DoubaoIme/ASRModel/versions/1_8/asr_model.model`
* **文件大小**：`824,999,405` 字节（约 825 MB）
* **MD5 / ETag**：`c31bdfbd138e9beac48e02672f98f1e8`
* **官方 CDN 下载直链**：
  * 主节点：`https://lf26-effect-aweme.byteeffecttos.com/obj/ies.fe.effect/c31bdfbd138e9beac48e02672f98f1e8?module=model`
  * 备用节点：`https://n98-lf-effect-aweme-302-ncdn.byteeffecttos.com/obj/ies.fe.effect/c31bdfbd138e9beac48e02672f98f1e8?module=model`

---

## 模型调度与下载协议逆向分析

通过静态与符号逆向分析，模型管理模块实现于 `OimeOfflineModel` 命名空间内，由以下核心链路驱动：

```text
DoubaoImeSettings / IPC 
    └──> startOfflineModelDownloadNotification
             └──> ASROfflineModelManager
                      ├──> ASROfflineModelMetaInfoService (查询接口)
                      │        └──> https://effect.snssdk.com/model/api/arithmetics
                      ├──> HEAD 请求 (获取 Content-Length 并预检)
                      │        └──> *.byteeffecttos.com
                      ├──> libTTNetDownloaderCrossPlatform.dylib (分块下载)
                      │        └──> ~/Library/Application Support/DoubaoIme/OfflineModelDownloads/
                      └──> MD5 校验与解压安装
                               └──> ASRModel/versions/ & ContextAuxModel/versions/
```

### 1. 模型元数据索引接口
* **请求端点**：`https://effect.snssdk.com/model/api/arithmetics`
* **请求方式**：HTTPS GET
* **必需参数**：
  * `sdk_version`：客户端内置算法 SDK 版本（当前为 `2.9.115`，缺失将返回 400 错误）
  * `device_platform`：`mac`
  * `aid`：应用标识（如 `843934` 或 `685343`）
* **接口行为**：
  服务端在 `data.arithmetics` 中下发指定模型的元数据列表，其中对象字段包含：
  * `name`：模型逻辑名（如 `acllm_pro_model_mac` / `acllm_general_model_mac` / `acllm_main_model_mac`）
  * `version`：版本号（如 `1.5` / `1.8`）
  * `uri`：即模型文件的 32 位 MD5 字符串
  * `url_list` / `zip_url_list`：对应的 `byteeffecttos.com` CDN 下载直链

### 2. 下载器执行机制
* 输入法主程序通过 `populateFileSizeByHEAD` 预先向 CDN 地址发送 `HEAD` 请求获取实际 `Content-Length`。
* 之后调度 `TTNet` 下载器写入 `OfflineModelDownloads/` 临时目录。
* 下载完成后校验哈希是否与 `sourceMD5` 严格一致。
* 在 1.1.1 中，目录组织升级为包含 MD5 散列的路径：`ASRModel/versions/<logicalName>/<version>_<md5>/asr_model.model`。
* 最终生成如下两个配置管理文件：
  * `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_manifest.json`（Schema v2）
  * `~/Library/Application Support/DoubaoIme/ASRContext/offline_model_active_layout.json`（Schema v1，记录当前激活模型，例如 `selectedMainModelName: acllm_pro_model_mac`）

---

## LuLu 防火墙规则配置建议

为防止输入法在后台上传击键统计、体验改进数据或实时云端语音，同时允许离线模型下载与更新，请配置 LuLu 防火墙规则。

### 1. 规则适用的进程路径

* `/Library/Input Methods/DoubaoIme.app/Contents/MacOS/DoubaoIme`
* `/Library/Input Methods/DoubaoIme.app/Contents/Applications/DoubaoImeSettings.app/Contents/MacOS/DoubaoImeSettings`

### 2. 仅允许放行名单（Allow Rules）

| 远程主机 (Endpoint / Host) | 端口 (Port) | 协议 (Protocol) | 作用说明 |
| :--- | :--- | :--- | :--- |
| `effect.snssdk.com` | `443` | TCP | 离线模型版本与下载直链元数据调度接口 |
| `*.byteeffecttos.com` | `443` | TCP | 离线模型本体与词典压缩包 CDN 资源下载 |

> [!NOTE]
> TTNet 即使被阻断了私有 HTTPDNS（如 `dig.zjurl.cn`），也会自动退避至 macOS 系统的标准本地 DNS 解析器，因此上述两条白名单规则足以完成模型的正常拉取。

### 3. 必须阻断名单（Block Rules）

除了上述两个明确与离线模型相关的域名外，其余所有外联建议保持 **Block**，特别是以下隐私敏感端点：

| 阻断域名 | 敏感行为说明 |
| :--- | :--- |
| `pc-mon.zijieapi.com` / `*.zijieapi.com` | 性能与行为打点收集（包含模块 `OimeReport` 的击键提交记录 `reportKeyboardCommitEvent`、用户体验改进数据 `reportUserExpImprovementData`） |
| `frontier*-audio-ime-*.doubao.com` | 实时云端语音转文字（WebSocket / QUIC 音频流传输通道） |
| `speech.bytedance.com` | 字节跳动云端语音识别中台接口 |
| `api-normal.doubao.com` | 账号鉴权与用户态心跳（`/passport/token/beat/v2/`） |
| `ime.doubao.com` / `ime.oceancloudapi.com` | 云端词库同步与通用配置下发 |

---

## 终极隐私方案：完全断网离线运行

若本地已下载好离线模型，**甚至无需对任何域名放行**：

1. 确认本地存在模型文件：
   * 专业版：`~/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_pro_model_mac/1_5_4f19c90670291b502a4dd34b936e5f2f/asr_model.model`
   * 或通用版：`~/Library/Application Support/DoubaoIme/ASRModel/versions/acllm_general_model_mac/1_8_a6846b0a91ac8a9579468e252c1da2e5/asr_model.model`
   * 辅助词典：`~/Library/Application Support/DoubaoIme/ContextAuxModel/versions/1_1/context_aux_model/`
2. 在 LuLu 防火墙中将 `DoubaoIme` 以及 `DoubaoImeSettings` 的 **所有网络访问权限均设置为 Block**。
3. 输入法本地 ASR 引擎（基于 `Flute` 框架）在无网状态下依然能够正常进行高精度语音转写与键盘输入，实现 100% 物理级隐私隔离。
