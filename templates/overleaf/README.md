# Overleaf Bridge

这个项目已经启用 AI Bridge Kit 的 Overleaf Bridge。

它解决的是一个很具体的问题：**Codex 需要看到整个科研仓库，但 Overleaf 只需要看到论文源码。**

例如科研仓库是：

```text
project/
├── code/
├── analysis/
├── results/
├── docs/
└── paper/
    └── manuscript/
```

Codex 仍然在 `project/` 根目录工作，可以同时读取代码、实验结果、研究文档和论文；Overleaf 只接收配置中的 `paper_root`。如果 `paper_root = "paper/manuscript"`，那么本地的：

```text
paper/manuscript/main.tex
```

在 Overleaf 中就是项目根目录下的：

```text
main.tex
```

Overleaf 不会自行从 GitHub 仓库里抽取某个子目录。这个“只发布论文目录”的工作由 Bridge Kit 在本机完成。

## 哪一边是主版本

完整科研项目仍以 GitHub 仓库为准。Overleaf 是论文协作和在线编译界面，不是整个科研仓库的第二个远端。

推荐理解为：

```text
完整科研仓库
    │
    ├── Codex 读取代码、结果、文档和论文
    │
    └── paper_root
          │
          └── Overleaf Bridge → Overleaf
```

## Codex 写完论文后怎么同步

正常流程是：

```text
Codex 修改论文
→ 本地检查或编译
→ 提交到科研仓库
→ git push origin main
→ ai-bridge overleaf status
→ ai-bridge overleaf push
```

`ai-bridge overleaf push` 不是 `git push origin main` 的替代品。前者只把已经提交的论文目录发布到 Overleaf，后者才是完整科研仓库的正常版本控制。

在真正推送前，Bridge Kit 会先检查 Overleaf 是否从上次同步后发生过变化。如果远端已经有人修改，它会拒绝直接覆盖。

## 合作者在 Overleaf 改了论文怎么办

先看状态：

```bash
ai-bridge overleaf status
```

如果显示 Overleaf 一侧有新修改，再执行：

```bash
ai-bridge overleaf pull
```

推荐后续流程：

```text
ai-bridge overleaf pull
→ 查看 git diff
→ 检查或编译论文
→ git add / commit
→ git push origin main
```

`pull` 只把 Overleaf 修改导入本地 `paper_root`，**不会自动提交，也不会自动推送到 GitHub**。这样可以先检查合作者到底改了什么。

## 同步前为什么要求论文目录干净

下面这些操作都会建立或改变同步基准，因此要求 `paper_root` 中所有需要发布的文件都已经提交：

```text
ai-bridge overleaf connect --bootstrap
ai-bridge overleaf connect
ai-bridge overleaf push
ai-bridge overleaf pull
```

如果论文目录里还有未提交、暂存、删除、重命名或未跟踪的发布文件，Bridge Kit 会先拒绝操作。这样可以避免：

- 把一个 GitHub 历史里不存在的临时草稿发布到 Overleaf；
- 从 Overleaf 拉取文件时覆盖本地尚未提交的新稿；
- 本地和 Overleaf 双方都改了内容时误判谁应该覆盖谁。

## `exclude_paths` 是什么

`paper_root` 里面可能有一些 Codex 或本地开发需要、但 Overleaf 完全不需要的文件。这些文件可以写进 `exclude_paths`。

典型例子：

```text
AGENTS.md
README.md
main.pdf
本地作者笔记
其他只供 GitHub/Codex 使用的辅助文件
```

不要排除任何 Overleaf 编译真正需要的文件，例如：

```text
.tex
.bib
.sty
.cls
论文引用的图片
论文读取的表格或其他资源
```

原则很简单：**只要 Overleaf 编译论文需要它，它就必须位于 `paper_root` 中，而且不能被排除。**

## 多台机器怎么用

项目配置会提交到 GitHub：

```text
automation/overleaf/config.toml
```

但真实 Overleaf 连接和本地镜像属于每台机器自己的状态：

```text
${AI_BRIDGE_STATE_HOME:-~/.ai-bridge}/overleaf/<repo-id>/
├── connection.json
└── mirror/
```

因此，如果同一个仓库会在 Mac、工作站和服务器上操作 Overleaf，每台需要执行同步的机器都要单独 `connect` 一次。

不要把另一台机器的 `~/.ai-bridge/overleaf/...` 复制进 GitHub。

Overleaf 项目的默认分支可能是 `main`、`master` 或项目声明的其他名称。Bridge Kit 会在 `connect` 时读取真实远端分支，并把它保存在本机 `connection.json`；`automation/overleaf/config.toml` 不需要写 `main/master`。

## Token 放在哪里

Bridge Kit 不保存 Overleaf token，也不提供 `--token` 或 `--password` 参数。

真实连接时由 Git 正常完成认证；如果希望以后不重复输入，可以使用自己已有的 Git credential helper。不要把 token 写进仓库、`config.toml`、`connection.json` 或 Git URL。

## 本地和 Overleaf 同时改了怎么办

如果上次同步以后，本地论文和 Overleaf 都发生了不同修改，Bridge Kit 会把状态判定为分叉，并同时拒绝直接 `push` 和 `pull`。

它不会猜哪一边更重要，也不会自动合并。

这时应先人工检查双方修改、完成合并并重新建立一致状态，再继续同步。

## 常用命令

```bash
# 查看状态
ai-bridge overleaf status

# 本地论文已经提交，希望发布到 Overleaf
ai-bridge overleaf push

# Overleaf 有合作者的新修改，希望拉回科研仓库
ai-bridge overleaf pull

# 检查配置和路径是否安全
ai-bridge overleaf validate
```

第一次连接真实 Overleaf 项目时，按照项目负责人提供的 Overleaf Git URL 执行 `ai-bridge overleaf connect`；不要自行覆盖已经有正文的 Overleaf 项目。
