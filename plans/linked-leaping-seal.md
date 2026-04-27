# skillpod-cli 公開發佈準備計畫

## Context

skillpod-cli 已完成 0.1.0 → 0.4.0 全部 4 個 Roadmap 里程碑（manifest/lockfile/installer、trust/search、groups、adapter layer），14 個 CLI subcommand 全部實作完成且有測試與 CI。但目前處於「程式碼可用、發行品包裝缺失」的狀態：

- `pyproject.toml` 版本仍為 `0.1.0.dev0`，與 git log 中 0.4.0 的成果脫鉤
- 沒有 `LICENSE` 檔案（雖宣告 MIT）
- 沒有 PyPI 必備的 metadata（License/OS/Topic classifiers、project URLs、long-description content type）
- 沒有 `py.typed`、CHANGELOG、CONTRIBUTING、SECURITY 等社群檔案
- 沒有 git remote、沒有 PyPI publish workflow
- README 過於精簡，缺 logo 與功能展示
- 4 個已實作的 OpenSpec 變更尚未 archive

目標：完成首次公開發佈 (PyPI + GitHub)，並將品牌資產（logo）就位。

**已確認決策**（依使用者回覆）：
- 首發版本：**0.5.0**（把所有公開準備工作視為新 release，0.4.0 留作未發佈的內部里程碑）
- 分支：本地 `master` → 改名為 `main`，同步更新 CI badge
- Logo：用 huashu-design skill 生 3 個方向供選
- PyPI 發佈：採 Trusted Publisher (OIDC)，免 token
- GitHub repo：**`g761007/skillpod-cli`**（pyproject 原本誤填 `danielhsieh`，要一併修正）

**重要 gate**：Phase 7（推 GitHub）與 Phase 8（PyPI 發佈）**必須等使用者明確指示「可以發佈」才執行**。Phase 1–6 可逕行進行。

---

## Phase 1 — 版本與 OpenSpec 對齊（Code-only，無外部副作用）

**為什麼先做**：版本號與已歸檔狀態錯亂會讓 PyPI 釋出與 GitHub release 對不上 commit。

1. 首發版本確定為 **`0.5.0`**：把「公開發佈準備」視為一次新 release，0.4.0 留作 git 歷史中的未發佈里程碑。
2. 修改 `pyproject.toml`：
   - `version = "0.5.0"`
3. 用 OpenSpec workflow 把 4 個 changes archive 到 `openspec/changes/archive/`：
   - `add-skillpod-mvp-install`
   - `add-skillpod-trust-and-search`
   - `add-skillpod-groups`
   - `add-skillpod-adapter-layer`
   - 使用 `openspec-bulk-archive-change` skill 一次處理。
4. 新增 `CHANGELOG.md`（Keep a Changelog 格式），補齊 0.1.0 → 0.4.0 內部里程碑的條目，並把 0.5.0 標為「首次 PyPI 公開發佈 + packaging hardening」。

**關鍵檔案**：
- `pyproject.toml`
- `CHANGELOG.md`（新增）
- `openspec/changes/**` → `openspec/changes/archive/**`

---

## Phase 2 — Packaging Metadata 完整化

**為什麼**：PyPI 列表頁的呈現與 pip 安裝體驗取決於這些欄位，缺漏會讓專案看起來不專業且影響可發現性。

修改 `pyproject.toml`：

```toml
[project]
license = { file = "LICENSE" }   # 改為檔案指向
classifiers = [
  "Development Status :: 4 - Beta",   # 由 Alpha 升 Beta（0.4.0 已成熟）
  "License :: OSI Approved :: MIT License",
  "Operating System :: OS Independent",
  "Topic :: Software Development :: Build Tools",
  "Topic :: System :: Software Distribution",
  "Intended Audience :: Developers",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
]

[project.urls]
Homepage = "https://github.com/g761007/skillpod-cli"
Repository = "https://github.com/g761007/skillpod-cli"
Issues = "https://github.com/g761007/skillpod-cli/issues"
Changelog = "https://github.com/g761007/skillpod-cli/blob/main/CHANGELOG.md"
```

新增檔案：
- `LICENSE` — MIT 全文（作者：Daniel Hsieh）
- `src/skillpod/py.typed` — 空檔，供 PEP 561 類型分發
- `MANIFEST.in`（或在 `pyproject.toml` 用 `[tool.hatch.build]` 指定）— 確保 README、LICENSE、CHANGELOG、`examples/`、`openspec/` 隨 sdist 分發

**關鍵檔案**：
- `pyproject.toml`
- `LICENSE`（新增）
- `src/skillpod/py.typed`（新增空檔）

---

## Phase 3 — 社群與貢獻文件

**為什麼**：開源專案被外部使用者第一次造訪時，這些檔案決定他們是否願意提交 issue/PR。

新增最小可行版本：
- `CONTRIBUTING.md` — 開發環境（`uv sync`、`uv run pytest`）、commit message 風格、PR 流程、OpenSpec 工作流連結
- `SECURITY.md` — 回報資安漏洞的私訊管道（email 或 GitHub Security Advisory）
- `.github/ISSUE_TEMPLATE/bug_report.yml`、`feature_request.yml`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `CODE_OF_CONDUCT.md`（建議採用 Contributor Covenant 2.1）

---

## Phase 4 — Logo 與品牌

**為什麼**：使用者在 README、PyPI、社群分享時對 logo 印象深刻；huashu-design skill 可一次產出多個方向。

呼叫 `huashu-design` skill：
- 主題：「pod-style dependency manager for AI coding agent skills」
- 風格輸入：請使用者選擇方向（minimal monogram / mascot / abstract glyph）
- 產出：SVG + PNG（256x256, 1024x1024）、深淺底版本
- 放置位置：`docs/assets/logo.svg`、`docs/assets/logo-dark.svg`、`docs/assets/logo-light.svg`

---

## Phase 5 — README 重寫

**為什麼**：目前的 README 仍以 「pre-release / planned」 描述，但實際上 14 個 CLI 都已可用。新版 README 是 PyPI 頁面與 GitHub 首頁的唯一門面。

新版結構：
1. Logo（HTML `<p align="center">` 置中）
2. 一句話 tagline + badges：CI、PyPI version、Python versions、License、（可選）downloads
3. **Why skillpod**：3 句話講清楚 vs. 全域 skill installer 的差異
4. **Installation**：`pip install skillpod` / `uv tool install skillpod`
5. **Quickstart**：實際可跑的 `init → add → install → list` 範例（含螢幕截圖或 asciinema GIF）
6. **How it works**：`.skillpod/skills/` 集中存放 + 多 agent symlink fan-out 的圖示
7. **Configuration**：`skillfile.yml` 範例（連到 `examples/`）+ `groups`、`user_skills`、`adapters` 的精簡說明
8. **Commands cheatsheet**：14 個 subcommand 一覽表
9. **Roadmap & Status**：連到 `openspec/` 與 `CHANGELOG.md`
10. **Contributing / License**

**關鍵檔案**：`README.md`

---

## Phase 6 — CI/CD 強化

**為什麼**：目前 CI 只跑 Linux + 沒跑 mypy + 沒有 publish workflow。要支援 PyPI 自動發佈與跨平台保證。

修改 `.github/workflows/ci.yml`：
- 加入 `os: [ubuntu-latest, macos-latest, windows-latest]` 矩陣（Windows 在 0.4.0 adapter layer 為已知 deferred，可先標 `continue-on-error: true`）
- 加入 `uv run mypy` 步驟（pyproject 已啟用 strict）
- 加入 Python 3.13

新增 `.github/workflows/release.yml`：
- 觸發：push tag `v*`
- 流程：`uv build` → `uv publish` 用 PyPI Trusted Publisher (OIDC，免 token)
- 發 GitHub Release，內容自動帶 `CHANGELOG.md` 對應 section

**關鍵檔案**：
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`（新增）

---

## Phase 7 — GitHub Repo 上線（⚠️ 等使用者下令）

**為什麼**：目前本地 git 沒有 remote、且分支是 `master`，公開前要遷到 `main`。

**前置條件**：使用者已在 https://github.com/g761007/skillpod-cli 建好空 repo 並明確說「可以推」。

1. 在 GitHub 建立 `g761007/skillpod-cli` repo（public，**不**用 GitHub 的 init 選項，避免衝突）
2. 在 PyPI 後台設定 Trusted Publisher（指向 `g761007/skillpod-cli` 的 `release.yml` workflow，environment 留白或設 `pypi`）
3. 本地分支改名 + 推 remote：
   ```bash
   git branch -M master main
   git remote add origin git@github.com:g761007/skillpod-cli.git
   git push -u origin main
   ```
4. 同步把 README badge URL、`ci.yml` 的 `on.push.branches`、所有 OpenSpec 文件中提到 master 的地方改為 `main`（grep 一次確認）
5. 在 GitHub repo 設定：description、topics（`ai-agents`, `claude-code`, `dependency-manager`, `cli`, `skills`）、首頁連結 (PyPI URL)
6. 分支保護：`main` 設 required CI checks（self-review 即可，初期不強制 PR review）

---

## Phase 8 — PyPI 首發（⚠️ 等使用者下令）

**為什麼**：上述都就緒後才推；TestPyPI 與正式 PyPI 都需要使用者明確 go-ahead。

1. 先發 TestPyPI 驗證安裝流程：
   ```
   uv build
   uv publish --index testpypi
   pip install -i https://test.pypi.org/simple/ skillpod
   skillpod --help
   ```
2. 通過後 tag + push：
   ```bash
   git tag v0.5.0
   git push origin v0.5.0
   ```
3. release.yml 透過 OIDC Trusted Publisher 自動 publish 至 PyPI + 建 GitHub Release（內容引用 CHANGELOG 0.5.0 區段）
4. 驗證 `pip install skillpod` 可在乾淨虛擬環境跑通

---

## Verification

**Phase 1–2 驗證**（本機可跑）：
```bash
uv run ruff check src tests
uv run pytest -q
uv run mypy src/skillpod
uv build && ls dist/
python -m tarfile -l dist/skillpod-0.5.0.tar.gz | grep -E "LICENSE|README|examples|py.typed"
```

**Phase 3–5 驗證**：
- `gh` CLI 預覽 README（或 GitHub web 預覽）
- 確認 logo 在亮/暗模式皆可讀

**Phase 6 驗證**：
- 開個 draft PR 觸發 CI，看三平台與 mypy 都綠
- TestPyPI 跑通

**Phase 7–8 驗證**：
- `pip install skillpod` 在乾淨虛擬環境成功
- `skillpod --help` 顯示完整 14 個 subcommand
- PyPI 頁面顯示 logo（README 中的相對路徑要轉絕對 GitHub raw URL）、所有 badges、classifiers 完整

---

## 執行順序總覽

```
Phase 1 (版本/OpenSpec) ─┐
Phase 2 (packaging)       ├─→ Phase 6 (CI)  ─┐
Phase 3 (社群文件)         │                   │
Phase 4 (logo)            ─┘                  ├─→ Phase 7 (GitHub) ─→ Phase 8 (PyPI 0.5.0)
Phase 5 (README)  ←(需 logo + 新 badges)     ─┘
```

**前置作業使用者要做**（無法由我代勞）：
- ✓ PyPI 帳號（已有）；TestPyPI 帳號若無也建議註冊（一鍵 GitHub OAuth）
- 在 GitHub 開好 `g761007/skillpod-cli` repo（不要 init），等 Phase 7 開始前完成
- 等 release.yml 已 push 到 GitHub 後，到 PyPI 後台註冊 Trusted Publisher（指向該 workflow）
