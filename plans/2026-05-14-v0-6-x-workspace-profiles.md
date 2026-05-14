# skillpod v0.6.x — Workspace Profiles Preview

## Context

`skillpod` 目前 (v0.5.7) 是一個 project-scoped skill 套件管理器：每個 repo 在 `skillfile.yml` 宣告 skills，resolver 取出 effective set，installer 把它 fan-out 到各 agent 目錄。

下一個方向是把同樣的「reproducible context」概念推升一層，讓使用者可以**重複利用、可切換的 AI 工作情境（Profile）**。Profile 不只是 role，可以是專案、任務模式、團隊基線。專案級 skills 仍然是 first-class，profile 是額外組合層。

v0.6.x 是 preview 系列，目的是讓 profile model、resolver precedence、activation scope 三件事有一個可用但仍可調整的形態，再到 v0.7.0 進入 beta、v1.0.0 freeze schema。

**這份計畫的執行模式**：詳細規劃 v0.6.0 → v0.6.4 五個版本，但**立即執行範圍只更新 README ROADMAP 表格**（加上 v0.6.x preview / v0.7.0 / v0.8.0 條目）。後續每個版本由用戶逐一啟動實作，本檔作為 source of truth。

**Profile skills 語意（已決定）**：filter mode。Profile 中的 `skills:` 必須是 project `manifest.skills` 中已宣告的 skill name；profile 不能引入新 skill，不能宣告 source。

---

## 立即執行範圍（plan 通過後立刻做）

只動一個檔：`README.md` 的 `## Roadmap & status` 表格（lines 432-448）。新增三列：

```
| 0.6.x     | preview     | Workspace Profiles preview series (core / isolation / switching / shell / composition) |
| 0.7.0     | planned     | Profile model beta — schema + resolver precedence + activation scope stable           |
| 0.8.0     | planned     | Local-first visual management UI                                                      |
| 1.0.0     | planned     | schema freeze                                                                         |
```

不更動其他檔案。CHANGELOG / pyproject 留到各版本實作時再動。

---

## 全局設計決策（適用 v0.6.x 全系列）

### 1. 不要再用 `resolver` 命名

`src/skillpod/sources/resolver.py` 已經佔走「resolver」這個詞（指 source 優先序選擇）。新層的命名建議：

```
src/skillpod/skillset/
  __init__.py
  compose.py     # compose_effective_skillset(...)
  layers.py      # Layer / LayerOrigin enum + provenance
```

公開 API：

```python
def compose_effective_skillset(
    manifest: Skillfile,
    project_root: Path,
    *,
    profile: Profile | None = None,
    global_profile: Profile | None = None,
    cli_overrides: list[str] | None = None,
) -> EffectiveSkillset:
    ...

@dataclass(frozen=True)
class EffectiveSkillset:
    skills: list[SkillEntry]                    # 最終 skill list
    provenance: dict[str, LayerOrigin]          # skill name → 來源層
```

### 2. 取代既有重複邏輯

目前 `flatten() + user_skills merge + shadow warning` 在三個地方重複：

| 檔案 | 行 | 取代方式 |
|---|---|---|
| `src/skillpod/installer/pipeline.py` | 130-145 | 換成 `compose_effective_skillset(...)` |
| `src/skillpod/cli/commands/sync.py` | 80-86 | 同上 |
| `src/skillpod/cli/commands/list_cmd.py` | 22-26 | 同上 |
| `src/skillpod/cli/commands/doctor.py` | 136 附近 | 同上 |

`installer/expand.py:flatten()` 變成 `skillset/compose.py` 的內部 helper。

### 3. Lockfile 維持 flat

`Lockfile.resolved: dict[str, LockedSkill]` 不引入 profile 維度。理由：

- Profile 只決定「哪些 skill 要被啟用」，不會改變 skill commit / sha256
- 如果 profile A 用 `repo-context` ref=main，profile B 用 `repo-context` ref=v2，那是不同的 SkillEntry 名稱，不是同一個 skill 的兩個 lock
- v0.6.x 不引入「per-profile lock」，避免過早承諾 schema

### 4. Profile schema 不允許 source 宣告

Filter mode 已選定 → profile 只引用名稱，不能 `source:` / `version:`。schema 強制 string-only items：

```yaml
# 合法
profiles:
  reviewer:
    skills:
      - pr-review
      - changelog-review

# 非法（v0.6.x 拒絕）
profiles:
  reviewer:
    skills:
      - name: pr-review
        source: my-source
```

未來若要 extend mode，再以 `extend: true` flag opt-in，不破壞既有 schema。

### 5. Profile 命名空間

- **Project profile**：定義在 `skillfile.yml` 的 `profiles:` 下；以 profile name 引用
- **Global profile**：`~/.skillpod/profiles/<name>.yml`，每個 profile 一個檔
- 命名衝突時 project 勝過 global（v0.6.0 行為，v0.6.1 加上 activation policy 可改）

### 6. 在 `installer/paths.py` 新增

```python
GLOBAL_PROFILES_REL = ".skillpod/profiles"

def global_profiles_root(home: Path | None = None) -> Path:
    return (home or Path.home()) / GLOBAL_PROFILES_REL

def global_profile_path(name: str, home: Path | None = None) -> Path:
    return global_profiles_root(home) / f"{name}.yml"
```

沿用既有 `home: Path | None = None` 注入模式（test 用 `monkeypatch.setenv("HOME", str(tmp_path))`）。

---

## v0.6.0 — Profile Core

### 目標
Profile data model、global/project profile storage、CRUD 命令、resolver 第一版、`status` / `resolve` 命令。**不引入 activation policy / switching / session**——profile 只能透過 `--profile <name>` 顯式傳入。

### Schema 變更

**新增 `src/skillpod/manifest/models.py`**（緊接 `_StrictModel` 之後）：

```python
class ProfileEntry(_StrictModel):
    name: str = Field(..., min_length=1)
    type: str | None = None                     # "role" / "project" / "task" / "team" — 純展示
    agents: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)   # filter mode：必須是 project skill name

    @field_validator("agents", "skills")
    @classmethod
    def _items_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("duplicate entries")
        return value
```

**`Skillfile` 新增 field（lines 140-218）**：

```python
profiles: dict[str, ProfileEntry] = Field(default_factory=dict)
```

新增 cross-validator（補入 `_cross_check` L192）：

- 每個 profile 的 `skills:` 必須是 `manifest.skills` 已宣告的 name（filter mode 強制）
- 每個 profile 的 `agents:` 必須是 `manifest.agents` 已宣告的 name
- profile name 不可與 group name / skill name 衝突

**Loader normaliser（`src/skillpod/manifest/loader.py:25-60` 新增 `_normalise_profiles`）**：

把 dict 形式的 profile body 中 `skills:` / `agents:` 的 bare string list 標準化（與 `_normalise_skills` 對稱）。Filter mode 下 skill items 已經是 string，但容許 `{name: foo}` 物件形式自動退化為 `"foo"`，避免使用者誤寫。

### Storage

**Global profiles**：每個 profile 一個 YAML 檔，schema 與 `ProfileEntry` 相同但需 `version: 1` 包裝：

```yaml
# ~/.skillpod/profiles/reviewer.yml
version: 1
profile:
  name: reviewer
  type: role
  agents: [claude, codex]
  skills:
    - pr-review
    - changelog-review
```

新增 `src/skillpod/profile/` 套件：

```
src/skillpod/profile/
  __init__.py
  models.py      # GlobalProfileFile (version + profile)
  io.py          # load_global_profile / write_global_profile / list_global_profiles
  errors.py      # ProfileError
```

`ProfileError` 加入 `cli/_output.py:run_with_exit_codes`（lines 44-66）以拿到 exit 1。

### Resolver 第一版

新增 `src/skillpod/skillset/`（見全局設計 §1）。v0.6.0 行為：

```text
1. 從 manifest 取 base set = flatten(manifest)（與目前邏輯一致）
2. + project user_skills（與目前邏輯一致）
3. 若有 profile 參數：
   - 由 project profile 或 global profile 解析出 ProfileEntry
   - effective = base ∩ profile.skills（filter）
   - profile.skills 中找不到對應 skill → ProfileError
4. provenance：每個 skill 標記來源 LayerOrigin = PROJECT / USER_SKILL / PROFILE_FILTER
```

**LayerOrigin enum**（`skillset/layers.py`）：

```python
class LayerOrigin(StrEnum):
    PROJECT = "project"           # manifest.skills
    USER_SKILL = "user_skill"     # .skillpod/user_skills/
    PROFILE_FILTER = "profile_filter"  # 經 profile 過濾保留
```

### 新增 CLI 命令

新增子 app `profile_app`（`src/skillpod/cli/app.py`）：

```python
profile_app = typer.Typer(help="Manage workspace profiles", no_args_is_help=True)
app.add_typer(profile_app, name="profile", help="Manage workspace profiles")
```

新增命令模組（每個都依循 `def run(*, project_root, manifest_path, json_output, ...) -> None` + `emit/fail`）：

| 模組 | 命令 | 行為 |
|---|---|---|
| `cli/commands/profile_create.py` | `profile create <name> [--global] [--type ROLE]` | 建立空 profile（預設 project，`--global` 寫入 `~/.skillpod/profiles/<name>.yml`） |
| `cli/commands/profile_list.py` | `profile list [--global] [--project]` | 列出 profile（預設兩者都列，標記 scope）|
| `cli/commands/profile_show.py` | `profile show <name> [--global]` | 印出 profile 內容；JSON 模式給結構 |
| `cli/commands/profile_add.py` | `profile add <profile> <skill> [--global]` | 加入 skill（檢查是 project skill）|
| `cli/commands/profile_remove.py` | `profile remove <profile> <skill> [--global]` | 移除 skill |
| `cli/commands/status.py` | `status [--profile NAME]` | 印出 project / 可用 profiles / 若指定 profile 印 effective set |
| `cli/commands/resolve.py` | `resolve [--profile NAME] [--explain]` | 印出 effective skillset；`--explain` 加上 provenance |

**輸出 conventions**（與 `global list` 模式一致）：

- 預設 plain text（compact 表格）
- `--json` 走 `_output.emit(payload, json_output=True, human=...)`
- 不引入 rich library；表格用 f-string 對齊

**安全網**：YAML 寫入用 `yaml.safe_dump`，profile 名稱 regex `^[a-zA-Z0-9_-]+$` 防止路徑跳脫。

### 測試

`tests/test_cli.py` 新增 section（沿用 v0.5.7 `# ---- ... ----` 風格，line 1159+）：

```
# ---- profile create / list / show ----
# ---- profile add / remove ----
# ---- status ----
# ---- resolve ----
```

涵蓋：
- 全部 CRUD 走 happy path（global + project 兩個 scope）
- profile.skills 引用不存在的 project skill → exit 1 + 訊息
- profile name 衝突（vs group/skill）→ ManifestError
- `resolve --profile foo` 在 profile 不存在時退出 1
- `resolve --explain` JSON 結構含 provenance map
- `--global` 用 `monkeypatch.setenv("HOME", str(tmp_path))` 測 `~/.skillpod/profiles/`

新增 `tests/test_skillset.py`（compose_effective_skillset 單元測試）+ `tests/test_profile_io.py`（global YAML round-trip）。

### Schema regen

跑 `skillpod schema > src/skillpod/schemas/skillfile.schema.json` 把新 `profiles:` field 寫回 snapshot。

### 對既有行為的影響
- `pipeline.py` / `sync.py` / `list_cmd.py` / `doctor.py` 改用 `compose_effective_skillset`，**不傳 profile** 時行為與目前完全一致（base set 不變）→ 既有測試全綠
- `flatten()` 變成 internal，`tests/test_manifest.py:14` 改 import path 或保留 re-export

### 驗證

```bash
uv run mypy src/skillpod
uv run ruff check src tests
uv run pytest -q

# 互動驗證
cd /tmp && mkdir profile-demo && cd profile-demo
skillpod init
echo 'skills: [foo, bar]' >> skillfile.yml      # 加 dummy skills（要先加 source）
skillpod profile create reviewer --type role
skillpod profile add reviewer foo
skillpod profile show reviewer
skillpod resolve --profile reviewer --explain
skillpod status --profile reviewer
```

---

## v0.6.1 — Project Isolation

### 目標
讓 project 可以宣告「禁止 global profile 影響我」的 activation 政策。Profile model 不變，只新增 activation block 與 resolver layer 計算。

### Schema 變更

`Skillfile` 新增：

```python
class ActivationPolicy(_StrictModel):
    mode: Literal["strict", "merge", "fallback", "manual"] = "manual"
    default_profile: str | None = None
    inherit_global: bool = True

# Skillfile 新欄位
activation: ActivationPolicy = Field(default_factory=ActivationPolicy)
```

預設 `manual` + `inherit_global=True` → 既有 project 行為不變（v0.6.0 也沒有 activation 概念）。

Cross-check：`activation.default_profile` 必須存在於 `manifest.profiles`。

### 模式語意

| Mode | base set | + profile |
|---|---|---|
| `strict` | project skills only | 只能用 project profile，不接受 global |
| `merge` | project skills | project profile ∪ global profile（兩者都套）|
| `fallback` | project skills | 沒指定 profile 時若 default_profile 為 None 才用 global |
| `manual` | project skills | 必須顯式 `--profile`，否則 base only（不自動套 global）|

`inherit_global=False` 在 strict/merge/fallback 之外再強制拒絕 global profile（v0.6.0 預設行為等同 `manual + inherit_global=False`，但現在可以調）。

### Resolver 變更

`compose_effective_skillset` 簽名擴充：

```python
def compose_effective_skillset(
    manifest: Skillfile,
    project_root: Path,
    *,
    profile_name: str | None = None,        # 取代直接傳 Profile
    cli_overrides: list[str] | None = None,
    ignore_global: bool = False,            # CLI 旗標可強制覆蓋
) -> EffectiveSkillset:
    ...
```

內部新增 `_apply_activation_policy(manifest.activation, ...)` 決定：

1. 解析 effective profile name（CLI > activation.default_profile > None）
2. 解析 effective profile body（project ∪ global，依 mode）
3. 套用 filter
4. 若 inherit_global=False 而試圖載入 global → 發 warning 並改用 project-only

新增 `LayerOrigin.GLOBAL_PROFILE_FILTER`、`POLICY_BLOCKED_GLOBAL`。

### CLI 變更

- 既有 `skillpod resolve` / `status` 套用 activation policy
- `skillpod status` 新增「Activation: strict / inherit_global=false」一行
- 新增 `--ignore-global` flag 給 `resolve` / `status` / `install` / `sync`
- 當 strict mode + global profile 命中時 → emit warning（stderr）

### 測試

`tests/test_skillset.py` 新增 activation 測試矩陣（4 mode × inherit_global 兩值 × profile 是否指定）。`tests/test_cli.py` 加 strict/merge/fallback/manual 各一個 e2e。

### 驗證

新建兩個 sample project（`tests/fixtures/multi_project_a`, `_b`），分別宣告不同 activation mode，跑同一個 global profile 應產生不同 resolved set。

### 對既有行為的影響

預設 `manual + inherit_global=True` → v0.6.0 用戶升級後 `resolve` 行為不變（沒指定 profile 就不套 profile）。文件提醒：要 strict 隔離記得明寫。

---

## v0.6.2 — Safe Switching

### 目標
讓 profile 啟用變成顯式、有 scope。引入 `switch` 高階命令與 `profile use` 低階別名。**Session scope 在這版只是 env-var 介面**（v0.6.3 才有真正 session shell）。

### State storage

新增 `src/skillpod/state/` 套件：

```
src/skillpod/state/
  __init__.py
  active.py      # ActiveProfile（global / project / session 三層）
  io.py
```

| Scope | 儲存位置 | 生命週期 |
|---|---|---|
| `global` | `~/.skillpod/active-profile` (純 text，profile name 一行) | 永久，全 user |
| `project` | `<project>/.skillpod/active-profile` | 永久，per-repo |
| `session` | env var `SKILLPOD_ACTIVE_PROFILE` | shell session 內 |

讀取優先序：`session env > project file > global file > activation.default_profile > none`。

### CLI

新增命令模組：

| 模組 | 命令 | 行為 |
|---|---|---|
| `cli/commands/switch.py` | `switch <profile> --scope SCOPE` | 寫入對應 scope 的 active-profile（session scope 印出 export 指令）|
| `cli/commands/profile_use.py` | `profile use <profile> --scope SCOPE` | switch 別名，掛在 profile_app |
| `cli/commands/profile_current.py` | `profile current` | 印出當前 active profile 與來源 layer |

`--scope` 預設為 `project`（在 project 內）/ `global`（沒有 project 時）。`--global` 在 project 內必須顯式（避免誤覆寫個人 default）。

```bash
skillpod switch reviewer --scope session
# stdout: export SKILLPOD_ACTIVE_PROFILE=reviewer
# stderr: # Run: eval "$(skillpod switch reviewer --scope session)"
```

### Resolver 變更

`compose_effective_skillset` 不再要求 caller 傳 `profile_name`：若沒傳，由 `state.active.read_active_profile(project_root)` 解析。

`status` 顯示：

```
Active profile: reviewer (scope: session)
```

### 測試

- 三層 scope 寫入/讀取的優先序矩陣
- `switch --scope global` 在 project 內必須加 `--global` 才動（warning gate）
- env var 設定後 `resolve` 自動套用

### 驗證

```bash
cd /repo && skillpod switch dev --scope project
skillpod profile current     # → dev (project)
SKILLPOD_ACTIVE_PROFILE=reviewer skillpod profile current  # → reviewer (session)
```

---

## v0.6.3 — Session Shell

### 目標
真正的 sub-shell，自動清理 session state、自動 export env、自動恢復 PROMPT。多 terminal 多 profile 並行。

### 命令

`cli/commands/shell.py` — `skillpod shell <profile>`：

1. 解析 profile（含 activation policy 檢查）
2. spawn `$SHELL`（fallback `/bin/sh`），帶 env：
   - `SKILLPOD_ACTIVE_PROFILE=<name>`
   - `SKILLPOD_SHELL_DEPTH=$((depth+1))`
   - `PS1` 加 prefix `[skillpod:<profile>] `（zsh/bash 各自處理）
3. 子 shell 結束 → 父 process 結束、無 cleanup 需求（env 是 process-local）
4. 不可在 `SKILLPOD_SHELL_DEPTH > 0` 時 nest（先 exit 才能再 enter）

### 新增 sync scope

`skillpod sync --scope session` — 與 `--scope project` 差別：fan-out 寫到 session 專屬 agent dir，**v0.6.3 暫不實作**（會牽動 fan-out path 設計），改成：

- `sync --scope session` 視為 `sync` + 強制 `compose_effective_skillset(profile_name=session_active)` → 確保 session profile 真的 materialise
- 不引入新 fanout root；agent dir 共用，session profile 切換時必跑一次 `install` 或 `sync`

（取捨：避免一次性引入「per-session agent dir」的長期 schema 承諾。如果跑團隊回饋確實需要 per-session 隔離，留到 v0.7.0+。）

### `status` 變更

```
Project: skillpod-cli
Shell session: active (depth=1)
Active profile: reviewer (scope: session)
Resolved from: 4 skills
```

### 測試

`pexpect` based test（or `subprocess.run` with `--no-shell` short-circuit flag）：

- spawn shell → 確認 env 帶入
- nested shell guard
- exit 後父 process env 不被污染

### 驗證

```bash
# Terminal A
cd ~/work/project-a && skillpod shell reviewer
echo $SKILLPOD_ACTIVE_PROFILE  # → reviewer

# Terminal B（同時）
cd ~/work/project-b && skillpod shell developer
echo $SKILLPOD_ACTIVE_PROFILE  # → developer
```

---

## v0.6.4 — Composition Preview

### 目標
**Experimental** 標籤的 profile 組合：`projectA+reviewer`。Diff、import、export。組合行為標記為 unstable，目的是收集真實 use case。

### Schema 變更

無新欄位。Composition 是 resolver 行為。

### 命令語法

```bash
skillpod switch skillpod-cli+reviewer --scope session
skillpod resolve --profile skillpod-cli+reviewer --explain
```

`+` 為 reserved separator。Profile name regex 已禁止 `+`，所以新解析路徑：

```python
def parse_profile_expr(expr: str) -> list[str]:
    return [p.strip() for p in expr.split("+") if p.strip()]
```

### Resolver 變更

`compose_effective_skillset(profile_name=...)` 改為 `profile_names: list[str]`。語意：

- 多個 profile 的 `skills:` 取**聯集**
- 多個 profile 的 `agents:` 取**聯集**
- type 衝突無所謂（純展示）
- 任一 profile 不存在 → 整個 expression 失敗

`LayerOrigin.PROFILE_FILTER` 改為 `LayerOrigin.PROFILE_FILTER` + `source_profiles: tuple[str, ...]` 帶在 provenance metadata。

### 新命令

| 模組 | 命令 | 行為 |
|---|---|---|
| `cli/commands/profile_diff.py` | `profile diff <a> <b>` | 印出 a/b skill / agent set 的 added / removed / common |
| `cli/commands/profile_export.py` | `profile export <name> [--out FILE]` | 輸出 self-contained YAML（含 metadata：source scope, exported_at）|
| `cli/commands/profile_import.py` | `profile import <file> [--global] [--rename NAME]` | 匯入並驗證 schema |

### Experimental gate

所有 composition path（包括 `+` 解析、`switch <a+b>`）在第一次使用時印 stderr warning：

```
warning: profile composition is experimental — semantics may change in v0.7.x
```

可用 `SKILLPOD_DISABLE_EXPERIMENTAL_WARNING=1` 關掉（純 noise reduction，不關功能）。

### 測試

- Composition 順序穩定性（`a+b` vs `b+a` 結果一致）
- diff 對稱性測試
- import 時 schema 不合法 → exit 1
- import + activation policy strict → 拒絕（與 v0.6.1 規則一致）

### 驗證

```bash
skillpod profile create reviewer --type role
skillpod profile create skillpod-cli --type project --global
skillpod resolve --profile skillpod-cli+reviewer --explain
skillpod profile diff reviewer skillpod-cli
skillpod profile export reviewer --out /tmp/reviewer.yml
skillpod profile import /tmp/reviewer.yml --rename reviewer-copy
```

---

## 跨版本 critical files

新建立：

```
src/skillpod/profile/__init__.py
src/skillpod/profile/models.py
src/skillpod/profile/io.py
src/skillpod/profile/errors.py
src/skillpod/skillset/__init__.py
src/skillpod/skillset/compose.py
src/skillpod/skillset/layers.py
src/skillpod/state/__init__.py            # v0.6.2
src/skillpod/state/active.py              # v0.6.2
src/skillpod/state/io.py                  # v0.6.2
src/skillpod/cli/commands/profile_create.py
src/skillpod/cli/commands/profile_list.py
src/skillpod/cli/commands/profile_show.py
src/skillpod/cli/commands/profile_add.py
src/skillpod/cli/commands/profile_remove.py
src/skillpod/cli/commands/profile_use.py     # v0.6.2
src/skillpod/cli/commands/profile_current.py # v0.6.2
src/skillpod/cli/commands/profile_diff.py    # v0.6.4
src/skillpod/cli/commands/profile_export.py  # v0.6.4
src/skillpod/cli/commands/profile_import.py  # v0.6.4
src/skillpod/cli/commands/status.py
src/skillpod/cli/commands/resolve.py
src/skillpod/cli/commands/switch.py           # v0.6.2
src/skillpod/cli/commands/shell.py            # v0.6.3
tests/test_skillset.py
tests/test_profile_io.py
tests/test_state_active.py                    # v0.6.2
tests/test_shell.py                           # v0.6.3
tests/test_composition.py                     # v0.6.4
tests/fixtures/multi_project_a/               # v0.6.1
tests/fixtures/multi_project_b/               # v0.6.1
```

修改：

```
src/skillpod/manifest/models.py        # 加 ProfileEntry / activation
src/skillpod/manifest/loader.py        # _normalise_profiles
src/skillpod/installer/paths.py        # global_profiles_root
src/skillpod/installer/pipeline.py     # 改用 compose_effective_skillset (line 130-145)
src/skillpod/installer/expand.py       # flatten 變 internal helper
src/skillpod/cli/app.py                # 掛 profile_app + 註冊 status/resolve/switch/shell
src/skillpod/cli/commands/sync.py      # 改用 compose_effective_skillset (line 80-86)
src/skillpod/cli/commands/list_cmd.py  # 改用 compose_effective_skillset (line 22-26)
src/skillpod/cli/commands/doctor.py    # 改用 compose_effective_skillset (line 136 附近)
src/skillpod/cli/_output.py            # ProfileError 加入 run_with_exit_codes
src/skillpod/schemas/skillfile.schema.json  # 每版 schema regen
README.md                              # 立即執行：roadmap 表格
CHANGELOG.md                           # 每版實作時新增 section
pyproject.toml                         # 每版 bump version
```

---

## 重複利用的既有元件

不需要重寫，直接呼叫：

- `src/skillpod/manifest/loader.py:load()` (L110) — manifest 載入
- `src/skillpod/installer/expand.py:flatten()` (L29) — group expansion，移為 skillset 內部 helper
- `src/skillpod/installer/user_skills.py:discover_user_skills()` (L16) — user_skills 掃描
- `src/skillpod/installer/paths.py` — 整個 paths 模組的 `home: Path | None = None` 注入模式
- `src/skillpod/cli/_output.py:emit/fail/run_with_exit_codes` — 全部新命令的 I/O 模式
- `tests/_git_fixtures.py:make_skill_repo / make_root_skill_repo / make_multi_skill_repo` — e2e 測試
- `tests/test_cli.py` 內 `_project(tmp_path, manifest)` helper (line 39-43)

---

## 驗證（每版實作時跑）

```bash
uv run mypy src/skillpod
uv run ruff check src tests
uv run pytest -q
uv run pytest tests/test_skillset.py tests/test_profile_io.py -v   # 新模組
```

E2E sanity（v0.6.0）：

```bash
cd /tmp && rm -rf profile-demo && mkdir profile-demo && cd profile-demo
skillpod init
# 編輯 skillfile.yml 加兩個 dummy git source skills
skillpod install
skillpod profile create reviewer --type role
skillpod profile add reviewer skill-a
skillpod resolve                          # 不傳 profile → 兩個 skill
skillpod resolve --profile reviewer       # → 只有 skill-a
skillpod resolve --profile reviewer --explain --json | jq .
skillpod status --profile reviewer
```

每版完成後執行 release：依 v0.5.7 範本（CHANGELOG → pyproject bump → ruff/mypy/pytest 三綠 → commit `release: v0.6.x` → tag → fast-forward main → push）。Release 不開 PR，直接到 main（依 [[feedback_release_no_pr]] 慣例）。

---

## 風險與注意事項

1. **`compose_effective_skillset` 取代既有四個 call site** 是這個系列最容易踩雷的地方。v0.6.0 的測試必須涵蓋「不傳 profile 時行為與 v0.5.7 完全一致」；建議先把現有四處的行為記錄成 fixture-based snapshot 測試，再做替換。

2. **Profile filter 對 user_skills 的處理**：filter 應該作用在「project skills + user_skills 聯集」之上，還是只 filter project skills？建議 v0.6.0 採前者（聯集後 filter），但 user_skills 名稱必須能在 profile.skills 中引用——cross-check 時要把 user_skills 也算進「合法名稱集合」。

3. **`switch --scope global` 在 project 內的安全性**：v0.6.2 必須要求顯式 `--global` 才願意改全域，避免「我以為只改本 repo，結果改了全域」的 footgun。

4. **Composition 順序穩定性**：v0.6.4 測試務必 pin `a+b` 與 `b+a` 結果一致（聯集），否則使用者會踩到不可預期 ordering。

5. **Schema regen 漏跑**：每版都要跑 `skillpod schema > src/skillpod/schemas/skillfile.schema.json`，否則 IDE tooling 會 drift。建議加進 release checklist。
