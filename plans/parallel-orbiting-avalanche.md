# 修正 `skillpod add owner/repo` — repo 根目錄即為 skill 本體

## Context

當使用者執行 `skillpod add owner/repo`（例如 `skillpod add anthropics/some-single-skill`）且未指定 `-s/--skill`，目前程式碼期望在 repo 中尋找 *子目錄*形式的 skill。然而，許多公開 repository（如官方 Anthropic 範例、單一 skill 專案）會把 `SKILL.md` 直接放在 **repo 根目錄**——也就是「整個 repo 本身就是一個 skill」。

目前的程式碼有兩個缺陷導致此情境壞掉：

1. **Discovery 名稱依賴 cache 目錄 basename**
   `discover_skills(repo_root)` 對 root-is-skill 時回傳 `name = repo_root.name`。
   git source 的 `repo_root` 為 `~/.cache/skillpod/<host>/<org>/<repo>@<commit>/`，因此 `repo_root.name == "<repo>@<commit>"`——一個含 commit SHA 的醜名稱，且**會隨 commit 變動**（manifest 寫入後在下次 `install` 會找不到）。
   👉 證據：`src/skillpod/sources/discovery.py:78`、`src/skillpod/sources/cache.py:67`。

2. **Project 安裝路徑無法解析 root-is-skill**
   `resolve_git(skill_name, source)` 永遠執行 `skill_dir = repo_root / skill_name`，當 skill 是 repo 根目錄時這個 path 不存在，於是丟出 `SourceError`。
   👉 證據：`src/skillpod/sources/git.py:115-120`。

而 *global* 路徑（`-g`）已經透過 `skill.rel_path == "."` 在 `install_global()` 內正確處理（`src/skillpod/installer/global_install.py:108`），但會繼承缺陷 #1 的醜名稱。

預期成果：使用者執行 `skillpod add owner/repo -y`（或 `-g`）時，
- 若 repo 根有 `SKILL.md`，自動以 `derived_name`（即 `repo` 部分）作為 skill name，將整個 repo 視為一個 skill 安裝。
- `.skillpod/skills/<derived_name>/` 與 fan-out 目錄正常產生。
- 子目錄式多 skill repo 行為不變。

## Fix Scope

只動 git source 的處理（local source 的 `resolve_local` 不受影響），與既有 0.5.3 「install root materialised as real-directory copy」修正並列為 0.5.4 的 bugfix。

## Implementation Plan

### 1. Discovery：允許 root-is-skill 改用呼叫端指定的名稱

**File**: `src/skillpod/sources/discovery.py`

- 修改 `discover_skills(root: Path) -> list[DiscoveredSkill]`，新增 keyword-only 參數
  `root_name: str | None = None`。
- `root_name` 僅影響 root-is-skill 分支（`discovery.py:74-83`）：
  - 若 `root_name` 提供 → 用它作為 `DiscoveredSkill.name`
  - 否則維持現行 `root.name` 行為（向後相容）。
- 子目錄 skill（`rel_path != "."`）一律維持以子目錄 basename 為名。

**Why**: 把「呼叫端知道的合適名稱」（CLI 來自 `spec.derived_name`、tests 可自由覆蓋）注入 discovery，避免 discovery 與 cache 目錄佈局耦合。

### 2. CLI：在 source-mode 把 `derived_name` 傳給 discovery

**File**: `src/skillpod/cli/commands/add.py:538`

```python
discovered = discover_skills(root, root_name=spec.derived_name)
```

對 `parse_source_spec` 而言：
- `owner/repo` → `derived_name="repo"`
- `https://github.com/owner/repo.git` → `derived_name="repo"`
- 本地 path `/path/to/foo` → `derived_name="foo"`

### 3. Resolver：root-is-skill fallback

**File**: `src/skillpod/sources/git.py:113-120`

在 `resolve_git()` 計算 `skill_dir = repo_root / skill_name` 之後，新增 fallback：

```python
skill_dir = repo_root / skill_name
if not skill_dir.is_dir():
    # Root-is-skill：repo 整個就是 skill，沒有子目錄
    if (repo_root / "SKILL.md").is_file():
        skill_dir = repo_root
    else:
        raise SourceError(
            f"git source {source.name!r}: skill {skill_name!r} not present at "
            f"{source.url}@{commit} (looked for {skill_dir} or {repo_root}/SKILL.md)"
        )
```

**Why**: install pipeline 由 manifest 驅動（`SkillEntry.name`），即使 add 時就把 `name=spec.derived_name` 寫入 manifest，下次 `skillpod install` 還是會走 `resolve_from_sources → resolve_git`，必須能用 `skill_name` 找到 `repo_root` 本身。

**Risk 評估**：fallback 仍要求 `repo_root/SKILL.md` 存在；不會把任意未知 skill 名稱錯認為根 skill。如果 repo 既有根 `SKILL.md` 又有子目錄 skill，且使用者手動把 manifest 改成不存在的名字，fallback 會把它解析成根 skill——這是極端 corner case，可在後續以 `subpath:` 顯式欄位處理（不在本次 scope）。

### 4. Tests — 新增 root-is-skill 端到端覆蓋

**File**: `tests/_git_fixtures.py`

新增 helper（保持 `make_skill_repo` API 不破壞）：
```python
def make_root_skill_repo(parent, *, repo_name="single-skill",
                        skill_files=None, branch="main") -> tuple[Path, str]:
    """建立 repo 根目錄即為 skill（SKILL.md 在 repo 頂層）的 git fixture。"""
```

**File**: `tests/test_discovery.py`
- 新測試 `test_discover_uses_root_name_override`：root SKILL.md + `root_name="custom"` → `name == "custom"`、`rel_path == "."`，並確認預設行為（不傳 `root_name`）仍維持 `name == tmp_path.name`。

**File**: `tests/test_sources.py`（如未存在則放在 `tests/test_cli_add_source.py`）
- 新測試 `test_resolve_git_falls_back_to_root_when_repo_is_skill`：使用 `make_root_skill_repo` 建 git repo，`resolve_git("anything", source)` 在 root SKILL.md 存在時回傳 `repo_root`。
- 新測試 `test_resolve_git_still_errors_when_no_skill_anywhere`：repo 根與子目錄皆無 SKILL.md → 仍丟 `SourceError`。

**File**: `tests/test_cli_add_source.py`
- 新測試 `test_source_mode_root_is_skill_installs_under_derived_name`：
  - 用 `make_root_skill_repo(repo_name="vibe")` 建 git repo。
  - 執行 `skillpod add <file:// repo path> -y`（或讓 `parse_source_spec` 走 file:// path）。
  - 斷言 `.skillpod/skills/vibe/SKILL.md` 為 real dir，`.claude/skills/vibe` 也存在。
  - 斷言 manifest 寫入 `name: vibe` 與單一 source。
- 新測試 `test_source_mode_root_is_skill_global_uses_derived_name`：
  - `-g -y` 模式下 `~/.skillpod/skills/vibe/` 為 real dir，名稱不含 `@<commit>`。

### 5. Docs

**File**: `README.md` Roadmap section
- 在 v0.5.3 之後新增 v0.5.4 條目（或在現有 0.5.3 補一行 highlight，視 release cadence 而定），描述：
  「`skillpod add owner/repo` 支援 repo 根目錄即為 skill 的 single-skill repository」。

**File**: `CHANGELOG.md`
- 新增 0.5.4（或 unreleased）區塊：`Fixed: skillpod add <git source> now installs single-skill repos whose SKILL.md sits at the repo root, using the URL-derived name instead of the cache directory basename.`

## Critical Files

| File | 變更 |
|---|---|
| `src/skillpod/sources/discovery.py` | 新增 `root_name` 參數 |
| `src/skillpod/cli/commands/add.py` (L538) | 傳 `root_name=spec.derived_name` |
| `src/skillpod/sources/git.py` (L113-120) | root-is-skill fallback |
| `tests/_git_fixtures.py` | 新 `make_root_skill_repo` helper |
| `tests/test_discovery.py` | 新 root_name override 測試 |
| `tests/test_cli_add_source.py` | 新端到端測試（project + global） |
| `README.md` / `CHANGELOG.md` | Roadmap / changelog 條目 |

## Reused / Existing Patterns

- `DiscoveredSkill.rel_path == "."` 已是 root-is-skill 的訊號（`discovery.py:80`、`global_install.py:108`），fix 沿用此語義。
- `parse_source_spec` 的 `derived_name` 已涵蓋所有形態（`owner/repo`、URL、SCP、`.git`、本地 path），可直接複用作為 root skill 名稱。
- 既有測試 `test_discover_treats_root_as_single_skill`（`tests/test_discovery.py:51`）確認 discovery 已支援 root-as-skill；本次只是讓 *呼叫端能控名稱*。
- 既有 `_materialise_install_root`（fanout 與 global_install）對 real-directory 拷貝的語義不需更動。

## Verification

1. **單元測試**：
   ```bash
   uv run pytest tests/test_discovery.py tests/test_cli_add_source.py -x
   ```
2. **完整測試 + 型別 + lint**：
   ```bash
   uv run pytest -x
   uv run mypy src
   uv run ruff check src tests
   ```
3. **手動 smoke**（使用本地 fixture，避免污染真實 GitHub 流程）：
   ```bash
   # 建立 root-is-skill 的本地 repo
   mkdir -p /tmp/single && cd /tmp/single && git init -q -b main \
     && printf -- "---\ndescription: demo\n---\n# demo\n" > SKILL.md \
     && git add . && git commit -q -m init
   # 用本地 repo 走 git source 流程
   cd /tmp && rm -rf demo-proj && mkdir demo-proj && cd demo-proj
   skillpod init -y
   skillpod add file:///tmp/single -y
   ls -la .skillpod/skills .claude/skills    # 應看到 single 目錄
   cat skillfile.yml                          # name: single, type: git, url: file:///tmp/single
   ```
4. **回歸覆蓋**：確認 `test_source_mode_adds_source_and_installs_selected`、`test_source_mode_global_installs_with_fanout`、`test_global_install_survives_cache_prune` 等既有多 skill 測試仍綠。

## Out of Scope

- 不引入 `SkillEntry.subpath` / `SourceEntry.subpath` schema 欄位（先以 root-is-skill fallback 解決使用者實際痛點，schema 修改留給後續 0.6 規劃）。
- 不調整 local source 的 `resolve_local` 邏輯——現有 CLI 在 local source 也走相同 discovery，但 `resolve_local` 的單一 skill 行為使用者目前未提出問題，避免 scope creep。
- 不改 `parse_source_spec` 的 `derived_name` 計算（已正確）。
