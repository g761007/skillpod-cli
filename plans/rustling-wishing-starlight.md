# Plan: skillpod add — 對齊 `npx skills add` 的 6 種 source 格式

## Context

`skillpod add <SOURCE>` 目前已能接受 6 種 source 格式中的 5 種，但有兩個問題促成這次工作：

1. **Deep tree URL 完全不支援。** `https://github.com/owner/repo/tree/<branch>/<subpath>` 會被原封不動丟給 `git clone`，GitHub 對該路徑回 404 → `GitOperationError`。`SourceSpec` 與 `SourceEntry` 都沒有 `subpath` 欄位，整條 install pipeline 沒有把「repo 內子目錄」當成獨立 source root 的概念。
2. **其餘 5 種格式雖然能跑卻沒被文件化、也缺端對端測試。** README §71-100 只列「git URL / owner/repo / local path」三種；GitLab、SCP `git@…:…`、`ssh://`、`https://…/…git` 雖然在 `parse_source_spec` 與 `parse_repo_url` 都被涵蓋，但完全沒有 CLI 端對端測試。

預期成果：`skillpod add` 對 `npx skills add` 列出的 6 種輸入形式行為一致；deep tree URL 直接安裝該 sub-tree 為單一 source；README 與測試把整套契約鎖定。

## Format gap matrix (after exploration)

| # | 輸入格式 | 現狀 | 是否動到實作 |
|---|---|---|---|
| 1 | `vercel-labs/agent-skills` (shorthand) | ✅ 已支援 | 否，僅補 README |
| 2 | `https://github.com/owner/repo` | ✅ 已支援 | 否，僅補 README |
| 3 | `…/tree/<ref>/<subpath>` (deep tree URL) | ❌ **完全壞** | **是 — 主軸** |
| 4 | `https://gitlab.com/org/repo` | ✅ 已支援 (`parse_repo_url` host-agnostic) | 否，補單元 + 端對端測試 + README |
| 5 | `git@github.com:org/repo.git` (SCP) / `ssh://…` | ✅ 已支援 | 否，僅補 README |
| 6 | `./local/path`, `~/path`, `/abs` | ✅ 已支援 | 否 |

## Design

### Subpath 的資料模型

選定方案：**把 subpath 視為 source root**。

- `SourceSpec` 與 `SourceEntry` 各加一個 `subpath: str | None`（git-only，local source 禁止設定）。
- `_fetch_source` 仍 clone 整個 repo 到 `~/.cache/skillpod/<host>/<owner>/<repo>@<sha>/`（cache key 不變，多個 subpath 共用同一份 clone），但回傳 `cache_root / subpath` 給 discovery 與 installer 使用。
- `skillfile.yml` 同時持久化 `url:`、`ref:`、`subpath:`，未來 `skillpod install` 走 `resolve_git` 重建時才能找回正確的 sub-tree。
- Lockfile 不變：sha256 已涵蓋實際安裝的 tree，subpath 為隱含資訊。

### Deep URL parser

新增一條規則放在 `parse_source_spec` 既有 `://` 通用分支**之前**，只攔截 `(http|https)://<host>/<owner>/<repo>` 後面接 `/tree/` 或 `/-/tree/`（GitLab 是 `/-/tree/`、GitHub 是 `/tree/`、Bitbucket 是 `/src/`）的 URL。`/blob/` 也接（指向單一檔案時退化為其父目錄）。

匹配後拆出：
- `clone_url` = `https://<host>/<owner>/<repo>` (`.git` 統一去掉)
- `ref` = path 第一段
- `subpath` = path 其餘段（為空時等同沒給）
- `derived_name` = subpath 末段；若 subpath 為空則回退 `repo`

不在 deep parser 命中的 `://` URL 仍照舊走 generic 分支，確保 ssh / git / file URL 不受影響。

## Files to modify

| 檔案 | 變動 |
|---|---|
| `src/skillpod/sources/spec.py` | (1) `SourceSpec` 加 `subpath: str | None = None`；(2) `parse_source_spec` 新增 deep URL 分支；(3) helper `_parse_deep_url(text) -> tuple[url, ref, subpath, name] | None`。 |
| `src/skillpod/manifest/models.py:75` | `SourceEntry` 加 `subpath: str | None = None`，validator 補：`type=local` 不得設 `subpath`。 |
| `src/skillpod/cli/commands/add.py:110` (`_fetch_source`) | git 分支於 `populate_cache` 後 `root = repo_root / spec.subpath if spec.subpath else repo_root`；缺漏時 `raise FileNotFoundError(f"subpath … does not exist at …@<commit>")`. |
| `src/skillpod/cli/commands/add.py:264` (`_ensure_source_and_skills`) | `new_source["subpath"]` 於 `spec.subpath` 非 `None` 時寫入；`_find_matching_source` 對 git source 比對 `(url, subpath)` 二元組。 |
| `src/skillpod/sources/git.py:126` (`resolve_git`) | 在計算 `skill_dir` 前先把 `repo_root` 換成 `repo_root / source.subpath`（若有），再走原本的 `<root>/<skill_name>/` + 根目錄 SKILL.md fallback。 |
| `src/skillpod/installer/global_install.py` | 與 `_fetch_source` 同步：global install 也尊重 `spec.subpath`。 |
| `tests/_git_fixtures.py` | 新增 `make_multi_skill_repo(parent, repo_name, skills: list[str], subdir="skills")`：建一個含多個 `skills/<name>/SKILL.md` 的 bare repo，回傳遠端 URL（`file://…`）+ commit。 |
| `tests/test_sources_spec.py` | parametric 新增：(a) GitHub `/tree/main/foo`；(b) GitHub `/tree/main/foo/bar`（多段 subpath）；(c) GitLab `/-/tree/main/foo`；(d) `/tree/<ref>` 不含 subpath（subpath=None，ref 仍取出）；(e) `/blob/` 視同 `/tree/`；(f) `derived_name` 為 subpath 末段。 |
| `tests/test_sources.py` | 新增 `parse_repo_url` 對 `https://gitlab.com/org/repo` → `("gitlab.com", "org/repo")` 的 case；`resolve_git` 帶 `subpath` 的整合測試（用 `make_multi_skill_repo`）。 |
| `tests/test_cli_add_source.py` | 新增兩個端對端測試：① 用 `make_multi_skill_repo` 的 file:// URL 直接走 `_fetch_source`/`discover_skills` 流程，模擬 deep-tree-URL 的 subpath 行為（注入 SourceSpec 已含 `subpath`），驗證只裝該子 skill、`skillfile.yml` 內 `subpath:` 正確、CLI 重跑為 idempotent；② host-agnostic add：用一個 `https://gitlab.example.test/...` 形式 URL（搭配 `monkeypatch` 改寫 `_run_git` 把 clone 重定向到 bare repo 的 file 路徑），驗證 cache 路徑落在 `gitlab.example.test/...`、安裝成功。 |
| `README.md:71-100` | 改寫「Adding skills from a git source」段落：列出 6 種格式範例（含 deep tree URL、GitLab、SCP、`./` local），說明 `--ref` 預設自動偵測、deep URL 內已含 ref 時 `--ref` 仍可覆寫。 |

## Reuse map（避免重造輪子）

- `cache_mod.parse_repo_url` (cache.py:35) 已是 host-agnostic，**不需動**。
- `resolve_default_branch` (git.py:65)、`resolve_ref` (git.py:53)、`populate_cache` (git.py:89) 全部沿用，subpath 只在「fetch 之後」才介入。
- `discover_skills(root, root_name=...)` 已支援自訂 root 與 root-is-skill 偵測 (discovery.py:64)，subpath 後的子目錄如果只放一個 SKILL.md 會被當 root-is-skill 處理；多個 SKILL.md 也照常 walk。
- `derive_unique_name` (spec.py:116) 沿用，當兩個 source 來自同 repo 但不同 subpath 時會產生 `agent-skills`、`agent-skills-2` 之類唯一名。
- `_StrictModel` Pydantic 設定保留 `extra="forbid"`，新欄位需顯式宣告。

## Verification

### 自動化測試
```bash
uv sync
uv run pytest tests/test_sources_spec.py -v          # parser parametric
uv run pytest tests/test_sources.py -v               # parse_repo_url + resolve_git subpath
uv run pytest tests/test_cli_add_source.py -v        # CLI 端對端
uv run pytest -q                                     # full sweep
uv run ruff check src tests
uv run mypy src/skillpod
```

### 手動煙霧測試
```bash
# 1) Deep tree URL（單一 skill 從 monorepo 子目錄安裝）
cd /tmp/test-skillpod && uv run skillpod init
uv run skillpod add https://github.com/anthropics/skills/tree/main/skills/skill-creator -y
# 預期：.skillpod/skills/skill-creator/SKILL.md 存在；skillfile.yml 內
#       sources: [{name: skills, type: git, url: https://github.com/anthropics/skills,
#                  ref: main, subpath: skills/skill-creator, priority: 50}]

# 2) GitLab URL
uv run skillpod add https://gitlab.com/<a-real-skill-repo> -l
# 預期：列出 SKILL.md 而不是 GitOperationError；cache 路徑落在 ~/.cache/skillpod/gitlab.com/...

# 3) SCP URL
uv run skillpod add git@github.com:vercel-labs/agent-skills.git -l

# 4) 本地路徑（含 ~ 展開）
uv run skillpod add ./tests/fixtures/example -l
```

### 完工判準
- 6 種輸入格式皆有測試覆蓋（5 種至少 spec parser 級，3、4 兩種另含端對端）。
- README 範例與實作行為一致。
- `pytest`、`ruff`、`mypy` 全綠。
- 既有 21 個 `test_cli_add_source` 測試與 root-is-skill 行為不退化。
