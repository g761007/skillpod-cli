# `skillpod global archive` — 改為「集中到 ~/.skillpod/skills」

## Context

目前 `skillpod global archive <name>` 的行為：把每個符合的 `~/.<agent>/skills/<name>/` 就地改名成 `<name>.archived-YYYYMMDD-HHMMSS`，**完全不碰 `~/.skillpod/skills/`**。換言之，「封存」只是在原 agent 目錄留下加時戳的備份。

使用者實際的目的是「整理現已存在、散落在各 agent 目錄的 global skill」：希望 `archive` 把 skill **集中搬到 `~/.skillpod/skills/<name>/`**（這正是 skillpod 既有的 global skill source-of-truth 路徑），同時把 agent 目錄裡的副本/連結刪掉；之後若有專案要用，再透過 skillpod 安裝即可。

也就是：
- 從「在 agent 目錄留時戳備份」→ 變成「把 skill **遷移**進 skillpod 集中庫」。
- 形式：保持目錄結構（不打包 tar.gz）。

## Recommended approach

重寫 `src/skillpod/cli/commands/global_archive.py:run()` 的核心邏輯，將語意從「rename in place」改為「move to `~/.skillpod/skills/<name>/`」。

### 行為規格

輸入：`skillpod global archive <name> [--force] [--json]`

1. 列舉所有符合的 agent 目錄項目：沿用 `scan_global_skills()` 過濾 `name == skill_name`（`src/skillpod/cli/commands/global_list.py:45`）。若無任何符合，沿用既有 `fail("global skill {name!r} not found")`。
2. 保留既有「拒絕封存 project-local 路徑」的安全檢查（避免打到 cwd 內的 `.<agent>/skills/<name>`）。
3. **分類每個 match**（沿用 `is_managed_fanout` 概念，但比對的是 *global* root `~/.skillpod/skills/<name>`，因此本檔需要新增一個小工具函式 `_points_into_global_root(link, target_dir)`；不要改 `installer/paths.py:is_managed_fanout`，那是專案級的）：
   - **a. symlink 已指向 `~/.skillpod/skills/<name>`**：屬於 fan-out 殘留，直接 `unlink`，不影響內容。
   - **b. 真實目錄（或指向別處的 symlink）**：是「待集中」的內容來源。
4. 解決目的地 `dest = global_skill_dir(skill_name)`（`installer/paths.py:32`，即 `~/.skillpod/skills/<name>/`）：
   - 若 `dest` 已存在：與所有 b 類來源做 `hash_directory()`（`lockfile/integrity.py:34`）比對。
     - 全部雜湊相符 → idempotent，僅清掉 a/b 類的 agent 端項目。
     - 雜湊不一致 → 預設 `fail("destination ~/.skillpod/skills/<name> exists with different content; pass --force to overwrite")`；`--force` 時以「第一個 b 類來源」為準覆寫 `dest`（先 `shutil.rmtree(dest)` 再搬）。
   - 若 `dest` 不存在：
     - 若 b 類為 0（只有 symlink 殘留）→ 仍 `fail`，因為內容根本不在任何 agent 目錄。
     - 若 b 類有 1 個 → 直接 `dest.parent.mkdir(parents=True, exist_ok=True)` + `shutil.move(b, dest)`。
     - 若 b 類有 ≥ 2 個 → 比對所有 b 類 `hash_directory()` 是否相同：相同則用第一個 `move` 進去，其餘 `rmtree` 刪掉；不同則預設 `fail("multiple agent copies of <name> have different content; pass --force to use {first_path}")`，`--force` 時以第一個為準。
5. 最後：把所有 a 類 unlink、所有未被選為來源的 b 類 `rmtree`。
6. 輸出 payload：`{ok: true, name, dest: str, moved_from: [...], unlinked: [...], removed: [...], skipped_existing: bool}`；human 模式列出每個動作一行。

> 不引入新的 `archived/` 子資料夾、不加時戳後綴、不再保留原 `.archived-<ts>` 命名 —— 使用者明確要求把 skill 集中到 `~/.skillpod/skills/<name>/`，與 `skillpod add -g` 後的成品同形，後續專案就能用既有路徑解析機制把它裝回專案。

### 需修改的檔案

- **`src/skillpod/cli/commands/global_archive.py`**（核心邏輯重寫；同檔內加私有 helper 比對 symlink 是否指向 global root）。
- **`src/skillpod/cli/app.py`**（`global archive` 指令註冊處 line 372–384 附近）：
  - 更新 `help` 為「Move matching global skills into `~/.skillpod/skills/<name>` and clean up agent copies.」
  - 新增 `--force / -f` Typer flag，傳進 `global_archive.run()`。
- **`tests/test_cli.py`**（line 841 既有 `test_global_archive_renames`）：
  - 改寫成 `test_global_archive_moves_to_skillpod_home`：驗證 `~/.skillpod/skills/audit/manifest.md` 存在、`~/.claude/skills/audit` 已不存在。
  - 新增 case：
    - `test_global_archive_idempotent_when_dest_matches`（destination 已存在且 hash 相同 → 只清 agent 端，exit 0）。
    - `test_global_archive_conflict_without_force`（destination 已存在但內容不同 → exit 非 0、保留原狀）。
    - `test_global_archive_force_overwrites`（同上但帶 `--force` → 內容被覆蓋）。
    - `test_global_archive_unlinks_managed_symlink`（agent 端是指向 `~/.skillpod/skills/<name>` 的 symlink → 直接 unlink，dest 內容不變）。
    - `test_global_archive_multi_agent_same_content`（claude+codex 兩處都有，內容相同 → 集中到 dest，兩端都清掉）。
- **`README.md`**：更新 `skillpod global archive` 段落（搜尋 "archive" 周邊文字），描述新語意 + `--force` flag + 對應到 `~/.skillpod/skills/<name>`。
- **`README.md`**：Roadmap & status 補上v0.5.1 shipped
- **`CHANGELOG.md`**：在 Unreleased 區塊新增 `Changed: skillpod global archive now moves matching skills into ~/.skillpod/skills/<name>/ and removes agent-dir copies (previously appended .archived-<ts> in place). Conflicts require --force.`

### 重用的既有 utilities（不要重寫）

| 用途 | 既有 helper | 路徑 |
|------|------|------|
| 列舉 agent 目錄裡 name 相符的項目 | `scan_global_skills()` | `src/skillpod/cli/commands/global_list.py:45` |
| 解出 `~/.skillpod/skills/<name>/` | `global_skill_dir(name)` | `src/skillpod/installer/paths.py:32` |
| 解出 `~/.skillpod/skills/` root（存在性檢查） | `global_install_root()` | `src/skillpod/installer/paths.py:26` |
| 比對兩個 skill 目錄內容是否相同 | `hash_directory(path)` | `src/skillpod/lockfile/integrity.py:34` |
| 統一 JSON / human 輸出 | `emit`, `fail` | `src/skillpod/cli/_output` |
| HOME-aware（測試用 `monkeypatch.setenv("HOME", ...)`） | 上述函式皆吃 `home: Path \| None` 參數 + `Path.home()` 預設 | — |

### Edge cases 與安全保險

- 仍保留「project-local 路徑拒絕」（`_is_inside`），避免誤動 `cwd/.claude/skills/<name>` 之類的專案內目錄。
- 搬移用 `shutil.move`：若同一 mount 是 rename，不同 mount 自動降級成 copy + remove，不需自己處理。
- 搬移前先 `dest.parent.mkdir(parents=True, exist_ok=True)`，避免 `~/.skillpod/skills/` 還沒建立時失敗。
- `rmtree(dest)`（`--force` 覆寫）前要再次確認 `dest` 在 `global_install_root()` 之內，作為防呆；目前 `dest` 來自 `global_skill_dir()` 必然成立，但加一道 `assert` 不傷成本。
- 全程不寫 `skillfile.yml`、不動 lockfile —— 這個指令是 advisory 層，純粹整理 user-level 檔案系統。

## Verification

1. 單元測試：`uv run pytest tests/test_cli.py -k global_archive -v`
2. 全套：`uv run pytest`
3. 手動 smoke：
   ```bash
   tmp=$(mktemp -d) && \
   mkdir -p "$tmp/.claude/skills/foo" && \
   echo '---\ndescription: x\n---\n# foo' > "$tmp/.claude/skills/foo/SKILL.md" && \
   HOME="$tmp" uv run skillpod global archive foo --json && \
   ls "$tmp/.skillpod/skills/foo" && \
   ! ls "$tmp/.claude/skills/foo" 2>/dev/null
   ```
   預期：`~/.skillpod/skills/foo/SKILL.md` 出現，`~/.claude/skills/foo` 消失。
4. 衝突路徑：在 `dest` 預先放不同內容 → 不帶 `--force` 應 exit 非 0、保留原狀；帶 `--force` → 內容被覆蓋成 agent 端的版本。
5. README 範例同步檢查：`grep -n "global archive" README.md` 比對措辭是否與新行為一致。
