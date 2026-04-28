# Plan: 擴充 `skillpod add` 為 vercel-labs/skills 風格

## Context

skillpod 目前的 `skillpod add <skill>` 只接受**單一 skill 名稱**並透過已宣告的 `sources:` 或 registry 解析 — 想要從新的 git repo 拉一組 skills 必須**手動**先編輯 `skillfile.yml` 的 `sources:` 區塊，再跑 `add`，體驗笨拙。

vercel-labs/skills 的 `npx skills add` 採取另一種設計：positional 是 **source**（git URL / `owner/repo` / 本地路徑），用 `-s` 選裡頭的 skills、`-a` 選 agent、`-l` 預覽、`-g` 安裝到全域。本計畫把這套介面**疊加**到既有指令上：

- positional 自動偵測「source 形式 vs skill 名稱」，向下相容現有用法
- source 形式時自動寫入 `sources:` 與對應的 `skills:`，不再需要手編
- 新增 `-g` 全域安裝路徑為 `~/.skillpod/skills/`，並 fan-out 到 `~/.<agent>/skills/`
- 新增 `-l` 預覽 source 內所有 skills（name + description）
- 新增 `-a`/`-s` 過濾 agent / 指定特定 skills
- 失敗時保留現有 manifest snapshot/rollback 機制

最終：`skillpod add anthropics/skills -s pdf -s docx -a claude` 一行完成「加 source、選 skills、限定 agent、安裝、寫 lockfile」。

---

## Design

### 1. positional 自動偵測

新增 `src/skillpod/sources/spec.py`，匯出 `parse_source_spec(text) -> SourceSpec | None`：

| 輸入形態 | 判定 | 範例 |
|---|---|---|
| 含 `://` | git URL | `https://github.com/anthropics/skills`、`git+ssh://git@github.com/x/y` |
| 開頭 `git@` | git SSH | `git@github.com:anthropics/skills.git` |
| 結尾 `.git` | git URL | `foo.git` |
| 開頭 `./`、`../`、`/`、`~` | local 路徑 | `./my-skills`、`~/work/skills` |
| 符合 `^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$` | GitHub shorthand → 展開 `https://github.com/{0}` | `anthropics/skills` |
| 其他 | bare skill name → 走舊流程 | `audit` |

回傳結構：
```python
@dataclass(frozen=True)
class SourceSpec:
    kind: Literal["git", "local"]
    url_or_path: str    # canonical 形式（GitHub shorthand 已展開）
    derived_name: str   # 預設 source name（去 .git 後的最後一段）
    ref: str = "main"
```

衝突時 `derived_name` 自動 suffix `-2`、`-3`（檢查 manifest 既有 sources）。

### 2. CLI 介面（`src/skillpod/cli/app.py`）

擴充 `@app.command("add")`：

```python
def add(
    target: Annotated[str, typer.Argument(help="Skill name OR source (git URL / owner/repo / local path).")],
    skill: Annotated[list[str] | None, typer.Option("--skill", "-s", help="Specific skill(s) to install from the source. Use '*' for all. Repeatable.")] = None,
    agent: Annotated[list[str] | None, typer.Option("--agent", "-a", help="Target agent(s). Repeatable. Defaults to manifest agents (project) or all known agents (global).")] = None,
    list_only: Annotated[bool, typer.Option("--list", "-l", help="List skills available in the source without installing.")] = False,
    global_: Annotated[bool, typer.Option("--global", "-g", help="Install to ~/.skillpod/skills/ and fan-out to ~/.<agent>/skills/ instead of project.")] = False,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip interactive prompts.")] = False,
    ref: Annotated[str, typer.Option("--ref", help="Git ref / branch / commit (default: main).")] = "main",
    source_name: Annotated[str | None, typer.Option("--source-name", help="Override the auto-derived source name written to skillfile.")] = None,
    manifest: ManifestOpt = Path("skillfile.yml"),
    json: JsonOpt = False,
) -> None: ...
```

互斥性：
- `-l` 與 `-g` 可共存（列出全域可裝的 skills）
- `target` 是 bare skill name 時，`-s/-l` 不適用 → 直接報錯
- `-g` 時不需要 manifest（純全域操作），略過 manifest 存在性檢查

### 3. `add.py` 流程重寫（`src/skillpod/cli/commands/add.py`）

```
run(target, ...)
  spec = parse_source_spec(target)
  if spec is None:                          # bare skill name
      if list_only or skill or global_:
          fail("flags require a source argument, not a skill name")
      return _legacy_add_skill_name(target, ...)   # 既有流程

  # source-mode
  cache_dir = _materialize_source(spec, ref)       # git: clone via existing populate_cache; local: 直接讀
  discovered = discover_skills(cache_dir)          # see §4

  if list_only:
      _print_skill_table(discovered, json_output)
      return

  selected = _select_skills(discovered, skill, yes)  # '*' / 互動 / 指定

  if global_:
      _install_global(spec, selected, agent, yes)    # see §5
  else:
      _install_project(spec, selected, agent, manifest_path, yes)  # see §6
```

互動選擇（沒有 `-y`、沒有 `-s`）：用 `typer.prompt` 列出 `(0) all / (1) skill-a / (2) skill-b ...` 接受逗號分隔；CI 偵測 `not sys.stdin.isatty()` 視同 `-y` 預設全部。

### 4. Skill 探勘（`src/skillpod/sources/discovery.py`，新檔）

```python
@dataclass(frozen=True)
class DiscoveredSkill:
    name: str           # 目錄名
    description: str    # SKILL.md frontmatter description（缺則為空）
    rel_path: str       # 相對 cache_dir 的路徑

def discover_skills(root: Path) -> list[DiscoveredSkill]:
    """Walk `root` for SKILL.md files; parse YAML frontmatter for `description`."""
```

規則：
- `root` 自身有 `SKILL.md` → 視為單一 skill，name 用目錄 basename
- 否則 walk 第一層 / 兩層子目錄找 `SKILL.md`（深度上限 2，避免 examples/ 等噪音）
- frontmatter 解析失敗 → description 為空，不丟例外
- 排除 `node_modules`、`.git`、`dist`

### 5. 全域安裝（`src/skillpod/installer/global_install.py`，新檔）

新增 `paths.py` 常數：
```python
GLOBAL_INSTALL_ROOT = Path.home() / ".skillpod" / "skills"

def global_skill_dir(name: str) -> Path:
    return GLOBAL_INSTALL_ROOT / name

def global_agent_skill_dir(agent: str, name: str) -> Path:
    return Path.home() / f".{agent}" / "skills" / name
```

流程（每個被選 skill）：
1. **Resolve**：git → reuse `sources/git.py` 的 `resolve_ref` + `populate_cache`（無變動）；local → 直接指向 source 路徑
2. **Materialize**：把 cache 中的 skill 子目錄 symlink 到 `~/.skillpod/skills/<name>/`（同名已存在則 fail，除非 `-y` → 覆寫）
3. **Fan-out**：`-a` 列表（預設用 `global_list.GLOBAL_SKILL_DIRS` 全部）逐一建立 `~/.<agent>/skills/<name>` 的 symlink
4. **不寫 skillfile**（全域操作獨立於專案 manifest，依使用者選項 1 的決議）

複用 `installer/fanout.py` 的 symlink 邏輯，抽出對 root 不敏感的版本。

### 6. 專案安裝（升級版 `add.py` 主路徑）

對每個被選 skill，**先**改 manifest，**再**跑 install pipeline，沿用既有 snapshot/rollback：

1. Snapshot `manifest_path.read_text()`
2. **若 source 不存在於 manifest**：append `sources:` entry
   ```yaml
   sources:
     - name: <derived or --source-name>
       type: git
       url: https://github.com/anthropics/skills
       ref: main
       priority: 50
   ```
   local 形式則 `type: local` + `path:`
3. 對每個 selected skill append 到 `skills:`：
   ```yaml
   skills:
     - name: pdf
       source: anthropics-skills
   ```
   已存在同名 skill → 跳過並警告（不算錯誤）
4. 若 `-a` 給定且與 manifest `agents:` 不同 → **不**改 manifest，只在 install pipeline 暫時覆寫（避免「加一次 skill 改全域 agents」副作用）。實作：傳 `agent_filter` 參數到 install pipeline 的 fan-out 階段
5. 跑 `install(project_root, manifest_path=manifest_path)`；失敗則 restore snapshot

對 manifest 結構保留：用 `ruamel.yaml` 的 round-trip 或維持 `pyyaml` 並接受註解流失（與現行 `_append_skill_to_manifest` 相同行為，先沿用 pyyaml）。

### 7. Pipeline 微調（`src/skillpod/installer/pipeline.py`）

新增 optional 參數：
```python
def install(
    project_root, *, manifest_path=None, lockfile_path=None,
    agent_filter: list[str] | None = None,   # NEW
) -> InstallReport: ...
```

`agent_filter` 在 fan-out 階段做集合交集：`effective_agents = manifest_agents ∩ agent_filter`，傳入 `installer/fanout.py`。預設 `None` 表示沿用 manifest 全部 agents。

---

## Files to add / modify

| 檔案 | 動作 | 重點 |
|---|---|---|
| `src/skillpod/cli/app.py` | 修改 | 擴充 `add` 簽章（新增 `-s/-a/-l/-g/-y/--ref/--source-name`）並把所有旗標傳進 `add_cmd.run` |
| `src/skillpod/cli/commands/add.py` | 大改 | 新增 source-mode 主路徑；保留 bare-name 路徑為 `_legacy_add_skill_name` |
| `src/skillpod/sources/spec.py` | **新檔** | `parse_source_spec` + `SourceSpec` dataclass + `derive_unique_name` |
| `src/skillpod/sources/discovery.py` | **新檔** | `discover_skills` + `DiscoveredSkill`（YAML frontmatter parse） |
| `src/skillpod/installer/global_install.py` | **新檔** | `install_global(spec, skills, agents)`：materialize 到 `~/.skillpod/skills/` + fan-out 到 `~/.<agent>/skills/` |
| `src/skillpod/installer/paths.py` | 修改 | 新增 `GLOBAL_INSTALL_ROOT`、`global_skill_dir`、`global_agent_skill_dir` |
| `src/skillpod/installer/pipeline.py` | 修改 | `install(...)` 加 `agent_filter` 選參，fan-out 階段做交集 |
| `src/skillpod/installer/fanout.py` | 修改 | fan-out function 接受 `agents: Iterable[str]` 參數覆寫 |
| `src/skillpod/cli/commands/global_list.py` | 重複利用 | `GLOBAL_SKILL_DIRS` 改為 `global_install` 的預設 agent 清單來源（共用，避免兩處維護） |
| `tests/test_cli_add_source.py` | **新檔** | 蓋三大路徑：bare-name（向下相容）、source-mode 專案安裝、source-mode 全域安裝（含 fan-out） |
| `tests/test_sources_spec.py` | **新檔** | `parse_source_spec` 全部分支單測 |
| `tests/test_discovery.py` | **新檔** | `discover_skills` walk + frontmatter parse 邊界 |
| `examples/skillfile.yml` | 修改 | README/示例補一段「`skillpod add anthropics/skills -s pdf` 後 manifest 自動長成這樣」 |
| `README.md` | 修改 | 新章節 `Adding skills from a git source` |
| `CHANGELOG.md` | 修改 | 0.6.0 條目 |

### 可重用元件（不要重寫）

- **Git clone + commit-pinned cache**：`src/skillpod/sources/git.py` 的 `resolve_ref(url, ref)` + `populate_cache(url, commit)`（已支援 immutable cache，全域安裝直接複用）
- **Manifest snapshot/rollback**：既有 `add.py:54-63` 模式
- **YAML mutation**：既有 `_append_skill_to_manifest`（擴充為「插 sources + skills」）
- **Agent fan-out**：`src/skillpod/installer/fanout.py`（加 agent 子集參數即可）
- **Symlink/copy 模式**：`installer/adapter*.py` + `manifest.install.mode`
- **JSON 輸出**：`cli/_output.py` 的 `emit`、`fail`、`run_with_exit_codes`
- **CLI 測試框架**：`tests/test_cli.py` 的 `CliRunner` + `tmp_path` + `respx` 模式

---

## Verification

執行下列場景，每項都要在乾淨 `tmp_path` 中跑通且 `git status` 無預期外變動：

### 單元
```bash
uv run pytest tests/test_sources_spec.py -v
uv run pytest tests/test_discovery.py -v
```

### 向下相容（既有 bare-name 路徑）
```bash
uv run pytest tests/test_cli.py -k "add" -v          # 既有測試全綠
uv run skillpod add audit                             # 在示例 manifest 中應與目前一致
```

### Source-mode 專案安裝（核心）
```bash
cd /tmp/demo && uv run skillpod init
uv run skillpod add anthropics/skills -l                 # 列出 skills + descriptions
uv run skillpod add anthropics/skills -s pdf -s docx -y   # 兩個 skills 安裝
cat skillfile.yml                                          # 應出現 sources: anthropics-skills + skills: pdf/docx
ls .skillpod/skills/ .claude/skills/                       # 兩處都看得到 pdf, docx
uv run skillpod doctor                                    # 全綠
```

### Source-mode 全域安裝
```bash
uv run skillpod add anthropics/skills -s pdf -g -a claude -y
ls ~/.skillpod/skills/pdf                                 # materialized
ls -la ~/.claude/skills/pdf                               # symlink 指回 ~/.skillpod/skills/pdf
ls ~/.codex/skills/pdf                                    # 不存在（`-a claude` 限定）
uv run skillpod global list                               # pdf 出現在 claude 列
```

### 失敗 rollback
```bash
uv run skillpod add anthropics/skills -s does-not-exist -y
# expect: 非 0 exit；skillfile.yml 內容與執行前完全一致（diff 為空）
```

### 整合 + JSON
```bash
uv run skillpod add anthropics/skills -s pdf --json | jq .  # JSON shape 含 added, source, commit
uv run pytest -v                                            # 全 suite 綠
```

### Lint / type
```bash
uv run ruff check src tests
uv run mypy src                                              # 若 repo 有設定
```
