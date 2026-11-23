# 离线语音模型架构图

| 文件 | 说明 |
| :--- | :--- |
| [doubao-asr-architecture.png](doubao-asr-architecture.png) | README 展示的架构图（5961 × 1867） |
| [doubao-asr-architecture.dot](doubao-asr-architecture.dot) | 可编辑的 Graphviz 源码 |

## 图例与版本说明

- **颜色**：蓝色为流式识别路径，紫色为上下文识别路径，绿色为转写输出，橙色虚线为 1.1.0 配置中的 draft 引用。
- **适用范围**：该图基于 1.1.0 主模型（`acllm_main_model_mac` 1.8）静态配置绘制，展示整体 VAD + 双路径骨架。
- **1.1.1 架构演进**：1.1.1 延续了相同的 VAD + 流式 + 非流式上下文双路径，具体变化体现在 [pro-config.yaml](../model-config/pro-config.yaml) 与 [general-config.yaml](../model-config/general-config.yaml)：
  - 推理封装改为 `AsrContextExecutor` + `IntegrationEngineCreator`，ASR 权重从 20 个 `.pthlite` 合并为 `.packed`（内含 `.mnn`）。
  - 新增 `tail_vad_probe`（尾部静音快检）与 `rag_words`（热词检索注入）。
  - 通用版（`share_weight: true`）取消了独立非流式特征提取，改为直接复用流式输出的 880 维 `audio_proj`。

## 重新渲染

安装 Graphviz 后，从仓库根目录执行：

```sh
dot -Tpng diagrams/doubao-asr-architecture.dot -o diagrams/doubao-asr-architecture.png
```

源码默认使用 `PingFang SC` 字体，非 macOS 环境可替换为系统自带中文字体后重新渲染。
