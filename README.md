<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/g761007/skillpod-cli/main/docs/assets/banner-dark.png">
    <img src="https://raw.githubusercontent.com/g761007/skillpod-cli/main/docs/assets/banner.png" alt="skillpod — pod-style dependency manager for AI coding agent skills">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/g761007/skillpod-cli/actions/workflows/ci.yml"><img src="https://github.com/g761007/skillpod-cli/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="https://pypi.org/project/skillpod/"><img src="https://img.shields.io/pypi/v/skillpod.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/skillpod/"><img src="https://img.shields.io/pypi/pyversions/skillpod.svg" alt="Python"></a>
  <a href="https://github.com/g761007/skillpod-cli/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
  <a href="#english">English</a> · <a href="#繁體中文">繁體中文</a>
</p>

---

## English

**Manage the skills your AI coding agents use — per project, or globally.**

A project says which skills it *recommends*. You decide what you actually run.
skillpod installs them once and wires them into every agent you use — Claude
Code, Codex, Gemini, Cursor, OpenCode, Antigravity.

> **Pre-1.0:** the manifest and profile schema may still change in breaking ways.

### Install

```bash
uv tool install skillpod     # or: pipx install skillpod
skillpod --version
```

Needs Python 3.11+ and `git` on your `PATH`.

### 60-second start

```bash
cd my-project
skillpod init                                   # writes skillfile.yml, gitignores .skillpod/
skillpod add anthropics/skills --skill pdf -y   # fetch a skill and wire it up
skillpod status                                 # confirm it landed
```

```
recommends: 1 skill(s)
  satisfied: 1   (1 project)
```

`pdf` is now materialised in `.skillpod/skills/` and linked into `.claude/skills/`,
so your agent can use it. Commit `skillfile.yml`; `.skillpod/` stays out of git.

Not sure what a repo offers? `skillpod add anthropics/skills --list` shows you
before you commit to anything.

### The idea

**`skillfile.yml` recommends, it does not compel.** Commit it and a teammate
reproduces your setup with one command — but nothing is pinned, and ignoring it
is a legitimate choice.

**A skill you already have globally counts as satisfied.** No redundant project
copy is made, as long as every agent you declare is known to read its personal
*and* project skill directories together — Claude Code, Codex, and Gemini CLI
today.

**`install` never surprises you.** It brings in what is missing and leaves the
rest alone, so re-running it is offline and instant. Pulling newer upstream
content is always an explicit `skillpod update`.

### Everyday commands

| Command | What it does |
| --- | --- |
| `skillpod add <source>` | Fetch a skill from a repo or directory and install it |
| `skillpod install` | Install what the manifest recommends and is not already present |
| `skillpod status` | The one-screen answer to "is this project ready" |
| `skillpod link` / `unlink` | Show or hide a skill without deleting it (`-g` for global) |
| `skillpod switch <profile>` | Run only part of this project's skill set |
| `skillpod doctor` | Report faults with paths and codes |

[Full command reference →](https://github.com/g761007/skillpod-cli/blob/main/docs/commands.md)

### Documentation

| Page | Covers |
| --- | --- |
| [Guide](https://github.com/g761007/skillpod-cli/blob/main/docs/guide.md) | Task recipes — recommend a set, install globally, profiles, machine-local skills |
| [Commands](https://github.com/g761007/skillpod-cli/blob/main/docs/commands.md) | Every subcommand and what it does |
| [`skillfile.yml`](https://github.com/g761007/skillpod-cli/blob/main/docs/skillfile.md) | Full manifest reference, with every default |
| [How it works](https://github.com/g761007/skillpod-cli/blob/main/docs/how-it-works.md) | Resolve → cache → materialise → fan out, and what you're trusting |
| [Troubleshooting](https://github.com/g761007/skillpod-cli/blob/main/docs/troubleshooting.md) | Common faults and their fixes |

Every page carries its 繁體中文 translation in the same file.

### Roadmap

| Milestone | Status | Highlights |
| --- | --- | --- |
| 0.1.0 – 0.5.x | shipped | manifest, installer, registry, adapters, `global` CLI |
| 0.6.x | shipped | workspace profiles, activation policy, session shell, composition |
| 0.9.0 | shipped | **recommendation model** — `skillfile.lock` retired, `prefer_global`, `global update`, `status` dashboard, unified `link`/`unlink`, project profiles that reconcile fan-out |
| 0.9.1 | shipped | `prefer_global` extended to Codex and Gemini CLI; Windows suite green and gating CI |
| 1.0.0 | planned | schema freeze |

Full history: [`CHANGELOG.md`](https://github.com/g761007/skillpod-cli/blob/main/CHANGELOG.md).

### Contributing

```bash
uv sync
uv run pytest -q
uv run ruff check src tests
uv run mypy src/skillpod
```

See [`CONTRIBUTING.md`](https://github.com/g761007/skillpod-cli/blob/main/CONTRIBUTING.md)
for the module map and conventions.

### License

MIT — see [`LICENSE`](https://github.com/g761007/skillpod-cli/blob/main/LICENSE).

---

## 繁體中文

**管理 AI coding agent 使用的 skill —— 可以只用在單一專案，也可以套用到全域。**

專案負責*建議*要用哪些 skill，實際跑什麼由你決定。skillpod 只安裝一份，
然後把它接到你用的每一個 agent：Claude Code、Codex、Gemini、Cursor、
OpenCode、Antigravity。

> **Pre-1.0：** manifest 與 profile schema 仍可能出現破壞性變更。

### 安裝

```bash
uv tool install skillpod     # 或：pipx install skillpod
skillpod --version
```

需要 Python 3.11+，且 `git` 必須在 `PATH` 上。

### 60 秒上手

```bash
cd my-project
skillpod init                                   # 產生 skillfile.yml，並把 .skillpod/ 加進 gitignore
skillpod add anthropics/skills --skill pdf -y   # 取得一個 skill 並接上 agent
skillpod status                                 # 確認結果
```

```
recommends: 1 skill(s)
  satisfied: 1   (1 project)
```

`pdf` 現在已經實體化在 `.skillpod/skills/`，並連結到 `.claude/skills/`，
你的 agent 就能使用它。請把 `skillfile.yml` 提交進版控；`.skillpod/` 則不進 git。

不確定某個 repo 提供哪些 skill？`skillpod add anthropics/skills --list`
可以讓你先看過再決定。

### 核心概念

**`skillfile.yml` 是建議，不是強制。** 把它提交進版控，同事就能用一道指令重現你的環境 ——
但它不釘死任何東西，選擇忽略它也是完全正當的。

**全域已經有的 skill 就算已滿足。** 不會再多做一份專案複本，前提是你宣告的每一個 agent
都確定會同時讀取個人與專案的 skill 目錄 —— 目前是 Claude Code、Codex 與 Gemini CLI。

**`install` 不會給你意外。** 它只補上缺少的，其餘原封不動，所以重複執行是離線且瞬間完成的。
要拉取較新的上游內容，永遠得明確執行 `skillpod update`。

### 常用指令

| 指令 | 用途 |
| --- | --- |
| `skillpod add <source>` | 從 repo 或目錄取得 skill 並安裝 |
| `skillpod install` | 安裝 manifest 建議、但目前尚未具備的 skill |
| `skillpod status` | 用一個畫面回答「這個專案準備好了嗎」 |
| `skillpod link` / `unlink` | 顯示或隱藏某個 skill，但不刪除它（`-g` 為全域） |
| `skillpod switch <profile>` | 只跑這個專案的一部分 skill |
| `skillpod doctor` | 回報問題，附上路徑與錯誤碼 |

[完整指令參考 →](https://github.com/g761007/skillpod-cli/blob/main/docs/commands.md#繁體中文)

### 文件

| 頁面 | 內容 |
| --- | --- |
| [使用指南](https://github.com/g761007/skillpod-cli/blob/main/docs/guide.md#繁體中文) | 情境操作 —— 建議一組 skill、全域安裝、profile、只存在本機的 skill |
| [指令](https://github.com/g761007/skillpod-cli/blob/main/docs/commands.md#繁體中文) | 每個子指令與它的用途 |
| [`skillfile.yml`](https://github.com/g761007/skillpod-cli/blob/main/docs/skillfile.md#繁體中文) | 完整 manifest 參考，含所有預設值 |
| [運作方式](https://github.com/g761007/skillpod-cli/blob/main/docs/how-it-works.md#繁體中文) | resolve → cache → 實體化 → fan out，以及你正在信任什麼 |
| [疑難排解](https://github.com/g761007/skillpod-cli/blob/main/docs/troubleshooting.md#繁體中文) | 常見問題與解法 |

每份文件都在同一個檔案裡附上英文原文。

### 藍圖

| 里程碑 | 狀態 | 重點 |
| --- | --- | --- |
| 0.1.0 – 0.5.x | 已發布 | manifest、installer、registry、adapter、`global` CLI |
| 0.6.x | 已發布 | workspace profile、activation 政策、session shell、組合 |
| 0.9.0 | 已發布 | **建議模型** —— 移除 `skillfile.lock`、`prefer_global`、`global update`、`status` 儀表板、統一的 `link`/`unlink`、會調和 fan-out 的專案 profile |
| 0.9.1 | 已發布 | `prefer_global` 擴及 Codex 與 Gemini CLI；Windows 測試套件全綠並納入 CI 把關 |
| 1.0.0 | 規劃中 | schema 凍結 |

完整歷程：[`CHANGELOG.md`](https://github.com/g761007/skillpod-cli/blob/main/CHANGELOG.md)。

### 參與貢獻

```bash
uv sync
uv run pytest -q
uv run ruff check src tests
uv run mypy src/skillpod
```

模組地圖與慣例請見
[`CONTRIBUTING.md`](https://github.com/g761007/skillpod-cli/blob/main/CONTRIBUTING.md)。

### 授權

MIT —— 詳見 [`LICENSE`](https://github.com/g761007/skillpod-cli/blob/main/LICENSE)。
