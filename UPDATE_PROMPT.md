# 版本更新复用 Prompt

当豆包输入法 macOS 发布新版本时，可直接复制下方 Prompt 交给 AI Agent，配合 [AGENTS.md](AGENTS.md) 与 `scripts/` 工具完成核验、最小修正与发布。

````markdown
参照仓库根目录 `AGENTS.md` 的规则与分工，使用本机最新安装的 `/Library/Input Methods/DoubaoIme.app` 与 `~/Library/Application Support/DoubaoIme/` 对当前仓库做一次全面核验与同步，将 `main` 更新至最新版本并同步对应的 `macos_<VERSION>` Git Tag 与 GitHub 仓库描述。

## 铁律
1. **只保留最新最终态**：`main` 分支所有文档直接写当前最新版本的状态与结论，不写“某版本复核/迁移对比”等过程记录；旧版产物只保留在 Git Tag（如 `macos_1.1.0`）。
2. **先核验再改写**：一切以本机实测输出为准；模型未变时复跑校验即可，不无故重算或改写哈希。
3. **全包扫描防漏检**：不仅核对已知清单，还要扫描整个 `.app` 包（含 `Applications/`、`Frameworks/`）与本地数据目录，排查新增模型变体、容器格式、推理后端（MNN / CoreML / MLX / ONNX 等）、拆分动态库或新外联域名/打点方法。
4. **隐私与合规边界**：严格遵守 `PRIVACY.md`——绝不提交权重、源包、应用二进制、`.local-data/` 产物或真实用户名路径（本机路径一律用 `~`）；Git 作者保持 `Anonymous <anonymous@invalid>`。
5. **文风要求**：简洁、高信息密度、说人话、直给结论，不堆叠空话和模板化表达。

## 执行流程（工具优先 + Agent 研判）

### 1. 一键采集本机现状与差异
运行：
```sh
python3 scripts/inspect_installation.py
```
重点检查输出的 `diff_vs_repo`、`bundle_scan`（新增/移除的 `flute.*`、声明模型名、推理后端关键字、网络域名、遥测打点方法、`sdk_version`）与 `local_models`：
- **仅主程序更新、模型未变**：走轻量更新路径（刷新指纹、运行时标记、版本号与架构图标题）。
- **模型、容器、引擎或架构有变**：先对变化项做深度静态/解包分析（包括排查是否有未下载的新模型变体），再扩展脚本并更新配置、分析报告、结构对比与架构图。

### 2. 验证离线模型与解包产物
- 对本机已下载的各离线 ASR 模型执行目录与解包校验：
  ```sh
  python3 model-analysis/verify_directory.py --model "<asr_model.model>"
  python3 model-analysis/extract_model.py --verify-only --model "<asr_model.model>" .local-data/<extracted-dir>
  ```
  （若为新模型或尚无本地解包目录，先去掉 `--verify-only` 解包到 `.local-data/` 并核对配置与内部文件。）
- 若容器版本、密钥派生或混淆算法有变，先扩展 `model-analysis/verify_directory.py`、`model-analysis/extract_model.py` 与 `model-analysis/FINDINGS.md`。
- 如需同步静态标记与 `.packed` 元数据：
  ```sh
  python3 scripts/inspect_installation.py --write-runtime-markers
  python3 scripts/inspect_installation.py --write-model-metadata
  ```

### 3. 同步仓库文档、索引与架构图
按需最小修正以下内容，保证跨文件版本号、SHA-256、文件数与结论一致：
- **指纹与文档**：`environment.json`、`README.md`、`OFFLINE_MODEL_DOWNLOAD.md`、`FILE_INDEX.md`、`PRIVACY.md`、`model-analysis/FINDINGS.md`、`comparison/COMPARISON.md`（若增删文件或支持新模型，同步更新 `FILE_INDEX.md` 文件总数及工具注释）。
- **架构图**：若版本号、模型阵容、数据流或硬件后端变化，更新 `diagrams/doubao-asr-architecture.dot` 并重新渲染，再核对 `diagrams/README.md` 中的分辨率：
  ```sh
  dot -Tpng diagrams/doubao-asr-architecture.dot -o diagrams/doubao-asr-architecture.png
  ```

### 4. 提交前统一门禁
所有编辑完成后、提交前必须执行：
```sh
python3 scripts/validate_repo.py --verify-local
```
确保全仓 JSON 语法、`FILE_INDEX.md` 与 `git ls-files` 一致性、相对链接、隐私脱敏、Git 作者配置、跨文件版本号/SHA-256/PNG 分辨率及本地模型校验全部 `[OK]`；再额外用 `git grep` 确认无旧版本号、旧哈希或失效符号残留。

### 5. 提交、打 Tag、推送与同步 GitHub 描述
1. 确认 Git 作者为 `Anonymous <anonymous@invalid>`，按 Conventional Commits 提交到 `main`。
2. 在新提交上创建带注释 Tag：`git tag -a macos_<VERSION> -m "macos_<VERSION>"`。
3. 推送 `main` 与 `refs/tags/macos_<VERSION>` 到 `origin`（如本次指令要求推送）。
4. 检查并同步 GitHub 仓库描述，确保准确反映当前版本与模型阵容：
   ```sh
   gh repo view --json nameWithOwner,description
   gh repo edit --description "<反映当前版本与模型阵容的简洁描述>"
   ```
````
