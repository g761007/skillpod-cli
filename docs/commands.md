# Commands / 指令

[← README](../README.md) · [English](#english) · [繁體中文](#繁體中文)

---

## English

| Command | What it does |
| --- | --- |
| `skillpod init` | Write a starter `skillfile.yml` and gitignore `.skillpod/` |
| `skillpod add <source>` | Fetch a skill from a repo or directory and install it |
| `skillpod install` | Install what the manifest recommends and is not already present |
| `skillpod update [skill]` | Re-resolve and pull newer upstream content |
| `skillpod remove <skill>` | Drop a skill from the manifest and uninstall it |
| `skillpod link <skill>` | Make a skill visible to your agents (`-g` for global) |
| `skillpod unlink <skill>` | Hide it again, keeping the copy (`-g` for global) |
| `skillpod status` | The one-screen answer to "is this project ready" |
| `skillpod list` | Per-skill breakdown: source, layer, installed commit |
| `skillpod doctor` | Report faults with paths and codes |
| `skillpod sync` | Rebuild fan-out from the install record, offline |
| `skillpod outdated` | Compare installed commits against upstream |
| `skillpod search <query>` | Search the skills.sh registry |
| `skillpod global …` | `list`, `link`, `unlink`, `update`, `archive`, `doctor` |
| `skillpod profile …` | `create`, `list`, `show`, `save`, `diff`, `export`, `import` |
| `skillpod switch <name>` | Set the active profile for a scope |
| `skillpod shell <name>` | Sub-shell with a profile pre-activated |
| `skillpod resolve` | Show the effective skill set, with `--explain` |
| `skillpod adapter list` | Inspect the active adapter registry |
| `skillpod schema` | Emit the JSON Schema for editor integration |

`--help` on any subcommand shows the full options. Most commands accept
`--json` for scripting.

See also: [Guide](./guide.md) · [`skillfile.yml` reference](./skillfile.md)

---

## 繁體中文

| 指令 | 用途 |
| --- | --- |
| `skillpod init` | 產生起始的 `skillfile.yml`，並把 `.skillpod/` 加進 gitignore |
| `skillpod add <source>` | 從 repo 或目錄取得 skill 並安裝 |
| `skillpod install` | 安裝 manifest 建議、但目前尚未具備的 skill |
| `skillpod update [skill]` | 重新解析並拉取較新的上游內容 |
| `skillpod remove <skill>` | 從 manifest 移除 skill 並解除安裝 |
| `skillpod link <skill>` | 讓 agent 看得到某個 skill（`-g` 為全域） |
| `skillpod unlink <skill>` | 再次隱藏它，但保留複本（`-g` 為全域） |
| `skillpod status` | 用一個畫面回答「這個專案準備好了嗎」 |
| `skillpod list` | 逐一 skill 的細節：source、layer、已安裝的 commit |
| `skillpod doctor` | 回報問題，附上路徑與錯誤碼 |
| `skillpod sync` | 依安裝紀錄離線重建 fan-out |
| `skillpod outdated` | 比對已安裝的 commit 與上游 |
| `skillpod search <query>` | 搜尋 skills.sh registry |
| `skillpod global …` | `list`、`link`、`unlink`、`update`、`archive`、`doctor` |
| `skillpod profile …` | `create`、`list`、`show`、`save`、`diff`、`export`、`import` |
| `skillpod switch <name>` | 設定某個 scope 目前生效的 profile |
| `skillpod shell <name>` | 開一個已預先啟用該 profile 的子 shell |
| `skillpod resolve` | 顯示最終生效的 skill 集合，可加 `--explain` |
| `skillpod adapter list` | 檢視目前生效的 adapter registry |
| `skillpod schema` | 輸出 JSON Schema 供編輯器整合 |

任何子指令加上 `--help` 都會顯示完整選項。大多數指令都支援 `--json` 以便寫腳本。

延伸閱讀：[使用指南](./guide.md#繁體中文) · [`skillfile.yml` 參考](./skillfile.md#繁體中文)
