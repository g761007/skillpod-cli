# `~/.skillpod/skills/` 與 `<project>/.skillpod/skills/` 改為實體 copy（不再 symlink 進 cache）

## Context

目前 skillpod 的 install root（`<project>/.skillpod/skills/<name>/` 與 `~/.skillpod/skills/<name>/`）一律是 **symlink**，指向：
- Git source：`~/.cache/skillpod/<host>/<org>/<repo>@<commit>/<rel_path>/`
- Local source：使用者本地路徑

這代表只要使用者執行 `rm -rf ~/.cache/skillpod`、清掉 mac 上久未使用的暫存，或 cache 路徑被工具自動整理，所有的 skillpod skill 立刻變成 dangling symlink。Agent fan-out（`~/.<agent>/skills/<name>` symlink → install root → cache）會跟著一起壞。

目標：把 install root 改為**實體目錄（`shutil.copytree` 複製內容）**，讓 install root 自我含括，cache 是純粹的下載暫存而非執行依賴。Fan-out（`~/.<agent>/skills/<name>`）則維持 symlink 指向 install root —— 因為 install root 已是實體，fan-out symlink 不再經 cache，cache 清掉也不影響。

範圍：global（`~/.skillpod/skills/`）與 project-local（`<project>/.skillpod/skills/`）皆修。

---

## Recommended approach

把兩個負責建 install root 的函式從 `symlink` 改成 `copytree`，並加上 hash-based idempotency 讓重跑安裝不會被「資料夾已存在」擋下。

### 行為規格（兩處共用語意）

對 install root path（`<root>/.skillpod/skills/<name>/`）做 materialise 時：

| 既有狀態 | 行為 |
|---|---|
| 不存在 | `mkdir(parents=True)` + `shutil.copytree(source_dir, link, symlinks=False)` |
| 是 symlink（legacy 安裝） | `unlink()` → 視同「不存在」 → 走 copytree |
| 是 broken symlink（cache 已清） | `unlink()` → copytree |
| 是實體目錄，內容雜湊 = source 雜湊 | **idempotent skip**（不寫、不報錯） |
| 是實體目錄，內容雜湊 ≠ source | 預設 `InstallConflict`；`force=True` → `rmtree` + copytree |

雜湊用既有 `hash_directory()`（`src/skillpod/lockfile/integrity.py:34`），它本就在 pipeline 後段被呼叫做 frozen-drift check，型別與穩定性已驗證。

### 為什麼 fan-out 維持 symlink

修完之後 `~/.skillpod/skills/<name>/` 是實體目錄，所以 `~/.<agent>/skills/<name>` symlink → 實體目錄，cache 清掉與此 symlink 無關。`is_managed_fanout()`（`installer/paths.py:43-68`）只檢查 immediate target 是否落在 `.skillpod/skills/` 之內，不需修改。

---

## Files to modify

### 1. `src/skillpod/installer/global_install.py`
**核心修改處**。

- 把 `_replace_with_symlink()`（行 129-150）改名 `_materialise_install_root()`，內部從 `link.symlink_to(target)` 換成下面流程：
  1. 若 `link.is_symlink()` → `link.unlink()`（含 broken symlink 由 `is_symlink()` 為 True 涵蓋；若 `exists()` 為 False 也照樣 unlink）。
  2. 若 `link` 是實體目錄 → 算 `hash_directory(link)` vs `hash_directory(source)`：
     - 相同 → return（idempotent）。
     - 不同 → 沒 `force` 拋 `InstallConflict`；有 `force` 先 `shutil.rmtree(link)`。
  3. `link.parent.mkdir(parents=True, exist_ok=True)`，呼叫 `IdentityAdapter().adapt(skill_name=skill.name, source_dir=source, target_dir=link, mode=InstallMode.COPY)`（重用既有 adapter，不要直接 import shutil）。
- `install_global()`（行 63-126）內 `_replace_with_symlink(install_link, skill_source_dir, force=force)`（行 102）改呼新名稱，並把 `skill.name` 一起傳進去。
- 既有的「skipped because identical content」可加進 `GlobalInstalledSkill`（或保留靜默 skip，文件只說 idempotent 即可）。

### 2. `src/skillpod/installer/fanout.py`
- `create_install_root_symlink()`（行 59-83）改名 `materialise_install_root()`，並把開頭 docstring（行 6-8 `... is always symlink-only ...`）整段重寫成「always real-directory copy」。
- 函式內部把 `_create_symlink(link, target)` 換成 `IdentityAdapter().adapt(... mode=InstallMode.COPY)`，並加上前述 hash idempotency 與 `force` 參數。
- 為與 global 端一致，新增 `force: bool = False` 參數（pipeline 呼叫端傳 `force=False`，將來若需要 `--force` 可一致開放）。
- `__all__` 同步。

> 注意：`_create_symlink` 仍被 `create_managed_fanout_symlink` 用，**不要刪掉**。

### 3. `src/skillpod/installer/pipeline.py`
- 行 200 `create_install_root_symlink(skill_link, resolved.path, record=record)` 改成 `materialise_install_root(skill_link, resolved.path, record=record, skill_name=resolved.name)`（依 fanout.py 的新簽名）。
- 行 204 的 `hash_directory(skill_link)` 不需動 —— 路徑現在是實體目錄，雜湊行為等價（既有 frozen-drift 檢查持續可用）。

### 4. `src/skillpod/installer/paths.py`
- `is_managed_fanout()`（行 43-68）邏輯不需改：fan-out symlink 仍指向 `.skillpod/skills/<name>`（只是 leaf 從 symlink 變實體目錄），immediate-parent canonical 比對仍正確。
- 不變動。

### 5. Tests — 修改既有 assertion
| 檔案 | 行 / 測試名 | 修改 |
|---|---|---|
| `tests/test_cli.py` | 86-87, 99-100 `test_install_creates_symlinks` | 重命名 `test_install_creates_real_dir_with_fanout_symlinks`；assert `.skillpod/skills/audit` `.is_dir()` 且 **非** `.is_symlink()`；fan-out `.claude/skills/audit` 仍 `.is_symlink()` 指向 `.skillpod/skills/audit` |
| `tests/test_installer.py` | 83, 86-90 `test_local_skill_materialised_and_fanned_out` | 同上：install root 改驗實體目錄；fan-out symlink 解析後落點仍正確 |
| `tests/test_cli_add_source.py` | 391, 412-413 | `~/.skillpod/skills/pdf` 改驗 `.is_dir()` 非 symlink；多 agent fan-out 仍是 symlink |
| `tests/test_adapters.py` | 12-22 | adapter 本身語意不變，無需改 |
| `tests/test_installer.py` | 702-744 `test_symlink_failure_falls_back_to_copy` | 該測試針對 fan-out（`materialise_fanout`）符號連結失敗的 fallback chain，install root 與此無關。**保留** |

### 6. Tests — 新增防回歸測試
新增於 `tests/test_installer.py`：

- `test_install_root_survives_cache_prune`：完成 `install` 後 `shutil.rmtree(cache_dir)`，assert `.skillpod/skills/<name>/SKILL.md` 仍可讀、agent fan-out 解析後檔案仍存在。**這是本次修復的核心驗證**。
- `test_repeated_install_is_idempotent_real_dir`：同一 commit 連跑兩次 `install`，第二次不應 raise、不應重新 copy（可用 `mtime` 或 hook 驗證；最低限度驗證不報錯）。
- `test_install_root_legacy_symlink_is_replaced`：手動把 `<project>/.skillpod/skills/<name>` 預先建成 symlink（模擬舊版升級情境），再跑 `install`，應自動轉為實體目錄。

新增於 `tests/test_cli_add_source.py`：

- `test_global_install_survives_cache_prune`：對應 global 路徑的 cache prune 測試。

### 7. README.md
- 搜「symlink」與「.skillpod/skills」相關段落，描述更新為「`.skillpod/skills/<name>/` 為實體目錄，cache 是純下載暫存，可安全清除」。

### 8. CHANGELOG.md
- `Unreleased` 下新增：
  > **Changed**: `.skillpod/skills/<name>/` 與 `~/.skillpod/skills/<name>/` 現在是實體目錄（先前為 symlink 進 `~/.cache/skillpod/`）。修復清除 cache 後 skill 全部失效的問題。重跑 install 為 idempotent；若實體目錄內容與 source 不一致，需加 `--force` 覆寫。

---

## 重用的既有 utilities（不要重寫）

| 用途 | 既有 helper | 路徑 |
|---|---|---|
| 實體 copy materialisation | `IdentityAdapter.adapt(... mode=InstallMode.COPY)` | `src/skillpod/installer/adapter_default.py:53-60` |
| 內容雜湊比對 | `hash_directory(path)` | `src/skillpod/lockfile/integrity.py:34` |
| 衝突錯誤型別 | `InstallConflict`, `InstallSystemError` | `src/skillpod/installer/errors.py` |
| 解出 install root | `project_skill_dir`, `global_skill_dir` | `src/skillpod/installer/paths.py:12, 32` |
| Rollback 紀錄 | `record(path)` from `rollback_on_failure()` | `src/skillpod/installer/fanout.py:27-48` |

---

## Edge cases 與安全保險

- **Broken symlink**（cache 已清的舊安裝）：`is_symlink()` 會回 True、`exists()` 會回 False；先 `unlink` 再走 copy 路徑，沒有特例。
- **Source path 不存在**：`shutil.copytree` 會直接拋 `FileNotFoundError`；包成 `InstallSystemError`，與既有 `_materialise_agent_link` 的 OSError 包裝保持一致。
- **Rollback**：`record(link)` 仍照舊；`rollback_on_failure` 已支援 `path.is_dir()` 分支（行 43-47），實體目錄回滾用 `shutil.rmtree(..., ignore_errors=True)`。
- **Pipeline 行 204 `hash_directory(skill_link)`**：對實體目錄與 symlink 行為一致（`integrity.py:25` 用 `rglob`，會跟隨 symlink 路徑），既有 frozen-drift 檢查不需動。
- **磁碟空間**：兩處從 link 變 copy，每個 skill 多佔約 ~1×size。若使用者擔心，cache 仍然可清除（cache 與 install root 不再耦合，這是修復的副作用）。
- **`source_dir` mutation 檢查**（pipeline 行 212, 232）：adapter contract 仍要求不寫 source。改 copy 後 source 是 cache，adapter 一樣不會寫，檢查保持有效。

---

## Verification

1. **新增 cache-prune 測試**：
   ```bash
   uv run pytest tests/test_installer.py::test_install_root_survives_cache_prune -v
   uv run pytest tests/test_cli_add_source.py::test_global_install_survives_cache_prune -v
   ```

2. **既有測試**（會抓到 symlink → 實體目錄的 assertion 變更）：
   ```bash
   uv run pytest tests/test_cli.py -v
   uv run pytest tests/test_installer.py -v
   uv run pytest tests/test_cli_add_source.py -v
   ```

3. **全套**：
   ```bash
   uv run pytest
   ```

4. **手動 smoke**（驗證真實工作流）：
   ```bash
   tmp=$(mktemp -d) && cd "$tmp" && \
     uv run skillpod init && \
     uv run skillpod add some-git-source -s some-skill && \
     uv run skillpod install && \
     test ! -L .skillpod/skills/some-skill && test -d .skillpod/skills/some-skill && \
     rm -rf ~/.cache/skillpod && \
     test -f .skillpod/skills/some-skill/SKILL.md && echo "OK: cache prune does not break install root"
   ```

5. **Global 路徑手動 smoke**：
   ```bash
   tmp_home=$(mktemp -d) && \
     HOME="$tmp_home" SKILLPOD_CACHE_DIR="$tmp_home/cache" \
       uv run skillpod add ./examples/some-source -s pdf -g && \
     test ! -L "$tmp_home/.skillpod/skills/pdf" && test -d "$tmp_home/.skillpod/skills/pdf" && \
     rm -rf "$tmp_home/cache" && \
     test -f "$tmp_home/.skillpod/skills/pdf/SKILL.md" && echo "OK: global cache prune does not break install root"
   ```

6. **Type check + lint**：
   ```bash
   uv run mypy src/
   uv run ruff check src/ tests/
   ```
