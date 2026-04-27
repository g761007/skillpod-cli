# skillpod-cli 專案計畫書

> Pod-style dependency manager for AI coding agent skills.
> One declarative manifest, multi-agent fan-out.

> **skillpod is a project-scoped, reproducible skill dependency manager — not a global skill installer.**
> **Discover skills from skills.sh, depend on them with skillpod.**

**Date**: 2026-04-27  
**Author**: Daniel Hsieh  
**Status**: Draft — pending implementation

---

# 1. 定位 (Positioning)

## 解決什麼問題

1. Skill bloat（global skills 汙染）
2. Multi-agent 重複維護
3. 不可重現（沒有 lockfile）
4. Skill discovery 困難（缺乏統一 registry）

---

## 核心理念

- project-scoped dependency
- reproducible (lockfile)
- multi-agent abstraction
- registry ≠ source of truth

---

# 2. 架構總覽

## 2.1 系統分層

~~~
skills.sh (registry / discovery layer)
        ↓
git repo (immutable commit)
        ↓
.skillpod/skills (project install)
        ↓
agents (symlink fan-out)
~~~

說明：

- skills.sh 是技能目錄與排行榜平台  [oai_citation:0‡ToolWorthy](https://www.toolworthy.ai/tool/skills-sh?utm_source=chatgpt.com)
- skillpod 只使用它做 discovery，不作為 source of truth

---

## 2.2 目錄結構

~~~
# Global cache（只做加速）
~/.cache/skillpod/
  github.com/
    <org>/<repo>@<ref>/

# Project（唯一 source of truth）
project/
  .skillpod/
    skills/
    user_skills/
~~~

---

## 2.3 Agent fan-out

~~~
.claude/skills
.codex/skills
.gemini/skills
.cursor/skills
.opencode/skills
.antigravity/skills
~~~

---

# 3. skillfile.yml

## 3.1 Schema

~~~
version: 1

registry:
  default: skills.sh

  skills.sh:
    allow_unverified: false
    min_installs: 1000
    min_stars: 50

agents:
  - claude
  - codex
  - gemini

install:
  mode: symlink
  on_missing: error

sources:
  - name: local
    type: local
    path: ~/.agents/skills
    priority: 100

  - name: anthropic
    type: git
    url: https://github.com/anthropics/skills
    ref: main
    priority: 80

skills:
  - audit
  - polish

  - name: custom-skill
    source: anthropic

groups:
  frontend:
    - audit
    - web-design

use:
  - frontend
~~~

---

# 4. Registry Layer（skills.sh）

## 4.1 定位

skills.sh 是：

- AI agent skills directory / leaderboard  [oai_citation:1‡Vibe Coding](https://vibecoding.app/blog/skills-sh-review?utm_source=chatgpt.com)  
- 聚合 GitHub skill repo 的 discovery 平台  [oai_citation:2‡Sofind AI](https://sofindai.com/tools/skills-sh?utm_source=chatgpt.com)  
- 提供搜尋、排行與安裝入口  

---

## 4.2 使用原則

~~~
skills.sh = discovery layer
git commit = source of truth
~~~

---

## 4.3 install 時流程

~~~
skillpod add audit

1. 查詢 skills.sh
2. 過濾（verified / installs / stars）
3. 取得 GitHub repo
4. resolve → commit
5. 寫入 lockfile
~~~

---

## 4.4 關鍵設計

### registry 不進 lockfile

~~~
❌ 不記錄 skills.sh
✅ 只記錄 git commit
~~~

---

### registry 只負責

- discovery
- metadata
- trust signal

---

## 4.5 安全性

skills.sh 官方也指出：

~~~
⚠️ 無法保證所有 skill 的品質與安全
~~~

 [oai_citation:3‡Skills](https://skills.sh/docs?utm_source=chatgpt.com)

因此：

- 必須透過 trust policy 過濾
- 不可直接信任 registry

---

# 5. skillfile.lock

~~~
version: 1

resolved:
  audit:
    source: git
    url: https://github.com/vercel-labs/agent-skills
    commit: abc123
    sha256: xxxx
~~~

---

# 6. 安裝流程

~~~
skillpod install

1. 讀 skillfile.yml
2. resolve skills（含 groups）
3. 若無 source → 查 registry
4. git clone（cache）
5. install → .skillpod/skills
6. 建立 agent symlink
7. 產生 lockfile
~~~

---

# 7. Cache 設計

~~~
~/.cache/skillpod/
  github.com/org/repo@ref/
~~~

特性：

- immutable
- shared
- 可安全清除
- 不影響 project reproducibility

---

# 8. Global Skills 策略

## 不管理 global

原因：

- 不可控
- 不可 reproducible
- 汙染依賴

---

## CLI 工具

~~~
skillpod global list
skillpod global archive <skill>
skillpod global doctor
~~~

---

# 9. User Skills

~~~
.skillpod/user_skills/
~~~

優先順序：

~~~
user_skills > sources > registry
~~~

---

# 10. CLI 設計

~~~
skillpod init
skillpod install
skillpod add <skill>
skillpod remove <skill>
skillpod list
skillpod sync
skillpod update
skillpod outdated
skillpod doctor

skillpod search
skillpod global list
~~~

---

# 11. Sources 設計

支援：

- local
- git

resolution：

~~~
priority 高 → 低
~~~

---

# 12. 關鍵設計決策

## 為什麼使用 skills.sh

- 最大 skills 生態（數萬個 skill）  [oai_citation:4‡Sofind AI](https://sofindai.com/tools/skills-sh?utm_source=chatgpt.com)  
- 類 npm 的 discovery 模型  [oai_citation:5‡John Oct](https://johnoct.com/blog/2026/02/12/skills-sh-open-agent-skills-ecosystem/?utm_source=chatgpt.com)  
- 支援多 agent  

---

## 為什麼不能直接當 source

- ranking 會變
- repo 可能消失
- 不保證安全

---

## skillpod 解法

- resolve → commit
- lockfile 固定
- project-scoped install

---

# 13. Roadmap

| 版本 | 功能 |
|------|------|
| 0.1.0 | install + registry |
| 0.2.0 | search + trust policy |
| 0.3.0 | groups |
| 0.4.0 | adapter layer |
| 1.0.0 | schema freeze |

---

# 14. 核心價值

~~~
discover → resolve → lock → install
~~~

> skills.sh = discovery  
> skillpod = dependency system