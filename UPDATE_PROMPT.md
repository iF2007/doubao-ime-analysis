# 版本更新复用 Prompt

当豆包输入法 macOS 发布新版本时，复制下方 Prompt 交给 AI Agent，配合 [AI Agent 维护指南](AGENTS.md) 执行全流程更新。

````markdown
使用本机最新安装的 `/Library/Input Methods/DoubaoIme.app` 与 `~/Library/Application Support/DoubaoIme/`，核验仓库全部结论并同步 `main` 分支、`macos_<VERSION>` Tag 与 GitHub 仓库描述。

先完整读取并严格遵守仓库根目录 `AGENTS.md` 与 `PRIVACY.md`，并按下列要求执行：

1. 运行 `python3 scripts/inspect_installation.py`，根据 `diff_vs_repo`、`bundle_scan` 和 `local_models` 判断是仅主程序更新，还是模型、容器或推理架构发生变化（不漏扫 `Applications/`、`Frameworks/` 及未下载的新模型逻辑名）。
2. 运行 `python3 model-analysis/verify_container.py --all` 和 `python3 model-analysis/extract_model.py --all --verify-only`（如遇新模型先解包到 `.local-data/`）。模型未变时保留原有哈希和校验值；容器、密钥派生或架构有变化时先完成逆向分析并更新脚本与配置。
3. 按需运行 `--write-runtime-markers` 和 `--write-packed-layers` 刷新扫描数据，并同步全部文档、索引与架构图。`main` 分支文档只保留当前最终态，不保留迁移或复核过程记录。
4. 编辑完成后执行 `python3 scripts/validate_repo.py --verify-local`，并用 `git grep` 确认无旧版本号、旧 SHA-256 或失效符号残留。
5. 以 `Anonymous <anonymous@invalid>` 按 Conventional Commits 提交至 `main`，打带注释 Tag `macos_<VERSION>`，推送 `main` 与 `refs/tags/macos_<VERSION>`，并更新 GitHub 仓库描述（只写当前版本与模型阵容，不提旧版本）。
````
