# 发布范围、隐私与合规声明

## 收录与排除

| 内容 | 状态 |
| :--- | :--- |
| 分析文档、FLUTE v2/v3 验证与解包脚本、仓库核验脚本 | 公开 |
| 离线模型配置文件（`pro-config.yaml` / `general-config.yaml` / `fbank.conf`） | 公开 |
| FLUTE v3 固定根种子（`flute-v3-seed.bin`）与校验报告 JSON | 公开 |
| 静态结构证据、架构图与公开资料链接 | 公开 |
| 加密模型源包、解包权重（`.packed` / `.pthlite` / `.mnn` 等） | 不提供 |
| 应用二进制、动态库、内存快照、LuLu 个人配置备份 | 不提供 |

`flute-v3-seed.bin` 仅用于验证 FLUTE v3 容器格式，与任何用户账号无关。本机解包产物统一放在 `.gitignore` 忽略目录 `.local-data/` 中。

## 身份与路径脱敏

- Git 提交作者使用 `Anonymous <anonymous@invalid>`，不含个人姓名或真实邮箱。
- 文档与校验报告中所有本机路径均以 `~` 替代用户主目录，脚本运行时通过 `Path.home()` 动态定位。

## 合规与反滥用原则

- **本地静态研究**：所有分析均基于本机合法获取的客户端与离线模型，不涉及对远程服务端的未授权探测、绕过或干扰。
- **脚本与种子用途**：`verify_container.py`、`extract_model.py` 与 `flute-v3-seed.bin` 仅用于本地格式复现与完整性校验，不支持用于模型提取后的商业化集成或权重二次分发。
- **CDN 链接边界**：[OFFLINE_MODEL_DOWNLOAD.md](OFFLINE_MODEL_DOWNLOAD.md) 中的官方地址仅用于个人离线部署与防火墙规则验证，禁止高并发拉取、自动化抓取或镜像分发。
- **非官方与权利响应**：本项目与相关厂商无任何关联。权利方如认为仓库存在不当内容，可通过 Issue 反馈，核实后将及时配合处理或移除。
