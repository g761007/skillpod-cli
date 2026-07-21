# How it works / 運作方式

[← README](../README.md) · [English](#english) · [繁體中文](#繁體中文)

---

## English

```
skillfile.yml  →  resolve  →  cache  →  .skillpod/skills/  →  .<agent>/skills/
```

1. **Resolve.** A skill declared with `source:` is looked up there. A bare name
   probes declared sources by priority, then falls back to the skills.sh
   registry.
2. **Cache.** Git sources clone into `~/.cache/skillpod/<host>/<owner>/<repo>@<commit>/`,
   written by atomic rename so a partial clone is never visible.
3. **Materialise.** `.skillpod/skills/<name>/` is a real directory copy, never
   a symlink — clearing the cache cannot break an installed project.
4. **Fan out.** Each declared agent gets `.<agent>/skills/<name>` pointing at
   that copy, using `install.mode`.

**What gets recorded.** `.skillpod/installed.yml` (and `~/.skillpod/installed.yml`
for global installs) records what is on this machine: source, ref, commit,
content digest. Both live under `.skillpod/`, which is gitignored — they
*describe* your machine, they do not constrain a teammate's.

**`install` versus `update`.** `install` brings in what is missing and leaves
alone what is already there, so re-running it is offline and instant. Pulling
newer upstream content is `skillpod update` — always an explicit act, never a
side effect.

### Security model — what you're trusting

Adding a skill pulls external text into your agent's context. A `SKILL.md` is
read as *instructions*, so review a repo before adding it, the same way you
would review a package before installing it.

**The registry trust policy gates skills.sh only.** `registry.skills_sh`
(`allow_unverified`, `min_installs`, `min_stars`) applies when you `search` or
resolve a bare name through the registry. Passing a git URL, an `owner/repo`
shorthand, or a local path to `skillpod add` trusts that source directly — no
threshold is checked.

**Content is digested, not policed.** Each install records a sha256 of what it
materialised, so `skillpod doctor` can tell you the disk no longer matches the
record. That detects drift and corruption; it does not vet the content.

To report a vulnerability in skillpod itself, see [`SECURITY.md`](../SECURITY.md).

See also: [`skillfile.yml` reference](./skillfile.md) ·
[Troubleshooting](./troubleshooting.md)

---

## 繁體中文

```
skillfile.yml  →  resolve  →  cache  →  .skillpod/skills/  →  .<agent>/skills/
```

1. **Resolve（解析）。** 有寫 `source:` 的 skill 直接到該來源查找。只寫名稱的
   則依 priority 依序探測已宣告的 source，最後才回退到 skills.sh registry。
2. **Cache（快取）。** git 來源會 clone 到
   `~/.cache/skillpod/<host>/<owner>/<repo>@<commit>/`，透過 atomic rename 寫入，
   所以永遠不會看到 clone 到一半的狀態。
3. **Materialise（實體化）。** `.skillpod/skills/<name>/` 是真正的目錄複本，
   絕不是 symlink —— 清掉 cache 不會弄壞已安裝的專案。
4. **Fan out（扇出）。** 每個宣告的 agent 都會得到指向該複本的
   `.<agent>/skills/<name>`，方式由 `install.mode` 決定。

**會被記錄下來的東西。** `.skillpod/installed.yml`（全域安裝則是
`~/.skillpod/installed.yml`）記錄這台機器上的狀態：source、ref、commit、
內容摘要。兩者都位於已被 gitignore 的 `.skillpod/` 之下 ——
它們*描述*你的機器，不會去約束同事的機器。

**`install` 與 `update` 的差別。** `install` 只補上缺少的，已經在的就不動它，
所以重複執行是離線且瞬間完成的。要拉取較新的上游內容請用 `skillpod update` ——
這永遠是明確的動作，絕不會是副作用。

### 安全模型 —— 你正在信任什麼

加入一個 skill，等於把外部文字拉進 agent 的 context。`SKILL.md` 會被當成*指令*讀取，
所以在加入某個 repo 之前請先審視它，就像你安裝套件前會先檢查一樣。

**registry 的信任政策只管得到 skills.sh。** `registry.skills_sh`
（`allow_unverified`、`min_installs`、`min_stars`）只在你 `search`，
或透過 registry 解析一個裸名稱時生效。直接把 git URL、`owner/repo` 簡寫
或本機路徑傳給 `skillpod add`，等於直接信任該來源 —— 不會檢查任何門檻。

**內容只做摘要，不做審查。** 每次安裝都會記錄實體化內容的 sha256，
所以 `skillpod doctor` 能告訴你磁碟上的內容已經與紀錄不符。
這能偵測漂移與損毀；但它不會替你審查內容本身。

要回報 skillpod 本身的安全漏洞，請見 [`SECURITY.md`](../SECURITY.md)。

延伸閱讀：[`skillfile.yml` 參考](./skillfile.md#繁體中文) ·
[疑難排解](./troubleshooting.md#繁體中文)
