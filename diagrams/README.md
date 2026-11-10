# 离线语音模型架构图

> [!NOTE]
> 仅供学习分析使用。

图描述豆包输入法 1.1.0 的 `acllm_main_model_mac` 1.8。内容依据 [主配置](../model-config/config.yaml)、[VAD 配置](../model-config/vad/config.yaml) 和 [模型结构分析](../comparison/COMPARISON.md)。

| 文件 | 用途 |
| --- | --- |
| [doubao-asr-architecture.png](doubao-asr-architecture.png) | README 使用的架构图，5961 × 1867 像素 |
| [doubao-asr-architecture.dot](doubao-asr-architecture.dot) | 可编辑的 Graphviz 源码 |

## 图例与证据范围

- 蓝色表示流式识别路径，紫色表示上下文识别路径，绿色表示两类转写输出。
- 实线表示配置中明确连接的数据流。橙色虚线只表示 draft 的配置引用，未完整验证其启用语义。
- 图是静态配置与模型图证据的整理，未进行运行时调用追踪。两类输出的最终整合策略未验证。
- `non_s_*` 是主模型包内的上下文识别路径，不能据此将它等同于未分析的独立上下文辅助模型 1.1。
- 模型训练血缘、精确参数量和识别性能仍未确认。

## 重新渲染

生成时使用 `diagram-generator` 和 Graphviz 16.1.1。安装 Graphviz 后，从仓库根目录执行：

```sh
dot -Tpng diagrams/doubao-asr-architecture.dot \
  -o diagrams/doubao-asr-architecture.png
```

源码使用 `PingFang SC` 字体。其他系统可改为本机支持中文的字体，再重新渲染。
