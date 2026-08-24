## Overleaf Bridge

本仓库已启用 AI Bridge Kit 的 Overleaf Bridge。

- Codex 可以读取整个科研仓库，用代码、实验结果、研究文档和论文共同判断内容。
- 只有 `__PAPER_ROOT__` 是 Overleaf 发布根目录，主文件 `__MAIN_DOCUMENT__` 必须位于其中。
- Overleaf 只是论文协作镜像，不是完整科研仓库的第二个主版本。
- Overleaf 远端分支由 `ai-bridge overleaf connect` 从真实项目读取，并保存在本机连接状态中；不要在 tracked config 中手工指定 `main/master`。
- Overleaf 编译所需的全部论文资源都必须位于发布根目录中，而且不能写进 `exclude_paths`。
- `exclude_paths` 只用于不参与 Overleaf 编译、但需要保留在 GitHub/Codex 工作区中的本地辅助文件。
- 执行 `ai-bridge overleaf push` 前，必须通过 Bridge 的同步基准检查，避免覆盖尚未拉取的 Overleaf 修改。
- 执行 `ai-bridge overleaf pull` 后，先检查差异并编译论文，再按正常 GitHub `origin` 流程提交和推送。
