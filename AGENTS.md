# AI Agent 维护指南

本仓库记录豆包输入法 macOS 离线语音模型的静态分析结果、验证工具与架构文档，主要由 AI Agent 随客户端新版迭代更新（可直接复制使用的更新 Prompt 见 [UPDATE_PROMPT.md](UPDATE_PROMPT.md)）。

## 铁律

1. **只保留最新最终态**：`main` 分支所有文档直接写当前最新版本的状态与结论，不写“某版本复核/迁移对比”等过程记录；旧版产物只留在 Git Tag（如 `macos_1.1.0`）。
2. **先核验再改写**：以本机 `/Library/Input Methods/DoubaoIme.app` 及 `~/Library/Application Support/DoubaoIme/` 的实测输出为准；模型未变时复跑校验即可，不无故重算或改写哈希。
3. **不漏检新变化**：不仅查仓库里已有清单，还要扫描整个 `.app` 包（含 `Applications/`、`Frameworks/`）与本地数据目录，排查新增模型变体、容器格式、推理后端（MNN / CoreML / MLX / ONNX 等）、拆分的动态库或新外联域名。
4. **隐私与合规边界**：严格遵守 [PRIVACY.md](PRIVACY.md)——绝不提交权重、源包、应用二进制、`.local-data/` 产物或真实用户名路径（本机路径一律用 `~`）；Git 作者保持 `Anonymous <anonymous@invalid>`。
5. **文风要求**：简洁、高信息密度、说人话、直给结论，不堆叠空话和模板化表达。

## 标准更新流程

### 1. 一键采集本机现状与差异
```sh
python3 scripts/inspect_installation.py
```
重点查看输出的 `diff_vs_repo`、`bundle_scan`（新增/移除的 `flute.*`、模型逻辑名、推理后端、网络域名与打点方法）以及 `local_models`：
- **仅主程序更新、模型未变**：走轻量更新路径（刷新指纹、运行时标记、版本号与架构图标题）。
- **模型、容器或架构有变**：先对变化项做深度分析，再按需更新解包脚本、`model-config/`、`model-analysis/FINDINGS.md`、报告 JSON、`comparison/COMPARISON.md` 与架构图。

### 2. 验证离线模型与解包产物
```sh
# 校验当前激活模型，或显式指定 --model 逐个校验
python3 model-analysis/verify_directory.py

# 已有解包目录时直接校验；新模型先去掉 --verify-only 解包到 .local-data/
python3 model-analysis/extract_model.py --verify-only \
  --model "<asr_model.model>" .local-data/<extracted-dir>
```
若需同步 `comparison/runtime-markers.json` 或 `comparison/model-metadata.json`：
```sh
python3 scripts/inspect_installation.py --write-runtime-markers
python3 scripts/inspect_installation.py --write-model-metadata
```

### 3. 更新文档与架构图
- 同步 `environment.json`、`README.md`、`OFFLINE_MODEL_DOWNLOAD.md`、`FILE_INDEX.md`、`model-analysis/FINDINGS.md`、`comparison/COMPARISON.md`。
- 若版本号、模型阵容或数据流变化，更新 `diagrams/doubao-asr-architecture.dot` 并重新渲染，再核对 `diagrams/README.md` 中的分辨率：
  ```sh
  dot -Tpng diagrams/doubao-asr-architecture.dot -o diagrams/doubao-asr-architecture.png
  ```

### 4. 提交前统一门禁
所有编辑完成后、提交前必须执行：
```sh
python3 scripts/validate_repo.py --verify-local
```
确保 JSON 语法、`FILE_INDEX.md` 与 `git ls-files` 一致性、相对链接、隐私脱敏、跨文件版本号/SHA-256/PNG 分辨率及本地模型校验全部通过。

### 5. 提交、打 Tag 与同步 GitHub 仓库描述
- 使用 Conventional Commits 提交到 `main`（作者 `Anonymous <anonymous@invalid>`）。
- 创建带注释 Tag：`git tag -a macos_<VERSION> -m "macos_<VERSION>"`。
- 推送 `main` 与 `refs/tags/macos_<VERSION>` 后，检查并同步 GitHub 仓库描述（只写当前版本与模型阵容，不提旧版本）：
  ```sh
  gh repo view --json nameWithOwner,description
  gh repo edit --description "<仅描述当前版本与模型阵容的简洁说明，不涉及旧版本>"
  ```

## 工具与 Agent 分工
- **交给脚本（确定性）**：指纹采集、全包字符串开放式扫描、`runtime-markers.json` / `model-metadata.json` 生成、FLUTE 容器校验/解包、JSON/链接/索引/隐私/跨文件一致性检查。
- **交给 Agent（智能判断）**：新模型/新容器/新推理后端的逆向研判、文档正文修订、架构图结构调整、GitHub 描述与提交信息撰写。
