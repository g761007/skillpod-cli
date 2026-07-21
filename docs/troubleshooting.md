# Troubleshooting / 疑難排解

[← README](../README.md) · [English](#english) · [繁體中文](#繁體中文)

---

## English

**Agent directory is empty after `install`**
`agents:` defaults to `[]`, which disables fan-out. Declare the agents you use.

**A skill is installed but my agent ignores it**
If the same name exists in `~/.skillpod/skills/`, Claude Code prefers the
personal copy. `skillpod status` shows which layer is serving it.

**Symlink creation fails (Windows, some CI)**
Set `install.mode: copy`, or rely on the default `fallback: [copy]`.

**`skillpod add <owner/repo>` fails with a git error**
Check `git` is on `$PATH`. For private repos, verify your SSH or HTTPS
credentials.

**`global archive '*'` expands to filenames**
Quote the asterisk — the shell expands it otherwise.

Still stuck? `skillpod doctor` reports faults with paths and codes, and
[issues](https://github.com/g761007/skillpod-cli/issues) are welcome.

---

## 繁體中文

**跑完 `install` 後 agent 目錄是空的**
`agents:` 預設為 `[]`，這會停用 fan-out。請宣告你實際使用的 agent。

**skill 裝好了，但我的 agent 沒理它**
如果 `~/.skillpod/skills/` 裡有同名的 skill，Claude Code 會優先採用個人複本。
`skillpod status` 會顯示目前是哪一層在提供它。

**建立 symlink 失敗（Windows、部分 CI）**
設定 `install.mode: copy`，或倚賴預設的 `fallback: [copy]`。

**`skillpod add <owner/repo>` 出現 git 錯誤**
確認 `git` 在 `$PATH` 上。私有 repo 請確認你的 SSH 或 HTTPS 憑證。

**`global archive '*'` 被展開成一堆檔名**
請把星號加上引號 —— 否則 shell 會先幫你展開。

還是卡住？`skillpod doctor` 會回報問題、路徑與錯誤碼，也歡迎到
[issues](https://github.com/g761007/skillpod-cli/issues) 回報。
