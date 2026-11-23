# 发布范围与隐私处理

## 收录与排除

| 内容 | 状态 |
| :--- | :--- |
| 分析文档、FLUTE v2/v3 验证与解包脚本 | 公开 |
| 1.1.1 模型配置文件（`pro-config.yaml` / `general-config.yaml` / `fbank.conf`） | 公开 |
| FLUTE v3 固定根种子（`model-seed.bin`）与校验报告 JSON | 公开 |
| 静态结构证据、架构图与公开资料链接 | 公开 |
| 加密模型源包、解包权重（`.packed` / `.pthlite`） | 不提供 |
| 应用二进制、动态库、内存快照、LuLu 个人配置备份 | 不提供 |

`model-seed.bin` 仅用于验证 FLUTE v3 容器格式，与任何用户账号无关。本机解包产物统一放在 `.gitignore` 忽略目录 `.local-data/` 中。

## 身份与路径脱敏

- Git 提交作者使用 `Anonymous <anonymous@invalid>`，不含个人姓名或真实邮箱。
- 文档与校验报告中所有本机路径均以 `~` 替代用户主目录，脚本运行时通过 `Path.home()` 动态定位。
