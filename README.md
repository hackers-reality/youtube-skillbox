<div align="center">
  <img src="assets/banner.svg" alt="YouTube Skillbox — 13 free YouTube skills for AI agents" width="100%">
</div>

<h1 align="center">YouTube Skillbox</h1>

<p align="center">
  <b>13 free YouTube skills for AI agents — research, transcripts, and the full creator workflow.</b><br>
  No API key · no credits · no expiry — <b>$0 forever</b>
</p>

<p align="center">
  <a href="#-table-of-contents">Table of Contents</a> ·
  <a href="#-demo">Demo</a> ·
  <a href="#-the-youtube-research-skill">Research</a> ·
  <a href="#-the-transcript-skill">Transcripts</a> ·
  <a href="#-when-yt-dlp-cant-do-it-we-build-it">Gap-fill engine</a> ·
  <a href="#%EF%B8%8F-the-11-creator-skills">Creator tools</a> ·
  <a href="#-install">Install</a> ·
  <a href="#-have-your-agent-set-it-up-for-you">Agent prompt</a>
</p>

---

## 📺 Demo

Watch the agent in action — OpenCode fetching MKBHD's full channel breakdown (tab counts, home shelves with Featured Channels URLs, paginated community posts, and a timestamped transcript):

<div align="center">
  <a href="https://www.youtube.com/watch?v=y9U_ZeJ713M" target="_blank">
    <img src="https://img.youtube.com/vi/y9U_ZeJ713M/maxresdefault.jpg" alt="YouTube Skillbox Demo" width="80%">
  </a>
  <br>
  <sub>Click to watch on YouTube →</sub>
</div>

---

## 📋 Table of Contents

| Section | Description |
|---------|-------------|
| [📺 Demo](#-demo) | Video walkthrough of the agent using the skills |
| [What is this?](#what-is-this) | Overview of the two-layer architecture |
| [📺 The `youtube` research skill](#-the-youtube-research-skill) | 10 subcommands for search, channels, posts, shows, etc. |
| [📜 The `transcript` skill](#-the-transcript-skill) | Free transcripts via yt-dlp |
| [🛠 Gap-fill engine](#-when-yt-dlp-cant-do-it-we-build-it) | How we fill yt-dlp's gaps with raw scrapers |
| [✂️ The 11 creator skills](#%EF%B8%8F-the-11-creator-skills) | Scripts, SEO, chapters, Shorts, audits, and more |
| [📦 Install](#-install) | Quick setup for any agent harness |
| [🤖 Have your agent set it up for you](#-have-your-agent-set-it-up-for-you) | Copy-paste prompt for any coding agent |
| [📝 Notes & limits](#-notes--limits) | Rate limits, pagination, edge cases |
| [📄 License](#-license) | MIT License |
| [🙏 Credits](#-credits) | yt-dlp, upstream skill sources |

---

## What is this?

A drop-in set of **[SKILL.md](https://github.com/anthropics/skills) skills** for agent harnesses like **OpenCode** (works anywhere skills are discovered from a folder). Each skill in [`skills/`](skills/) is self-contained: a `SKILL.md` the agent reads, plus small Python tools it runs.

Two layers:

| Layer | Skills | Powered by |
| ----- | ------ | ---------- |
| **Data** (research) | `youtube`, `transcript` | `yt-dlp` + custom raw YouTube scrapers |
| **Creator workflow** | 11 × `yt-*` | local Python scripts, zero network deps for logic |

Everything is free. There is **no paid tier, no API key, and no account** anywhere in the stack.

---

## 📺 The `youtube` research skill

Ten subcommands behind one script — `skills/youtube/scripts/ytdata.py`:

```bash
python scripts/ytdata.py search "query" --limit 10     # find videos on a topic
python scripts/ytdata.py profile "@handle"             # About: subs, description, keywords
python scripts/ytdata.py sections "@handle"            # count EVERY tab at once
python scripts/ytdata.py home "@handle"                # home shelves + Featured Channels
python scripts/ytdata.py channel "@handle" --tab shorts
python scripts/ytdata.py latest "@handle" --limit 10
python scripts/ytdata.py posts "@handle" --limit 30    # community posts, paginated
python scripts/ytdata.py shows "@handle"               # Shows tab (episode collections)
python scripts/ytdata.py playlist "<playlist-url>"
python scripts/ytdata.py info "<video-url-or-id>"      # views, likes, tags, date
```

Add `--json` to any command for structured output. Example:

```
$ python scripts/ytdata.py sections "@MrBeast"
Channel: https://www.youtube.com/@MrBeast
  videos   : 805
  shorts   : 205
  streams  : no tab
  shows    : 5
  playlists: no tab
  community: 20+ posts (use `posts` to read them)
```

| Command | Returns |
| ------- | ------- |
| `search` | Videos matching a query — title, duration, views, channel, URL |
| `profile` | Channel About section — name, handle, subs, description, **all** keywords |
| `sections` | One-call counts of every tab: videos / shorts / streams / shows / playlists / posts |
| `home` | Home-tab shelves — featured video, Shorts, playlists, posts, **Featured Channels** (names + URLs) |
| `channel` | Channel uploads (`--tab videos \| shorts \| streams`) |
| `latest` | Most recent uploads, reverse-chronological |
| `posts` | Community posts — text, author, date, like count, URL. **Paginated** (~10/page) |
| `shows` | Shows tab — title, episode count, URL |
| `playlist` | Every video in a playlist |
| `info` | One video's exact stats — views, likes, subs, date, tags, categories, description |

---

## 📜 The `transcript` skill

Spoken text of any video, free via yt-dlp:

```bash
python scripts/gettranscript.py "<url-or-id>"                    # clean text
python scripts/gettranscript.py "<url-or-id>" --format stamped   # [MM:SS] per line
python scripts/gettranscript.py "<url-or-id>" --format json      # segments + metadata
python scripts/gettranscript.py "<url-or-id>" --lang es,es-419   # language priority list
```

Prefers human captions, falls back to auto-generated. The JSON form carries `start`/`duration` per cue — ready for chapters, quotes, or edit lists.

---

## 🛠 When yt-dlp can't do it, we build it

`yt-dlp` is the data engine for search, channels, playlists, metadata and transcripts — but it explicitly refuses a few things (returns `0 entries` or `"no home tab"`). Rather than pay an API, each gap is filled with **a small pure-Python scraper** (`urllib` + JSON parsing of YouTube's own page data / Innertube endpoints):

| Gap | What yt-dlp does | Our fill |
| --- | ---------------- | -------- |
| **Community posts** | `/community` → `0 entries` (wontfix) | Raw `ytInitialData` scrape of `/posts` (with `/community` fallback) |
| **Post pagination** | — | **Innertube `browse` continuation POSTs** — the exact request infinite-scroll fires when you scroll. `--limit 30` reaches ~3 pages / months back |
| **Home sections** | `"This channel does not have a home tab"` | Home-tab shelf parser: featured video, Shorts, playlists, posts, and **Featured Channels** with URLs |
| **Shows tab** | `0 entries` (can't parse `gridShowRenderer`) | Direct renderer parser → title, episode count, show URL |
| **Tab counts** | one tab per invocation | `sections` probes every tab and merges yt-dlp + raw results |

All of it is dependency-free Python — no API key, no credits, no tokens to manage.

```
$ python scripts/ytdata.py home "@MKBHD" --limit 3
  1. [featured video] Macbook PROLED XDR Impressions: ...  (1 item)
  2. [videos] Videos  (12 items)
  3. [featured channels] 🔥 MKBHD Approved 🔥  (6 items)
       - The Studio      https://www.youtube.com/channel/UCG7J20...
       - Auto Focus      https://www.youtube.com/channel/UC2J-0g...
       - WVFRM Podcast   https://www.youtube.com/channel/UCEcrRX...
```

---

## ✂️ The 11 creator skills

Local tools that turn raw transcripts/data into publishing artifacts:

| Skill | Does |
| ----- | ---- |
| `yt-script` | Full video script from a raw idea — 21 hook formulas, scored |
| `yt-package` | Title + thumbnail text written and linted as one pairing |
| `yt-seo` | Description, tags and search-facing text aimed at real queries |
| `yt-chapters` | Validated YouTube chapters straight from a transcript |
| `yt-shorts` | Finds the self-contained Shorts hiding inside a long video |
| `yt-edit` | Transcript → edit decision list (dead air, fillers, retakes) |
| `yt-retention` | Reads a Studio retention export, says where viewers leave |
| `yt-audit` | End-to-end channel audit — packaging, consistency, first 15s |
| `yt-viral` | What's actually working in a niche, ranked by channel-beat |
| `yt-plan` | A week/month content calendar sized to real capacity |
| `yt-comment` | Drafts comment replies in the creator's voice, triaged |

They pair naturally with the data layer: `youtube` finds the videos → `transcript` pulls the text → `yt-*` does the work.

---

## 📦 Install

**Requirements:** Python 3.10+ and [`yt-dlp`](https://github.com/yt-dlp/yt-dlp):

```bash
python -m pip install --user -U yt-dlp
```

> `posts`, `home` and `shows` work even *without* yt-dlp (pure HTTP). Everything else runs through it. Run it as a module (`python -m yt_dlp`) if the exe isn't on PATH.

Then, from this repo — point the installer at **your agent's skills directory** (where it discovers `SKILL.md` files):

```bash
./install.sh "/path/to/your/agents/skills"          # Linux / macOS — e.g. ~/.config/opencode/skills
```

```powershell
.\install.ps1 "C:\path\to\your\agents\skills"       # Windows — e.g. %USERPROFILE%\.config\opencode\skills
```

…or by hand — copy any folder from [`skills/`](skills/) there yourself:

```bash
cp -r skills/* ~/.config/opencode/skills/            # example: OpenCode
```

Restart the agent session; the skills are auto-discovered by their `description` frontmatter.

---

## 🤖 Have your agent set it up for you

Don't want to install by hand? Paste this into any coding agent that can read files — **Claude Code, OpenCode, or whatever you use**:

```text
Set up my YouTube skills from https://github.com/hackers-reality/youtube-skillbox

1. Get the repo: git clone https://github.com/hackers-reality/youtube-skillbox.git
   (if you can't clone, fetch the files from the GitHub page instead)
2. Copy every folder inside its skills/ directory into my agent's skills
   directory (the folder where you discover SKILL.md files — for OpenCode
   that's ~/.config/opencode/skills; if you use a different one, use yours
   and tell me which path you chose).
3. Make sure the data engine is installed: python -m pip install --user -U yt-dlp
4. Smoke-test it: run
   python <skills-dir>/youtube/scripts/ytdata.py search "rick astley" --limit 1
   and show me the output.
5. Then list the 13 skills you can now use (youtube, transcript, and the
   11 yt-* ones) with one line each on when you'd use them.
   Read each skills/*/SKILL.md for the details — don't ask me, infer from those.
```

---

## 📝 Notes & limits

- YouTube may throttle (HTTP 429) if you hammer it — a small delay between bulk calls is enough.
- `posts` costs one HTTP request per ~10 posts; keep `--limit` ≤ 100 per invocation.
- `sections` shows `N+` for community counts when more pages exist (exact when they fit on page 1).
- Flat list view counts can show `?` occasionally — use `info` on a specific video for exact numbers.
- Private / age-restricted / deleted targets fail with a clear message instead of silence.

## 📄 License

Released under the **[MIT License](LICENSE)** — free to use, modify, and redistribute.

## 🙏 Credits

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — the extraction engine underneath the data layer.
- The 11 creator (`yt-*`) skills come from the community GitHub collection **`youtube-agent-skill`** — installed here nearly as-is (deduplicated only), not rewritten from scratch.
- The `youtube` and `transcript` skills (scripts and docs, including every gap-fill in this README) were built and rewritten in this project.
- This project reads publicly available YouTube data; use it responsibly and respect YouTube's Terms of Service.

<p align="center">Made so nobody has to pay for a YouTube API key again 🎉</p>