# skillpod-cli v0.6.1 — Project Isolation (Activation Policy)

## Context

v0.6.0 交付 Workspace Profiles core（profile CRUD、`compose_effective_skillset`、`status`/`resolve`），但 profile 只能透過 `--profile <name>` 顯式啟用，沒有任何 project-level 的政策能管控「global profile 是否會影響我」。

v0.6.1 新增一個 `activation:` block，讓 `skillfile.yml` 可宣告 4 種模式 × `inherit_global` 旗標來決定 profile 解析行為。預設值（`mode: manual` + `inherit_global: true`）刻意與 v0.6.0 等價，所以既有 project 升上來零變動。

範圍刻意控制：只擴 `compose_effective_skillset` 與直接呼叫它的 `resolve`/`status` 兩個 CLI。`install`/`sync` 走的是 `installer.install` → `flatten()` 舊路徑，不在這版做（見「Out-of-scope」段）。

---

## Schema 變更

### `src/skillpod/manifest/models.py`

在 `ProfileEntry`（lines 143–160）與 `Skillfile`（line 163 起）之間新增：

```python
class ActivationPolicy(_StrictModel):
    mode: Literal["strict", "merge", "fallback", "manual"] = "manual"
    default_profile: str | None = Field(default=None, min_length=1)
    inherit_global: bool = True
```

`Skillfile` 在 line 175（緊跟 `profiles` 之後）新增：

```python
activation: ActivationPolicy = Field(default_factory=ActivationPolicy)
```

`_cross_check`（lines 231–267）在 `return self` 前加：

- 若 `activation.default_profile is not None`：必須存在於 `self.profiles`；否則 `ManifestError`。
- `activation.mode == "manual"` 且 `activation.default_profile` 不為 None → `ManifestError`（manual 模式不該有預設 profile，避免靜默誤導）。

`__all__`（lines 270–281）新增 `"ActivationPolicy"`。

### `src/skillpod/manifest/loader.py`

mirror `_normalise_profiles`（lines 83–98）新增 `_normalise_activation`：

```python
def _normalise_activation(raw: Any) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ManifestError(f"`activation:` must be a mapping, got {type(raw).__name__}")
    return raw
```

在 `loads()`（lines 115–122 區段）profiles 標準化之後加 `if "activation" in data: data["activation"] = _normalise_activation(data["activation"])`。

---

## Mode 語意（compose 內部）

| Mode | 沒 `--profile` 時 | 給 `--profile` 時 |
|---|---|---|
| `strict` | 套用 `activation.default_profile`（若有）僅限 project；沒有就 base only | 必須是 project profile；命中 global → stderr warning + `ProfileError` |
| `merge` | 套 `default_profile`（project ∪ global） | project profile ∪ global profile（聯集），任一缺少不致命 |
| `fallback` | 套 `default_profile`：project 優先，沒有就 global | 同理：project 優先，沒有用 global |
| `manual` | base only（即使有 `default_profile` 也忽略，預設值禁止 `default_profile`） | 行為等同 v0.6.0：project 優先，沒有就 global |

`inherit_global=False`（與 CLI `--ignore-global`）作為硬閘門：在套 global profile 前就先 reject。`strict` + 試圖載 global → 發 stderr warning。

---

## Resolver 變更（`src/skillpod/skillset/compose.py`）

### 新簽名

```python
def compose_effective_skillset(
    manifest: Skillfile,
    project_root: Path,
    *,
    profile_name: str | None = None,
    home: Path | None = None,
    ignore_global: bool = False,            # ← 新增
) -> EffectiveSkillset:
```

### `EffectiveSkillset` 擴充

加一個欄位（lines 17–22）：

```python
@dataclass(frozen=True)
class EffectiveSkillset:
    skills: list[SkillEntry]
    provenance: dict[str, LayerOrigin]
    warnings: tuple[str, ...] = ()          # ← 新增；CLI 印 stderr
```

### 新增 `_apply_activation_policy` helper

放在 compose.py 內部、`compose_effective_skillset` 之前：

```python
def _apply_activation_policy(
    activation: ActivationPolicy,
    *,
    profile_name: str | None,
    ignore_global: bool,
    manifest: Skillfile,
    home: Path | None,
) -> tuple[ProfileEntry | None, set[str], list[str]]:
    """Return (effective_profile, global_filter_skill_names, warnings)."""
```

回傳三元組：
1. `effective_profile`：最終要套的 ProfileEntry（已含 merge 後的 union skills/agents），或 `None` 代表 base only。
2. `global_filter_skill_names`：屬於 global profile 那層的 skill name set（用來標 `GLOBAL_PROFILE_FILTER` provenance）。
3. `warnings`：strict + global 命中等情況的 stderr 訊息。

`compose_effective_skillset` 本體：
1. 跟現在一樣 `flatten` + `discover_user_skills` 組出 `combined`（base set）。
2. 呼叫 `_apply_activation_policy(...)` 拿到 `(effective_profile, global_names, warnings)`。
3. 若 `effective_profile is None` → 回傳 base + warnings。
4. 否則 filter `combined` by `effective_profile.skills`，為每個 skill 標：
   - `LayerOrigin.GLOBAL_PROFILE_FILTER` 若 name ∈ `global_names`
   - 否則 `LayerOrigin.PROFILE_FILTER`
5. 未知 skill name → `ProfileError`（同 v0.6.0 邏輯）。

### `src/skillpod/skillset/layers.py`

`LayerOrigin` 增加兩個成員：

```python
GLOBAL_PROFILE_FILTER = "global_profile_filter"
POLICY_BLOCKED_GLOBAL = "policy_blocked_global"
```

`POLICY_BLOCKED_GLOBAL` 不直接用作 per-skill provenance，是預留給 status/diagnostic 標記，避免 v0.6.2+ 再改 enum。

---

## CLI 變更

### `resolve.py`

`run()` 新增 `ignore_global: bool = False`，傳進 `compose_effective_skillset`（line 24–26）。`app.py` 端的 Typer 包裝加 `--ignore-global` flag。

### `status.py`

- `run()` 新增 `ignore_global: bool`。
- 人類輸出在 line 61（`f"skills:    {len(manifest.skills)}"`）後插：
  ```
  activation: <mode> / inherit_global=<true|false>
  ```
- JSON payload（lines 48–56）加：
  ```python
  "activation": {
      "mode": manifest.activation.mode,
      "inherit_global": manifest.activation.inherit_global,
      "default_profile": manifest.activation.default_profile,
  }
  ```
- 若 `compose_effective_skillset` 回傳 `warnings`，逐行 `typer.echo(..., err=True)`。

### `app.py`

`resolve` 與 `status` Typer 包裝各加：

```python
ignore_global: bool = typer.Option(
    False, "--ignore-global",
    help="Ignore ~/.skillpod/profiles when resolving (overrides inherit_global=true).",
),
```

---

## Out-of-scope（v0.6.1 不做）

- `install` / `sync` 的 `--ignore-global` flag：這兩個 CLI 走 `installer.install` → `installer.expand.flatten()`，沒接 `compose_effective_skillset`。要加 flag 必須先做 v0.6.x 計畫裡「§2 取代既有重複邏輯」的遷移（pipeline.py / sync.py / list_cmd.py / doctor.py 四個 call site），那是一個獨立的清理 task，建議拆到 v0.6.1.x 或 v0.6.2。
- Session / state / `switch`：v0.6.2。
- Composition (`a+b`)：v0.6.4。

---

## 測試

### `tests/test_skillset.py`

延續既有 inline-YAML + `_manifest()` helper 模式，加一個新 section：

```
# ---- activation policy ----
```

涵蓋（建議用 `@pytest.mark.parametrize` 跑矩陣，但拆成獨立函式也行——選擇權留實作時看可讀性決定）：

- 4 modes × 2 `inherit_global` × `profile_name` 給/不給 = 16 case 的核心邏輯
- `manual` + `default_profile != None` → `ManifestError`
- `default_profile` 不存在 → `ManifestError`
- `strict` + 試圖載 global → warning + `ProfileError`
- `merge` + project profile 也存在 → 聯集，provenance 同時含 PROFILE_FILTER 與 GLOBAL_PROFILE_FILTER
- `fallback` 無 project profile → 改用 global
- `ignore_global=True` 永遠強制忽略 global 即使 `inherit_global=True`

### `tests/test_cli.py`

加 e2e（沿用 `_project(tmp_path, manifest)` helper，line 39–43）：

- `status` 顯示 `activation:` 行（plain + JSON）
- `resolve --ignore-global` 真的繞過 global profile
- 各 mode 一條 happy-path e2e（4 條）

### `tests/test_manifest.py`

- `ActivationPolicy` 預設值
- Cross-check：`default_profile` 不存在 → `ManifestError`
- Cross-check：`manual` + `default_profile` → `ManifestError`

### Fixtures（選用，可用 inline YAML 替代）

`tests/fixtures/multi_project_a/skillfile.yml`（strict）、`multi_project_b/skillfile.yml`（merge）。若 inline YAML 已夠用就略過——同一個 global profile 套到兩 fixture 拿到不同 set 的差異測試是 plan 裡標記為「驗證」段而非必跑單元測試。

---

## Schema regen

實作完跑一次：

```bash
uv run skillpod schema --output schemas/skillfile.schema.json
```

這會把 `activation` field 寫進 root-level schema snapshot（v0.6.0 PR #4 之前那個漏跑事故的修補經驗）。

---

## 對既有行為的影響

- 既有 `skillfile.yml` 沒寫 `activation:` → 預設 `manual + inherit_global=True` → 等同 v0.6.0 行為，0 個既有測試會壞。
- `compose_effective_skillset` 新 `ignore_global` 是 kwarg-only 預設 False，既有 caller 不用改簽名。
- `EffectiveSkillset.warnings` 用 default `()`，既有 caller 也不用動。

---

## Critical files

修改：
```
src/skillpod/manifest/models.py        # ActivationPolicy + Skillfile.activation + cross-check
src/skillpod/manifest/loader.py        # _normalise_activation
src/skillpod/skillset/compose.py       # _apply_activation_policy + 新 sig + warnings
src/skillpod/skillset/layers.py        # 兩個新 enum
src/skillpod/cli/commands/resolve.py   # ignore_global kwarg
src/skillpod/cli/commands/status.py    # activation 顯示 + ignore_global
src/skillpod/cli/app.py                # --ignore-global Typer 包裝
schemas/skillfile.schema.json          # regen
tests/test_skillset.py                 # activation 矩陣
tests/test_cli.py                      # CLI e2e
tests/test_manifest.py                 # model + cross-check 單元
```

無新建檔（除選用的 fixtures）。

---

## 重複利用既有元件

- `_StrictModel` (models.py:32-35) — `ActivationPolicy` 直接繼承
- `_normalise_profiles` (loader.py:83-98) — `_normalise_activation` 的 template
- `load_global_profile` / `list_global_profiles` (profile/io.py) — `home: Path | None = None` 注入已就位
- `_apply_activation_policy` 內部沿用 v0.6.0 既有的 project profile 查找 + global 載入邏輯（從 compose.py:67-74 抽出）
- `ProfileError` (profile/errors.py) — 已掛 `run_with_exit_codes` exit 1
- `tests/test_cli.py:_project()` 與 `tests/_git_fixtures.py` helpers — e2e 沿用

---

## 驗證

```bash
uv run mypy src/skillpod
uv run ruff check src tests
uv run pytest -q                                  # 全綠（323 + 新增 ≈ 20+）
uv run pytest tests/test_skillset.py -v           # 新矩陣
uv run pytest tests/test_cli.py -k activation -v  # CLI e2e
```

E2E sanity（手測）：

```bash
cd /tmp && rm -rf v0_6_1_demo && mkdir v0_6_1_demo && cd v0_6_1_demo
skillpod init
# 編輯 skillfile.yml：加 activation: { mode: strict, inherit_global: false } 與一個 profile
skillpod status                          # 看 activation 行
skillpod profile create reviewer --global # 建 global profile
skillpod resolve --profile reviewer      # strict + inherit_global=false → 應 reject + warning
skillpod resolve --profile reviewer --ignore-global   # 等價
```

---

## Workflow

1. 從 `main` 切 `v0.6.1` branch（PR #4 已 merge 入 main，handoff 撰寫時雖 open，但這份計畫假設 merge 完成；若未 merge 就從 `v0.6.0` 切）。
2. 按上方順序實作：models → loader → layers → compose → resolve/status CLI → schema regen → tests。
3. Quality gate：`uv run mypy src/skillpod && uv run ruff check src tests && uv run pytest -q`。
4. Commit：`feat(profile): v0.6.1 — Project Isolation (activation policy)`。
5. Open PR targeting main。
