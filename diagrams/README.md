# 离线语音模型架构图

| 文件 | 说明 |
| :--- | :--- |
| [doubao-asr-architecture.png](doubao-asr-architecture.png) | README 展示的 1.1.1 架构图（5720 × 1516） |
| [doubao-asr-architecture.dot](doubao-asr-architecture.dot) | 可编辑的 Graphviz 源码 |

## 图例

- **颜色**：蓝色为流式识别路径（`stream.packed`），紫色为非流式上下文路径（`nonstream.packed` / `no_stream.packed`），黄色为 1.1.1 新增的尾部静音快检（`TailVadProbeActor`），绿色为两类转写输出。
- **双版本路径差异**：
  - **专业版（`LiteASRP_v1.2.0_7`，`share_weight: false`）**：经独立 `nonstream_feature_extractor` 进入 `nonstream.packed`（29 层解码器，Metal）。
  - **通用版（`LiteASRm_v1.0.1_5`，`share_weight: true`）**：紫色虚线路径，直接复用流式输出并经 4 倍下采样的 880 维 `audio_proj`。
- **历史版本**：1.1.0 单模型架构图保留在 Git Tag `tags/macos_1.1.0`。

## 重新渲染

安装 Graphviz 后，从仓库根目录执行：

```sh
dot -Tpng diagrams/doubao-asr-architecture.dot -o diagrams/doubao-asr-architecture.png
```

源码默认使用 `PingFang SC` 字体，非 macOS 环境可替换为系统自带中文字体后重新渲染。
