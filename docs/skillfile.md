# `skillfile.yml` reference / 參考

[← README](../README.md) · [English](#english) · [繁體中文](#繁體中文)

---

## English

Only `version` is required. Everything below shows its default.

```yaml
version: 1

# Agents that receive fan-out. Empty means skills land in .skillpod/skills/
# only. Supported: claude, codex, gemini, cursor, opencode, antigravity.
agents: [claude]

install:
  mode: symlink          # symlink | copy | hardlink
  fallback: [copy]       # tried when `mode` fails (e.g. symlinks denied)
  on_missing: error      # error | skip
  prefer_global: true    # a skill already in ~/.skillpod/skills/ counts as satisfied

sources:
  - name: skills
    type: git            # git | local
    url: https://github.com/anthropics/skills
    ref: main            # branch, tag, or commit
    subpath: skills      # git only — where the skills live inside the repo
    priority: 50         # higher wins when several sources could provide a skill

skills:
  - audit                          # shorthand: resolve against sources, then the registry
  - name: pdf
    source: skills                 # pin to one source, skipping the registry
    version: <40-char commit sha>  # optional: pin to an exact commit

groups:                  # named bundles, activated by `use:`
  frontend: [pdf, docx]
use: [frontend]

registry:
  default: skills.sh
  skills_sh:
    allow_unverified: false
    min_installs: 0
    min_stars: 0

profiles:                # named subsets, see `skillpod switch`
  minimal:
    skills: [pdf]

activation:
  mode: manual           # manual | strict | merge | fallback
  inherit_global: true
  default_profile: null
```

Run `skillpod schema --output schemas/skillfile.schema.json` for editor
autocomplete, or `skillpod schema --profile` for the global profile schema.

See also: [Guide](./guide.md) · [How it works](./how-it-works.md)

---

## 繁體中文

只有 `version` 是必填。以下每一項顯示的都是預設值。

```yaml
version: 1

# 接受 fan-out 的 agent。留空代表 skill 只會落在 .skillpod/skills/。
# 支援：claude、codex、gemini、cursor、opencode、antigravity。
agents: [claude]

install:
  mode: symlink          # symlink | copy | hardlink
  fallback: [copy]       # 當 `mode` 失敗時的備援（例如 symlink 被禁止）
  on_missing: error      # error | skip
  prefer_global: true    # 已在 ~/.skillpod/skills/ 的 skill 視為已滿足

sources:
  - name: skills
    type: git            # git | local
    url: https://github.com/anthropics/skills
    ref: main            # branch、tag 或 commit
    subpath: skills      # 僅限 git —— skill 在 repo 中的位置
    priority: 50         # 多個 source 都能提供同一個 skill 時，數字大的勝出

skills:
  - audit                          # 簡寫：先比對 sources，再查 registry
  - name: pdf
    source: skills                 # 固定使用某個 source，略過 registry
    version: <40-char commit sha>  # 選填：釘在特定 commit

groups:                  # 具名組合，由 `use:` 啟用
  frontend: [pdf, docx]
use: [frontend]

registry:
  default: skills.sh
  skills_sh:
    allow_unverified: false
    min_installs: 0
    min_stars: 0

profiles:                # 具名子集合，參見 `skillpod switch`
  minimal:
    skills: [pdf]

activation:
  mode: manual           # manual | strict | merge | fallback
  inherit_global: true
  default_profile: null
```

執行 `skillpod schema --output schemas/skillfile.schema.json` 可取得編輯器自動完成用的
schema，或用 `skillpod schema --profile` 取得全域 profile 的 schema。

延伸閱讀：[使用指南](./guide.md#繁體中文) · [運作方式](./how-it-works.md#繁體中文)
