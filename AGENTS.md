# AI Agent 维护指南

本仓库记录豆包输入法 macOS 离线语音模型的静态分析结果、验证工具与架构文档。每次客户端新版发布时，由 AI Agent 配合仓库脚本完成核验与更新。可直接复制使用的触发 Prompt 见 [UPDATE_PROMPT.md](UPDATE_PROMPT.md)。

## 基本准则

1. `main` 分支文档只写当前最新版本的状态和结论，不保留跨版本迁移或复核的过程记录。旧版产物保存在 Git Tag 中（例如 `macos_1.1.0`）。
2. 所有修改必须以本机 `/Library/Input Methods/DoubaoIme.app` 与 `~/Library/Application Support/DoubaoIme/` 的实测输出为准。模型未变化时只复跑校验，不改动现有校验哈希。
3. 扫描范围必须覆盖整个 `.app` 包（含 `Applications/` 与 `Frameworks/`）以及本地数据目录，主动排查新增模型变体、容器格式、推理后端（MNN、CoreML、MLX、ONNX 等）、拆分动态库与新的外联域名。
4. 遵守 [PRIVACY.md](PRIVACY.md) 约定的数据边界。不要提交模型权重、容器源包、应用二进制或 `.local-data/` 目录中的文件。文档和 JSON 报告中的本机主目录路径统一写成 `~`。Git 提交作者必须使用 `Anonymous <anonymous@invalid>`。
5. 行文保持直接、简洁，只写实测事实与明确结论，不加修饰性套话。

## 标准更新步骤

按下列顺序完成本机核验、脚本校验和发布。

1. 采集本机应用指纹、全包静态扫描结果与差异摘要：

   ```sh
   python3 scripts/inspect_installation.py
   ```

   重点检查输出中的 `diff_vs_repo`、`bundle_scan` 与 `local_models`：
   - 如果只有主程序更新且模型未变，只刷新应用指纹、运行时标记、版本号与架构图标题。
   - 如果模型、容器或推理架构发生变化，先对变化部分做静态与解包分析，再更新解包脚本、`model-config/`、`model-analysis/CONTAINER_AND_DECRYPTION.md`、报告 JSON、`comparison/ARCHITECTURE_COMPARISON.md` 与架构图。

2. 校验本地离线模型并按需提取或刷新元数据：

   ```sh
   python3 model-analysis/verify_container.py --all
   python3 model-analysis/extract_model.py --all --verify-only
   ```

   如果这是初次提取新模型，先去掉 `--verify-only` 将模型解包到 `.local-data/`。如需同步 `comparison/runtime-markers.json` 或 `comparison/packed-mnn-layers.json`，运行：

   ```sh
   python3 scripts/inspect_installation.py --write-runtime-markers
   python3 scripts/inspect_installation.py --write-packed-layers
   ```

3. 同步 `environment.json`、`README.md`、`OFFLINE_MODEL_DOWNLOAD.md`、`FILE_INDEX.md`、`model-analysis/CONTAINER_AND_DECRYPTION.md` 与 `comparison/ARCHITECTURE_COMPARISON.md`。如果版本号、模型阵容或数据流有变化，先更新 `diagrams/doubao-asr-architecture.dot` 并重新渲染，再检查 `diagrams/README.md` 中的像素尺寸：

   ```sh
   dot -Tpng diagrams/doubao-asr-architecture.dot -o diagrams/doubao-asr-architecture.png
   ```

4. 提交前在仓库根目录运行门禁脚本，确保全部检查输出 `[OK]`：

   ```sh
   python3 scripts/validate_repo.py --verify-local
   ```

5. 使用 Conventional Commits 提交到 `main`（作者 `Anonymous <anonymous@invalid>`），然后创建带注释 Tag 并推送远端：

   ```sh
   git tag -a macos_<VERSION> -m "macos_<VERSION>"
   git push origin main refs/tags/macos_<VERSION>
   ```

   推送完成后，检查并更新 GitHub 仓库描述，只写当前版本和模型阵容，不提旧版本：

   ```sh
   gh repo view --json nameWithOwner,description
   gh repo edit --description "<仅描述当前版本与模型阵容的说明，不提旧版本>"
   ```

## 脚本与 Agent 分工

以下任务分别由脚本和 Agent 承担：

- 脚本负责确定性操作：指纹采集、全包字符串扫描、`runtime-markers.json` 与 `packed-mnn-layers.json` 生成、FLUTE 容器校验与解包，以及 JSON、链接、索引、隐私和跨文件一致性检查。
- Agent 负责研判与修订：分析新模型或新推理后端的格式变化、更新文档正文、调整架构图结构，以及撰写 Git 提交信息与 GitHub 仓库描述。
