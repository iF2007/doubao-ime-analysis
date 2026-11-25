# 离线语音模型架构图

下表列出架构图成品与 Graphviz 源文件。

| 文件 | 说明 |
| :--- | :--- |
| [doubao-asr-architecture.png](doubao-asr-architecture.png) | README 展示的 `1.1.2` 架构图（5720 × 1516 像素） |
| [doubao-asr-architecture.dot](doubao-asr-architecture.dot) | 可编辑的 Graphviz 源码 |

## 图例

图中的颜色与连线分别代表以下组件和路径：

- 蓝色节点表示流式识别路径（`stream.packed`）。
- 紫色节点表示非流式上下文路径（专业版为 `nonstream.packed`，通用版为 `no_stream.packed`）。
- 黄色节点表示尾部静音快检（`TailVadProbeActor`）。
- 绿色节点表示两类转写输出。
- 专业版（`LiteASRP_v1.2.0_7`，`share_weight: false`）经独立 `nonstream_feature_extractor` 进入 `nonstream.packed`（29 层解码器，Metal）。
- 通用版（`LiteASRm_v1.0.1_5`，`share_weight: true`）沿紫色虚线复用流式输出的 880 维 `audio_proj`（4 倍下采样）。
- `1.1.0` 单模型架构图保留在 Git Tag `macos_1.1.0`。

## 重新渲染

安装 Graphviz 后，在仓库根目录运行以下命令，即可重新生成 `5720 × 1516` 像素的 `doubao-asr-architecture.png`：

```sh
dot -Tpng diagrams/doubao-asr-architecture.dot -o diagrams/doubao-asr-architecture.png
```

源码默认使用 `PingFang SC` 字体。如果当前系统不是 macOS，先将该字体替换为系统自带中文字体后再渲染。
