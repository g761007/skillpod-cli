# Guide / 使用指南

[← README](../README.md) · [English](#english) · [繁體中文](#繁體中文)

---

## English

Task-oriented recipes. Each entry starts from something you want to do.

### …recommend a set of skills for this project

`skillfile.yml` is the recommendation. Commit it, and a teammate who wants the
same setup runs one command.

```yaml
version: 1
agents: [claude]

sources:
  - name: skills
    type: git
    url: https://github.com/anthropics/skills
    ref: main
    subpath: skills

skills:
  - name: pdf
    source: skills
  - name: docx
    source: skills
```

```bash
skillpod install
```

Nothing here is enforced. A teammate who ignores it, or already has these
skills globally, is not doing anything wrong — see the next entry.

### …not install a skill I already have globally

This is the default. If a skill is already in `~/.skillpod/skills/`, the
recommendation is already met, so no project copy is made:

```console
$ skillpod install
Already present: 2 skill(s)
Satisfied by your global install: xlsx
```

It applies only where **every** agent you declare is known to read its personal
*and* project skill directories together. Verified today: **Claude Code,
Codex, and Gemini CLI**. Declare any other agent and that project gets a real
copy instead — an unverified agent is assumed *not* to merge, because a
silently missing skill is far worse than a redundant copy.

To force a project-local copy anyway:

```yaml
install:
  prefer_global: false
```

The three verified agents each resolve a name collision differently, so
`skillpod install` warns only where the project copy really is ignored:

| Agent | Same skill name in both places |
|---|---|
| Claude Code | the **personal** copy wins ([docs](https://code.claude.com/docs/en/skills)) — so `prefer_global: false` warns you the project copy is not the one in use |
| Gemini CLI | the **project** copy wins |
| Codex | neither — both appear in the skill selector |

### …see what I actually have right now

```console
$ skillpod status
project:    my-project
manifest:   /path/to/skillfile.yml

recommends: 4 skill(s)
  satisfied: 2   (1 global, 1 project)
  missing:   1   → skillpod install
  broken:    1   → skillpod doctor
```

Every count names the command that fixes it. For the per-skill breakdown:

```console
$ skillpod list
NAME      SOURCE    LAYER     INSTALLED
pdf       skills    project   fa0fa64bdc96
docx      skills    project   fa0fa64bdc96
```

`LAYER` says which copy is actually serving each skill: `project`, `global`,
`user`, `missing`, or `broken`.

### …install a skill for every project, not just this one

```bash
skillpod add anthropics/skills --skill xlsx -g -y
```

This puts the skill in `~/.skillpod/skills/` **without** wiring it into any
agent — that is a deliberate second step, so a global install never silently
changes what your agents see:

```bash
skillpod global link xlsx --agent claude    # or omit --agent for all of them
skillpod global list
```

```
NAME  LINKED     SIZE  MTIME
xlsx  cl      1102893  2026-07-21
```

### …turn a skill off without deleting it

```bash
skillpod unlink audit             # this project
skillpod unlink xlsx -g           # globally
```

The materialised copy stays put, so `skillpod link audit` brings it back with
no download. Only skillpod-created links are removed — anything you placed by
hand is reported and left alone.

This is deliberately not `remove`: that deletes the content and edits
`skillfile.yml`, which is much more than "stop showing me this".

### …use a skill I already have, in a project that doesn't declare it

```console
$ skillpod link xlsx
Copied 'xlsx' from ~/.skillpod/skills/ — nothing downloaded.
Linked to: claude
```

`link` never fetches. If the skill is already on your machine — in this project
or globally — it wires it up; if it is nowhere, it tells you to run
`skillpod add`.

### …update my global skills

```console
$ skillpod global update --dry-run
Would update 18 skill(s):
  algorithmic-art              5128e1865d67 → fa0fa64bdc96
  brand-guidelines             5128e1865d67 → fa0fa64bdc96
  …
  local        33 skill(s) — no upstream to pull from
  no source    37 skill(s) — origin unknown, reinstall from a source to make them updatable
```

Drop `--dry-run` to apply, or name specific skills:

```bash
skillpod global update pdf docx
```

Skills with no recoverable origin, skills from local directories, and remotes
that cannot be reached are reported and skipped — never fatal. One dead remote
does not stop the rest.

### …run only some of this project's skills right now

```console
$ skillpod switch minimal
active profile set to 'minimal' (scope: project)
  hidden: polish (still installed — switching back is instant)
```

Declare the subsets in `skillfile.yml`:

```yaml
profiles:
  minimal:
    skills: [audit]
```

Hidden skills stay in `.skillpod/skills/`, so switching back is offline and
immediate. `install` and `sync` respect the active profile too — neither will
put a hidden skill back.

### …switch my whole global setup at once

Save what you have now, then move between named sets:

```bash
skillpod profile save writing            # snapshot the current global skills
skillpod switch reviewing --scope global # download what's missing, unlink the rest
skillpod switch --back                   # undo
```

Add `--dry-run` to preview the reconcile first, or `dev+reviewer` to union two
profiles.

### …use a skill that only exists on my machine

Drop it in `.skillpod/user_skills/<name>/` and run `skillpod install`. It needs
no source and no manifest entry, and it takes precedence over a declared skill
of the same name.

Next: [Commands](./commands.md) · [`skillfile.yml` reference](./skillfile.md) ·
[How it works](./how-it-works.md) · [Troubleshooting](./troubleshooting.md)

---

## 繁體中文

以任務為導向的操作情境。每一節都從「你想做什麼」開始。

### …為這個專案建議一組 skill

`skillfile.yml` 就是那份建議。把它提交進版控，想要相同環境的同事只要跑一道指令。

```yaml
version: 1
agents: [claude]

sources:
  - name: skills
    type: git
    url: https://github.com/anthropics/skills
    ref: main
    subpath: skills

skills:
  - name: pdf
    source: skills
  - name: docx
    source: skills
```

```bash
skillpod install
```

這裡沒有任何強制性。同事選擇忽略它，或是已經在全域裝過這些 skill，
都不算做錯事 —— 詳見下一節。

### …不要重複安裝我全域已經有的 skill

這是預設行為。如果某個 skill 已經在 `~/.skillpod/skills/`，就代表建議已經被滿足，
不會再複製一份到專案裡：

```console
$ skillpod install
Already present: 2 skill(s)
Satisfied by your global install: xlsx
```

這條規則只在**你宣告的每一個 agent** 都確定會同時讀取個人與專案 skill 目錄時才適用。
目前已驗證的有：**Claude Code、Codex、Gemini CLI**。只要宣告了其他 agent，
該專案就會拿到真正的複本 —— 未經驗證的 agent 一律假設它*不會*合併兩邊，
因為 skill 悄悄消失的後果，遠比多一份複本嚴重。

若想強制在專案內留一份複本：

```yaml
install:
  prefer_global: false
```

這三個已驗證的 agent 各自用不同方式處理名稱衝突，所以 `skillpod install`
只在專案複本真的會被忽略時才發出警告：

| Agent | 同名 skill 同時存在於兩處時 |
|---|---|
| Claude Code | **個人**複本勝出（[官方文件](https://code.claude.com/docs/en/skills)）—— 所以設 `prefer_global: false` 時會警告你專案複本並非實際生效的那份 |
| Gemini CLI | **專案**複本勝出 |
| Codex | 都不覆蓋 —— 兩份都會出現在 skill 選單裡 |

### …看看我現在到底裝了什麼

```console
$ skillpod status
project:    my-project
manifest:   /path/to/skillfile.yml

recommends: 4 skill(s)
  satisfied: 2   (1 global, 1 project)
  missing:   1   → skillpod install
  broken:    1   → skillpod doctor
```

每一項數字都會直接標出修正它的指令。想看逐一 skill 的細節：

```console
$ skillpod list
NAME      SOURCE    LAYER     INSTALLED
pdf       skills    project   fa0fa64bdc96
docx      skills    project   fa0fa64bdc96
```

`LAYER` 表示實際提供該 skill 的是哪一份複本：`project`、`global`、
`user`、`missing` 或 `broken`。

### …讓某個 skill 在所有專案都能用，而不只是這一個

```bash
skillpod add anthropics/skills --skill xlsx -g -y
```

這會把 skill 放進 `~/.skillpod/skills/`，但**不會**接到任何 agent ——
這是刻意分成第二個步驟，好讓全域安裝永遠不會在你沒察覺時改變 agent 看到的東西：

```bash
skillpod global link xlsx --agent claude    # 省略 --agent 則套用到全部
skillpod global list
```

```
NAME  LINKED     SIZE  MTIME
xlsx  cl      1102893  2026-07-21
```

### …先關掉某個 skill，但不要刪掉它

```bash
skillpod unlink audit             # 只針對這個專案
skillpod unlink xlsx -g           # 全域
```

實體化的複本會原地保留，所以 `skillpod link audit` 可以在不下載任何東西的情況下把它接回來。
只有 skillpod 自己建立的連結會被移除 —— 你手動放的東西只會被列出來，不會被動到。

這刻意不叫 `remove`：`remove` 會刪掉內容並且改寫 `skillfile.yml`，
遠超過「先別讓我看到這個」的需求。

### …在沒有宣告某個 skill 的專案裡，用我已經有的那份

```console
$ skillpod link xlsx
Copied 'xlsx' from ~/.skillpod/skills/ — nothing downloaded.
Linked to: claude
```

`link` 永遠不會下載。只要 skill 已經在你機器上 —— 不論在這個專案或全域 ——
它就會直接接起來；如果哪裡都找不到，它會叫你去跑 `skillpod add`。

### …更新我的全域 skill

```console
$ skillpod global update --dry-run
Would update 18 skill(s):
  algorithmic-art              5128e1865d67 → fa0fa64bdc96
  brand-guidelines             5128e1865d67 → fa0fa64bdc96
  …
  local        33 skill(s) — no upstream to pull from
  no source    37 skill(s) — origin unknown, reinstall from a source to make them updatable
```

拿掉 `--dry-run` 就會實際套用，或是指定特定 skill：

```bash
skillpod global update pdf docx
```

找不到來源的 skill、來自本機目錄的 skill，以及連不上的遠端，都只會被列出並跳過 ——
永遠不會中斷整個流程。一個掛掉的遠端不會拖垮其他的。

### …現在只想跑這個專案裡的部分 skill

```console
$ skillpod switch minimal
active profile set to 'minimal' (scope: project)
  hidden: polish (still installed — switching back is instant)
```

在 `skillfile.yml` 裡宣告這些子集合：

```yaml
profiles:
  minimal:
    skills: [audit]
```

被隱藏的 skill 仍留在 `.skillpod/skills/`，所以切回去是離線且即時的。
`install` 與 `sync` 同樣尊重目前生效的 profile —— 兩者都不會把隱藏的 skill 放回來。

### …一次切換整套全域設定

先把現在的狀態存起來，之後就能在具名的組合之間移動：

```bash
skillpod profile save writing            # 為目前的全域 skill 拍一張快照
skillpod switch reviewing --scope global # 下載缺少的、解除其餘的連結
skillpod switch --back                   # 還原
```

加上 `--dry-run` 可以先預覽這次調和的結果，或用 `dev+reviewer` 聯集兩個 profile。

### …使用只存在我機器上的 skill

把它放進 `.skillpod/user_skills/<name>/` 然後跑 `skillpod install`。
它不需要 source，也不需要寫進 manifest，而且會優先於同名的已宣告 skill。

接著看：[指令](./commands.md#繁體中文) · [`skillfile.yml` 參考](./skillfile.md#繁體中文) ·
[運作方式](./how-it-works.md#繁體中文) · [疑難排解](./troubleshooting.md#繁體中文)
