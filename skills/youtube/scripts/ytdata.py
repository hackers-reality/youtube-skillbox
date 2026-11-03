#!/usr/bin/env python3
"""
YouTube research via yt-dlp + raw page scraping: search, channels, playlists,
metadata, community posts (paginated), home sections, shows, keyword research
and rank tracking. No API key, no credits.

Subcommands:
  search     <query>              Search YouTube videos.
  keywords   <seed>               Keyword ideas + relative demand (YouTube + DDG suggest).
  compete    <query>              Competition score (0–100) for a keyword from live SERP.
  trends     <seed>               Historical trend for a seed keyword (from keywords runs).
  track      <query> --video URL  Rank position for a keyword, with ↑↓ history.
  scorecard  <video> --keyword    SEO checklist for a video (title/desc/tags/keyword fit).
  outliers   <handle>             Videos overperforming their channel (views/subs ratio).
  gap        <seed> --competitor  Content gap: my seed vs competitor's profile keywords.
  profile    <handle-or-url>      Channel About/profile section.
  sections   <handle-or-url>      Count every tab (videos/shorts/shows/playlists/posts).
  channel    <handle-or-url>      List a channel's uploads.
  latest     <handle-or-url>      Most recent uploads (reverse-chronological).
  posts      <handle-or-url>      Community posts — paginates past the first page.
  home       <handle-or-url>      Home tab shelves (Featured Channels, sections).
  shows      <handle-or-url>      Channel Shows (episode collections).
  playlist   <url-or-id>          List a playlist's videos.
  info       <url-or-id>          Full metadata for one video (views, likes, date, tags).

Common flags:
  --limit N        Max results (default 10; max ~50 per call for search).
  --json           Emit structured JSON instead of readable text.
  --tab            channel only: videos (default) | shorts | streams
  --gl XX --hl YY  search/keywords/track: pin region + language (default US / en).
  --sources        keywords only: engines to merge (default yt,ddg).

Requires: pip install yt-dlp  (posts/home/shows/search/keywords/track work without it)
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def run_ytdlp(args):
    cmd = [sys.executable, "-m", "yt_dlp"] + args + ["--no-warnings", "--no-write-thumbnail"]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


# ---- Community posts via raw Innertube page scrape (no yt-dlp; it can't do this) ----

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
       "Accept-Language": "en-US,en;q=0.9"}


def _http_get(url):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _extract_ytInitialData(html):
    """Pull the ytInitialData blob. YouTube serves it as `var ytInitialData`,
    `window["ytInitialData"]`, etc. — try every known form."""
    for pat in (r"var ytInitialData\s*=\s*(\{.*?\});</script>",
                r"window\[.ytInitialData.\]\s*=\s*(\{.*?\});",
                r"ytInitialData\s*=\s*(\{.*?\});"):
        m = re.search(pat, html, re.S)
        if not m:
            continue
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
    return None


def _extract_ytcfg(html):
    """Pull INNERTUBE_API_KEY + INNERTUBE_CONTEXT from the page's ytcfg blob."""
    m = re.search(r"ytcfg\.set\((\{.*?\})\);", html, re.S)
    if not m:
        return None, None
    try:
        cfg = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None, None
    return cfg.get("INNERTUBE_API_KEY"), cfg.get("INNERTUBE_CONTEXT")


def _innertube_browse(token, api_key, context):
    """POST to the Innertube browse endpoint with a continuation token.

    This is exactly what the browser does when you scroll the community feed —
    the token IS the 'next page'.
    """
    payload = json.dumps({"context": context, "continuation": token}).encode("utf-8")
    url = f"https://www.youtube.com/youtubei/v1/browse?key={api_key}"
    headers = dict(_UA, **{"Content-Type": "application/json"})
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


# ---- Locale-aware search via raw Innertube (gap-fill: yt-dlp has no region flag) ----
# yt-dlp localizes every search to whatever country the request comes from —
# its context ships gl=<your IP's country> and there is no flag to override it
# (no `gl`/`region` extractor-arg exists). A rank position that depends on where
# you're sitting isn't a rank position, so we call the endpoint ourselves and
# pin client.gl / client.hl. Also means search works with no yt-dlp installed.

_YT_SEARCH_PARAMS = "EgIQAfABAQ=="  # videos-only filter (the same param yt-dlp sends)
_cfg_cache = {}


def _innertube_cfg():
    """Read INNERTUBE_API_KEY + INNERTUBE_CONTEXT off the homepage (cached per run)."""
    if not _cfg_cache:
        key, ctx = _extract_ytcfg(_http_get("https://www.youtube.com/"))
        if not key or not ctx:
            raise RuntimeError("could not read YouTube's innertube config")
        _cfg_cache["key"], _cfg_cache["context"] = key, ctx
    return _cfg_cache["key"], _cfg_cache["context"]


def _innertube_post(endpoint, payload):
    key, _ = _innertube_cfg()
    url = f"https://www.youtube.com/youtubei/v1/{endpoint}?key={key}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=dict(_UA, **{"Content-Type": "application/json"}),
                                 method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _parse_count(txt):
    """'1,234,567 views' / '1.2M views' / 'No views' → int (None if absent)."""
    if not txt:
        return None
    if re.search(r"no\s+views", txt, re.I):
        return 0
    m = re.search(r"(\d[\d,\.\s]*?)\s*([KMB])?(?:\s|$)", txt, re.I)
    if not m:
        return None
    raw = m.group(1).strip()
    if raw.count(".") > 1 or raw.count(",") > 1:   # grouping, not a decimal: 1.234.567
        raw = re.sub(r"[.,\s]", "", raw)
    else:
        raw = raw.replace(",", "").replace(" ", "")
    try:
        num = float(raw)
    except ValueError:
        return None
    return int(num * {"K": 1e3, "M": 1e6, "B": 1e9}.get((m.group(2) or "").upper(), 1))


def _parse_clock(txt):
    """'1:02:03' → 3723 seconds (None if absent or not a clock)."""
    if not txt:
        return None
    parts = txt.strip().split(":")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    sec = 0
    for p in parts:
        sec = sec * 60 + int(p)
    return sec


def _parse_age(txt):
    """'1d ago' / '2w ago' / '3mo ago' / '1 year ago' → age in days (None if absent).

    Probed live from search results: YouTube emits the compact units
    d / w / mo / y (note: months is 'mo', not 'm') plus full words.
    """
    if not txt:
        return None
    m = re.match(r"\s*(\d+)\s*([a-zA-Z]+)", txt)
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower().rstrip("s")   # 'months' -> 'month'
    if unit == "mo":
        unit = "month"
    mult = {"second": 1 / 86400, "minute": 1 / 1440, "hour": 1 / 24,
            "day": 1, "week": 7, "month": 30, "year": 365}.get(unit)
    if mult is None and len(unit) == 1:
        # compact form. 'm' alone is never emitted (months are 'mo'), so don't
        # guess at it — minutes are always written out in full.
        mult = {"d": 1, "w": 7, "y": 365}.get(unit)
    return int(n * mult) if mult else None


def _parse_video(v):
    """videoRenderer → the same shape `slim()` expects from a flat yt-dlp entry."""
    vid = v.get("videoId")
    if not vid:
        return None
    owner = v.get("ownerText") or v.get("longBylineText") or v.get("shortBylineText") or {}
    runs = owner.get("runs") or []
    chan_url = None
    if runs:
        browse = (runs[0].get("navigationEndpoint") or {}).get("browseEndpoint") or {}
        if browse.get("browseId"):
            chan_url = f"https://www.youtube.com/channel/{browse['browseId']}"
    # The channel checkmark lives in ownerBadges (badges only carries video-level
    # markers like CC/4K). The style key is `style` on current innertube responses;
    # older/other surfaces used `badgeStyleType`, so accept either.
    def _has_verified(badges):
        for b in badges or []:
            r = b.get("metadataBadgeRenderer") or {}
            style = r.get("style") or r.get("badgeStyleType") or ""
            if "VERIFIED" in style:
                return True
            if (r.get("tooltip") or "").lower() == "verified":
                return True
        return False

    verified = _has_verified(v.get("ownerBadges")) or _has_verified(v.get("badges"))
    length = _runs_text(v.get("lengthText"))
    return {
        "id": vid,
        "title": _runs_text(v.get("title")),
        "url": f"https://www.youtube.com/watch?v={vid}",
        "duration": _parse_clock(length),
        "duration_string": length or None,
        "view_count": _parse_count(_runs_text(v.get("viewCountText"))),
        "channel": runs[0].get("text") if runs else None,
        "channel_url": chan_url,
        "channel_is_verified": verified or None,
        "upload_date": None,
        "live_status": None,
        "age_days": _parse_age(_runs_text(v.get("publishedTimeText"))),
    }


def _innertube_search(query, limit, gl="US", hl="en", params=None):
    """Search YouTube at an explicit locale, paginating via continuation tokens.

    Raises on a hard failure (no config / endpoint down) so callers can fall
    back to yt-dlp; returns [] only when YouTube genuinely has nothing.
    """
    key, base_ctx = _innertube_cfg()
    ctx = json.loads(json.dumps(base_ctx))        # copy — never mutate the cache
    ctx.setdefault("client", {})["gl"] = gl
    ctx["client"]["hl"] = hl

    out, token, seen_tokens, seen_ids = [], None, set(), set()
    while len(out) < limit:
        payload = {"context": ctx}
        if token:
            payload["continuation"] = token
        else:
            payload["query"] = query
            if params:
                payload["params"] = params
        try:
            data = _innertube_post("search", payload)
        except Exception as e:
            if not out:
                raise
            print(f"WARNING: search page failed ({e}); keeping {len(out)} results",
                  file=sys.stderr)
            break
        for v in _find_renderers(data, "videoRenderer"):
            item = _parse_video(v)
            if item and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                out.append(item)
        token = _first_continuation(data)
        if not token or token in seen_tokens:
            break
        seen_tokens.add(token)
    return out[:limit]


def _first_continuation(obj, path=""):
    """Find the feed's continuation token, preferring it over chip-bar/filter tokens.

    The community page can carry several continuationCommand tokens (feed +
    filter-chip bar). The feed's is the one not under a 'chip' path.
    """
    def scan(o, p):
        """Returns (score, token) or None — score 1 = feed, 0 = chip bar."""
        best = None
        if isinstance(o, dict):
            cc = o.get("continuationCommand")
            if isinstance(cc, dict) and isinstance(cc.get("token"), str) and len(cc["token"]) >= 50:
                score = 0 if re.search(r"chip", p, re.I) else 1
                best = (score, cc["token"])
            for k, v in o.items():
                r = scan(v, f"{p}.{k}")
                if r and (best is None or r[0] > best[0]):
                    best = r
        elif isinstance(o, list):
            for i, v in enumerate(o):
                r = scan(v, f"{p}[{i}]")
                if r and (best is None or r[0] > best[0]):
                    best = r
        return best

    best = scan(obj, path)
    return best[1] if best else None


def _find_renderers(obj, key):
    """Yield every dict stored under the given renderer key."""
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], dict):
            yield obj[key]
        for v in obj.values():
            yield from _find_renderers(v, key)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_renderers(v, key)


def _runs_text(node):
    """Flatten a YouTube runs node into a plain string."""
    if not isinstance(node, dict):
        return ""
    runs = node.get("runs") or []
    if runs:
        return "".join(r.get("text", "") for r in runs)
    return node.get("simpleText", "") or ""


def _find_post_renderers(obj):
    """Recursively yield every backstagePostRenderer dict."""
    if isinstance(obj, dict):
        if "backstagePostRenderer" in obj:
            yield obj["backstagePostRenderer"]
        for v in obj.values():
            yield from _find_post_renderers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _find_post_renderers(v)


def _parse_post(p):
    likes = (p.get("voteCount") or {}).get("simpleText")
    img = None
    att = p.get("attachment") or {}
    if "playlistVideoListRenderer" in att:
        img = "(playlist attachment)"
    shared = (att.get("videoThumbnailRenderer") or {})
    if shared:
        thumbs = ((shared.get("thumbnail") or {}).get("thumbnails") or [])
        if thumbs:
            img = thumbs[-1].get("url")
    return {
        "post_id": p.get("postId"),
        "author": _runs_text(p.get("authorText")),
        "text": _runs_text(p.get("contentText")),
        "published": _runs_text(p.get("publishedTimeText")),
        "likes": likes,
        "image_or_attachment": img,
        "url": f"https://www.youtube.com/post/{p.get('postId')}" if p.get("postId") else None,
    }


def _count_community(base):
    """Return (count, has_more) for a channel's community posts.

    Reads page 1, then probes ONE continuation page so '+' only shows when more
    posts genuinely exist (a lone feed token doesn't prove it).
    """
    for suffix in ("/posts", "/community"):
        try:
            html = _http_get(base + suffix)
        except Exception:
            continue
        data = _extract_ytInitialData(html)
        if not data:
            continue
        posts = [_parse_post(p) for p in _find_post_renderers(data)]
        if not posts:
            if suffix == "/posts":
                continue  # try the /community fallback
            return 0, False
        seen = {p["post_id"] for p in posts}
        token = _first_continuation(data)
        if not token:
            return len(posts), False
        key, ctx = _extract_ytcfg(html)
        if not key or not ctx:
            return len(posts), True
        try:
            resp = _innertube_browse(token, key, ctx)
        except Exception:
            return len(posts), True
        new = [p for p in (_parse_post(x) for x in _find_post_renderers(resp))
               if p["post_id"] and p["post_id"] not in seen]
        if not new:
            return len(posts), False
        return len(posts) + len(new), bool(_first_continuation(resp))
    return 0, False


def _paginate_posts(url, limit, max_pages=20):
    """Fetch the first page of posts, then follow continuation tokens — this is
    exactly what infinite-scroll does in the browser: each token is one more batch."""
    try:
        html = _http_get(url)
    except Exception as e:
        return [], str(e)
    data = _extract_ytInitialData(html)
    if not data:
        return [], "no ytInitialData"

    posts = [_parse_post(p) for p in _find_post_renderers(data)]
    seen = {p["post_id"] for p in posts if p["post_id"]}

    if len(posts) < limit:
        api_key, ctx = _extract_ytcfg(html)
        token = _first_continuation(data)
        if api_key and ctx and token:
            for _ in range(max_pages):
                if len(posts) >= limit:
                    break
                try:
                    resp = _innertube_browse(token, api_key, ctx)
                except Exception:
                    break  # token rejected / endpoint changed — keep what we have
                added = 0
                for p in (_parse_post(x) for x in _find_post_renderers(resp)):
                    if p["post_id"] and p["post_id"] not in seen:
                        seen.add(p["post_id"])
                        posts.append(p)
                        added += 1
                token = _first_continuation(resp)
                if not token or added == 0:
                    break
    return posts, None


def cmd_posts(a):
    base = a.posts if a.posts.startswith("http") else f"https://www.youtube.com/{a.posts}"
    base = base.rstrip("/")
    # If the user passed an explicit tab, honour just that one.
    if base.endswith("/posts"):
        candidates = [base]
    elif base.endswith("/community"):
        candidates = [base]
    else:
        # /posts works on every channel tested; /community sometimes shows
        # "This Community isn't available". Try both and merge.
        candidates = [base + "/posts", base + "/community"]

    all_posts, errs = [], []
    for url in candidates:
        # Roughly 10 posts/page, so pages ~= limit/10 (+1 for the first page).
        max_pages = max(1, min(20, a.limit // 10 + 2))
        posts, err = _paginate_posts(url, a.limit, max_pages)
        if err:
            errs.append(f"{url}: {err}")
        if posts:
            all_posts = posts
            break  # first source that yields posts wins (they're the same feed)

    # De-dupe by post_id, preserve order
    seen, uniq = set(), []
    for p in all_posts:
        if p["post_id"] and p["post_id"] not in seen:
            seen.add(p["post_id"])
            uniq.append(p)
    uniq = uniq[: a.limit]

    if a.json:
        print(json.dumps(uniq, ensure_ascii=False, indent=2))
        return
    if not uniq:
        print("No community posts found (channel may have none, or the tab layout changed).")
        for e in errs:
            print(f"  note: {e}", file=sys.stderr)
        return
    for i, p in enumerate(uniq, 1):
        print(f"{i}. [{p['published']}] ({p['likes']} likes) via {p['author']}")
        print(f"   {p['text']}")
        if p["image_or_attachment"]:
            print(f"   attachment: {p['image_or_attachment']}")
        if p["url"]:
            print(f"   {p['url']}")


def dump_entries(args):
    """Run yt-dlp in flat-playlist JSON mode and return a list of entry dicts."""
    proc = run_ytdlp(args + ["--flat-playlist", "--dump-json"])
    entries = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not entries:
        err = (proc.stderr or "").strip().splitlines()
        hint = err[-1] if err else "no results"
        print(f"ERROR: {hint}", file=sys.stderr)
        sys.exit(1)
    return entries


def fmt_views(n):
    if n is None:
        return "?"
    for unit, div in (("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if n >= div:
            return f"{n/div:.1f}{unit}"
    return str(n)


def fmt_duration(s):
    if s is None:
        return "?"
    s = int(s)
    h, r = divmod(s, 3600)
    m, sec = divmod(r, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def slim(e):
    """Normalize an entry dict across search/channel/playlist (flat) shapes."""
    vid = e.get("id")
    url = e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None)
    channel = e.get("channel") or e.get("uploader") or e.get("playlist_channel") or e.get("channel_title")
    return {
        "id": vid,
        "title": e.get("title"),
        "url": url,
        "duration": e.get("duration"),
        "duration_string": e.get("duration_string") or fmt_duration(e.get("duration")),
        "views": e.get("view_count"),
        "channel": channel,
        "channel_url": e.get("channel_url") or e.get("uploader_url"),
        "verified": e.get("channel_is_verified"),
        "upload_date": e.get("upload_date") or e.get("timestamp"),
        "live_status": e.get("live_status"),
        "age_days": e.get("age_days"),
    }


def print_list(items, as_json):
    if as_json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    for i, it in enumerate(items, 1):
        dur = it.get("duration_string", "?")
        views = fmt_views(it.get("views"))
        ch = it.get("channel") or "?"
        verify = " ✓" if it.get("verified") else ""
        print(f"{i:>3}. {it.get('title')}")
        print(f"     {dur} | {views} views | {ch}{verify}")
        if it.get("url"):
            print(f"     {it['url']}")


def cmd_search(a):
    q = a.query.replace(":", " ").strip()
    entries = []
    try:
        entries = _innertube_search(q, a.limit, gl=a.gl, hl=a.hl, params=_YT_SEARCH_PARAMS)
    except Exception as e:
        print(f"WARNING: locale search failed ({e})", file=sys.stderr)
    if not entries:
        # yt-dlp can't pin a locale, but it's better than no results at all
        print(f"WARNING: falling back to yt-dlp — results will follow your IP, "
              f"not gl={a.gl}", file=sys.stderr)
        entries = dump_entries([f"ytsearch{a.limit}:{q}"])
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_channel(a):
    base = a.handle if a.handle.startswith("http") else f"https://www.youtube.com/{a.handle}"
    if "/@" not in base and not base.rstrip("/").endswith(("/videos", "/shorts", "/streams")):
        base = base.rstrip("/") + "/videos"
    if a.tab in ("shorts", "streams") and not base.rstrip("/").endswith("/" + a.tab):
        base = base.rstrip("/").split("/videos")[0] + f"/{a.tab}"
    args = [base, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
    # flat-playlist doesn't include duration; fetch per-video if --with-duration
    if getattr(a, "with_duration", False):
        for e in entries:
            vid = e.get("id")
            if vid:
                detail = run_ytdlp(["--skip-download", "--dump-single-json", f"https://www.youtube.com/watch?v={vid}"])
                if detail.returncode == 0:
                    try:
                        d = json.loads(detail.stdout)
                        e["duration"] = d.get("duration")
                        e["duration_string"] = d.get("duration_string")
                    except json.JSONDecodeError:
                        pass
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_latest(a):
    # /videos tab is reverse-chronological by default, so the head is "latest".
    base = a.handle if a.handle.startswith("http") else f"https://www.youtube.com/{a.handle}"
    if not base.rstrip("/").endswith(("/videos", "/shorts")):
        base = base.rstrip("/") + "/videos"
    args = [base, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
    # flat-playlist doesn't include duration; fetch per-video if --with-duration
    if getattr(a, "with_duration", False):
        for e in entries:
            vid = e.get("id")
            if vid:
                detail = run_ytdlp(["--skip-download", "--dump-single-json", f"https://www.youtube.com/watch?v={vid}"])
                if detail.returncode == 0:
                    try:
                        d = json.loads(detail.stdout)
                        e["duration"] = d.get("duration")
                        e["duration_string"] = d.get("duration_string")
                    except json.JSONDecodeError:
                        pass
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_playlist(a):
    url = a.playlist if a.playlist.startswith("http") else a.playlist
    args = [url, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_sections(a):
    base = a.sections if a.sections.startswith("http") else f"https://www.youtube.com/{a.sections}"
    base = base.rstrip("/")
    # Strip any existing tab suffix so we probe each tab from a clean base.
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    tabs = ["videos", "shorts", "streams", "playlists"]
    result = {"channel": base}
    errors = {}
    for tab in tabs:
        proc = run_ytdlp(["--flat-playlist", "--dump-json", f"{base}/{tab}"])
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        count = len(lines)
        # yt-dlp errors when a tab doesn't exist (e.g. no streams tab).
        # Check for specific "does not have" message which indicates the tab genuinely doesn't exist.
        stderr = proc.stderr or ""
        if count == 0 and "does not have" in stderr:
            result[tab] = None  # tab doesn't exist
        elif proc.returncode != 0:
            # Network failure, HTTP 429, bot detection, timeout, or extractor error
            # Don't silently convert to "no tab" - record the error
            errors[tab] = stderr.strip() or f"yt-dlp exit code {proc.returncode}"
            result[tab] = {"error": errors[tab]}
        else:
            result[tab] = count

    # Shows tab: yt-dlp can't parse gridShowRenderer, so count via raw scrape.
    try:
        shows_html = _http_get(base + "/shows")
        shows_data = _extract_ytInitialData(shows_html)
        n_shows = sum(1 for _ in _find_renderers(shows_data or {}, "gridShowRenderer"))
        # A channel without a Shows tab gets redirected to a page with no shows.
        result["shows"] = n_shows if n_shows else None
    except Exception as e:
        result["shows"] = {"error": str(e)}

    # Community posts: page 1 + one continuation probe for an honest count.
    n_posts, has_more = _count_community(base)
    result["community_posts"] = n_posts
    result["community_posts_more"] = has_more

    if errors:
        result["_errors"] = errors

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    def fmt(v, none="no tab"):
        if isinstance(v, dict) and "error" in v:
            return f"error: {v['error'][:80]}"
        return none if v is None else v

    print(f"Channel: {base}")
    print(f"  videos   : {fmt(result['videos'])}")
    print(f"  shorts   : {fmt(result['shorts'])}")
    print(f"  streams  : {fmt(result['streams'])}")
    print(f"  shows    : {fmt(result['shows'])}")
    print(f"  playlists: {fmt(result['playlists'])}")
    more = "+" if result["community_posts_more"] else ""
    print(f"  community: {result['community_posts']}{more} posts (use `posts` to read them)")
    if errors:
        print("\nErrors encountered (these tabs may exist but couldn't be fetched):")
        for tab, err in errors.items():
            print(f"  {tab}: {err[:100]}")


def cmd_shows(a):
    """List a channel's Shows — episode collections (YouTube treats them as playlists)."""
    base = a.shows if a.shows.startswith("http") else f"https://www.youtube.com/{a.shows}"
    base = base.rstrip("/")
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    try:
        html = _http_get(base + "/shows")
    except Exception as e:
        print(f"ERROR: could not fetch shows tab: {e}", file=sys.stderr)
        sys.exit(1)
    data = _extract_ytInitialData(html)
    if not data:
        print("ERROR: could not parse the shows tab.", file=sys.stderr)
        sys.exit(1)

    items = []
    for s in _find_renderers(data, "gridShowRenderer"):
        ep = (s.get("navigationEndpoint") or {}).get("browseEndpoint", {})
        show_url = None
        wm = (s.get("navigationEndpoint") or {}).get("commandMetadata", {}).get("webCommandMetadata", {})
        if wm.get("url"):
            show_url = "https://www.youtube.com" + wm["url"].split("?")[0]
        playlist_id = ep.get("browseId")
        if playlist_id and playlist_id.startswith("VL"):
            playlist_id = playlist_id[2:]  # VLPLxyz -> PLxyz
        count = None
        for ov in s.get("thumbnailOverlays") or []:
            t = (ov.get("thumbnailOverlayBottomPanelRenderer") or {}).get("text")
            if t:
                count = _runs_text(t)
        items.append({
            "title": (s.get("title") or {}).get("simpleText") or _runs_text(s.get("title")),
            "videos": count,
            "byline": _runs_text(s.get("shortBylineText")),
            "playlist_id": playlist_id,
            "url": show_url or (f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else None),
        })
    items = items[: a.limit]
    if a.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    if not items:
        print("No Shows tab on this channel (only some channels have one).")
        return
    for i, it in enumerate(items, 1):
        print(f"{i:>3}. {it['title']}")
        if it["videos"]:
            print(f"     {it['videos']}")
        if it["url"]:
            print(f"     {it['url']}")


# renderers that represent a single home-shelf item, mapped to their kind.
# (richItemRenderer deliberately excluded: it WRAPS other renderers, which the
# walk finds on their own — counting it too would double-count items.)
_HOME_ITEM_KINDS = {
    "gridVideoRenderer": "video", "videoRenderer": "video", "lockupViewModel": "lockup",
    "gridPlaylistRenderer": "playlist", "playlistRenderer": "playlist",
    "gridChannelRenderer": "channel", "channelRenderer": "channel",
    "reelItemRenderer": "short", "shortsLockupViewModel": "short",
    "backstagePostRenderer": "post", "postRenderer": "post",
}


def _home_item(kind_node):
    """Extract (kind, id, title, url) from a single home-shelf item node."""
    (key, node), = kind_node.items()
    if key == "lockupViewModel":
        cid = node.get("contentId") or ""
        if cid.startswith("UC") and len(cid) == 24:
            kind = "channel"
        elif cid[:2] in ("PL", "UU", "OL", "RD", "FL", "MN", "TL", "PU", "LM") or cid.startswith("OLAK5uy"):
            kind = "playlist"
        else:
            kind = "video"
        title = None
        md = ((node.get("metadata") or {}).get("lockupMetadataViewModel") or {})
        title = md.get("title", {}).get("content") if isinstance(md.get("title"), dict) else None
        title = title or _runs_text(node.get("title"))
        url = {"video": f"https://www.youtube.com/watch?v={cid}",
               "playlist": f"https://www.youtube.com/playlist?list={cid}",
               "channel": f"https://www.youtube.com/channel/{cid}"}[kind]
        return kind, cid, title, url
    if key in ("gridVideoRenderer", "videoRenderer", "reelItemRenderer"):
        vid = node.get("videoId")
        return "video" if key != "reelItemRenderer" else "short", vid, _runs_text(node.get("title")) or _runs_text(node.get("headline")), (f"https://www.youtube.com/watch?v={vid}" if vid else None)
    if key in ("gridPlaylistRenderer", "playlistRenderer"):
        pid = node.get("playlistId")
        return "playlist", pid, _runs_text(node.get("title")), (f"https://www.youtube.com/playlist?list={pid}" if pid else None)
    if key in ("gridChannelRenderer", "channelRenderer"):
        cid = node.get("channelId") or (node.get("navigationEndpoint") or {}).get("browseEndpoint", {}).get("browseId")
        return "channel", cid, _runs_text(node.get("title")), (f"https://www.youtube.com/channel/{cid}" if cid else None)
    if key == "shortsLockupViewModel":
        vid = (((node.get("onTap") or {}).get("innertubeCommand") or {})
               .get("reelWatchEndpoint", {}).get("videoId"))
        if not vid:
            eid = node.get("entityId") or ""
            vid = eid.rsplit("-", 1)[-1] if "-" in eid else None
        return "short", vid, node.get("accessibilityText"), (f"https://www.youtube.com/shorts/{vid}" if vid else None)
    if key in ("backstagePostRenderer", "postRenderer"):
        return "post", node.get("postId"), _runs_text(node.get("contentText")), (f"https://www.youtube.com/post/{node.get('postId')}" if node.get("postId") else None)
    return key.replace("Renderer", "").replace("ViewModel", "").lower(), None, None, None


def cmd_home(a):
    """Parse the channel's Home tab shelves — featured video, shorts, playlists,
    Featured Channels, and any custom sections (what the paid API's 'sections' did)."""
    base = a.home if a.home.startswith("http") else f"https://www.youtube.com/{a.home}"
    base = base.rstrip("/")
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows", "/home"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    try:
        html = _http_get(base)
    except Exception as e:
        print(f"ERROR: could not fetch channel home: {e}", file=sys.stderr)
        sys.exit(1)
    data = _extract_ytInitialData(html)
    if not data:
        print("ERROR: could not parse the home tab.", file=sys.stderr)
        sys.exit(1)

    try:
        tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
        content = tabs[0].get("tabRenderer", {}).get("content", {})
        sections = content.get("sectionListRenderer", {}).get("contents", [])
    except (KeyError, AttributeError):
        sections = []

    out = []
    for sec in sections:
        inner_list = (sec.get("itemSectionRenderer") or {}).get("contents") or []
        for inner in inner_list:
            top_key = next(iter(inner), None)
            node = inner.get(top_key, inner)
            # section title
            title = None
            for cand in (node.get("title") if isinstance(node, dict) else None,):
                if isinstance(cand, dict):
                    title = _runs_text(cand) or None
                elif isinstance(cand, str):
                    title = cand
            if title is None:
                # view-model style titles
                for p, k, v in _walk_pairs(node):
                    if k in ("title", "content") and isinstance(v, str) and 0 < len(v) < 90:
                        title = v
                        break
                    if k == "title" and isinstance(v, dict):
                        t = _runs_text(v)
                        if t:
                            title = t
                            break
            # classify section type + collect items
            if top_key == "channelVideoPlayerRenderer":
                stype = "featured video"
                vid = node.get("videoId")
                vt = node.get("title")
                if isinstance(vt, dict):
                    vt = _runs_text(vt)
                elif not isinstance(vt, str):
                    vt = None
                items = [("video", vid, vt, f"https://www.youtube.com/watch?v={vid}" if vid else None)]
            else:
                # Generic: walk whatever renderers this section holds, so ANY
                # section type (known or future) still yields its items.
                items = [_home_item({k: v}) for k, v in _pairs_of_kind(node)]
                counts = {}
                for it in items:
                    counts[it[0]] = counts.get(it[0], 0) + 1
                dom = max(counts, key=counts.get) if counts else None
                stype = {"video": "videos", "short": "shorts", "playlist": "playlists",
                         "channel": "featured channels", "post": "posts"}.get(dom)
                if stype is None:
                    # no items: fall back to the renderer name (keeps the section visible)
                    stype = {"shelfRenderer": "shelf", "reelShelfRenderer": "shorts"}.get(
                        top_key,
                        (top_key or "section").replace("Renderer", "").replace("ViewModel", "").lower())
            out.append({"type": stype, "title": title, "count": len(items),
                        "items": [{"kind": k, "id": i, "title": t, "url": u}
                                  for k, i, t, u in items]})

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if not out:
        print("No home sections found (tab layout may have changed).")
        return
    print(f"Home — {base}")
    for i, s in enumerate(out, 1):
        label = s["title"] or s["type"]
        print(f"{i:>3}. [{s['type']}] {label}  ({s['count']} item{'s' if s['count'] != 1 else ''})")
        for it in s["items"][: a.limit]:
            if it["kind"] == "channel":
                print(f"       - {it['title']}  {it['url']}")
            elif a.verbose and it["title"]:
                print(f"       - [{it['kind']}] {it['title']}")


def _walk_pairs(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield path + "." + k, k, v
            yield from _walk_pairs(v, path + "." + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_pairs(v, path + f"[{i}]")


def _pairs_of_kind(node):
    """Yield (renderer_key, renderer_node) for every shelf item inside a node."""
    for p, k, v in _walk_pairs(node):
        if k in _HOME_ITEM_KINDS and isinstance(v, dict):
            yield k, v


def cmd_profile(a):
    """Fetch channel profile using fast Innertube API (avoids yt-dlp timeout on large channels)."""
    # Resolve handle to channel URL
    handle = a.profile.strip()
    if handle.startswith("http"):
        base = handle
    elif handle.startswith("@"):
        base = f"https://www.youtube.com/@{handle[1:]}"
    elif handle.startswith("UC") and len(handle) == 24:
        base = f"https://www.youtube.com/channel/{handle}"
    else:
        base = f"https://www.youtube.com/@{handle}"
    
    base = base.rstrip("/")
    # Strip any tab suffix
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows", "/about"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    
    # First, get channel ID from the initial page's metadata
    channel_id = None
    try:
        html = _http_get(base)
        data = _extract_ytInitialData(html)
        if data:
            # The channel ID is in metadata.channelMetadataRenderer.externalId
            meta = data.get("metadata", {}).get("channelMetadataRenderer", {})
            channel_id = meta.get("externalId")
            if channel_id and channel_id.startswith("UC"):
                pass  # Got it
            else:
                # Fallback: search for channelId in the data
                def find_channel_id(obj):
                    if isinstance(obj, dict):
                        if "channelId" in obj and isinstance(obj["channelId"], str) and obj["channelId"].startswith("UC"):
                            return obj["channelId"]
                        for v in obj.values():
                            r = find_channel_id(v)
                            if r:
                                return r
                    elif isinstance(obj, list):
                        for v in obj:
                            r = find_channel_id(v)
                            if r:
                                return r
                    return None
                channel_id = find_channel_id(data)
    except Exception:
        pass
    
    if not channel_id:
        print("ERROR: could not resolve channel ID", file=sys.stderr)
        sys.exit(1)
    
    # Fetch profile via Innertube browse API (fast, no video data)
    try:
        key, ctx = _innertube_cfg()
        payload = json.dumps({"context": ctx, "browseId": channel_id}).encode("utf-8")
        url = f"https://www.youtube.com/youtubei/v1/browse?key={key}"
        req = urllib.request.Request(url, data=payload, headers=dict(_UA, **{"Content-Type": "application/json"}), method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print(f"ERROR: could not fetch channel profile: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse profile data from Innertube response
    meta = resp.get("metadata", {}).get("channelMetadataRenderer", {})
    header_vm = resp.get("header", {}).get("pageHeaderRenderer", {}).get("content", {}).get("pageHeaderViewModel", {})
    
    # Extract subscriber count from header metadata
    subscribers = None
    video_count = None
    for row in header_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", []):
        for part in row.get("metadataParts", []):
            text = part.get("text", {}).get("content", "")
            if "subscriber" in text.lower():
                # Parse "131 subscribers" / "1.2K subscribers" / "466M subscribers" -> int
                subscribers = _parse_count(text)
            elif "video" in text.lower():
                video_count = _parse_count(text)
    
    # Get shorts count if requested (optional, can be slow)
    shorts_count = None
    if getattr(a, "with_shorts", False):
        try:
            shorts_proc = run_ytdlp(["--skip-download", "--flat-playlist", "--dump-json", f"{base}/shorts"])
            if shorts_proc.returncode == 0 and shorts_proc.stdout.strip():
                shorts_count = len([ln for ln in shorts_proc.stdout.splitlines() if ln.strip().startswith("{")])
        except Exception:
            pass
    
    # Fallback to metadata for video count if not in header
    if video_count is None:
        video_count = meta.get("videoCount")
        if video_count:
            try:
                video_count = int(video_count)
            except Exception:
                video_count = None
    
    payload = {
        "name": meta.get("title"),
        "handle": meta.get("vanityChannelUrl", "").replace("http://www.youtube.com/", "").replace("https://www.youtube.com/", "") or channel_id,
        "channel_url": meta.get("channelUrl") or base,
        "subscribers": subscribers,
        "video_count": video_count,
        "shorts_count": shorts_count,
        "total_views": None,  # Not available in fast API
        "description": meta.get("description"),
        "tags": meta.get("keywords", "").split(", ") if meta.get("keywords") else [],
        "country": meta.get("country"),
    }
    
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    
    for k, v in payload.items():
        if v is not None and v != []:
            if isinstance(v, str) and len(v) > 600:
                v = v[:600] + "..."
            print(f"{k:>13}: {v}")


def cmd_info(a):
    url = a.info if a.info.startswith("http") else f"https://www.youtube.com/watch?v={a.info}"
    proc = run_ytdlp(["--skip-download", "--dump-single-json", url])
    if proc.returncode != 0 or not proc.stdout.strip():
        err = (proc.stderr or "").strip().splitlines()
        print(f"ERROR: {err[-1] if err else 'could not fetch info'}", file=sys.stderr)
        sys.exit(1)
    d = json.loads(proc.stdout)
    payload = {
        "id": d.get("id"),
        "title": d.get("title"),
        "channel": d.get("channel") or d.get("uploader"),
        "channel_url": d.get("channel_url") or d.get("uploader_url"),
        "subscribers": d.get("channel_follower_count"),
        "views": d.get("view_count"),
        "likes": d.get("like_count"),
        "upload_date": d.get("upload_date"),
        "duration_seconds": d.get("duration"),
        "duration_string": d.get("duration_string"),
        "live_status": d.get("live_status"),
        "categories": d.get("categories"),
        "tags": d.get("tags"),
        "description": (d.get("description") or "")[:800] or None,
    }
    if a.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    for k, v in payload.items():
        if v is not None:
            print(f"{k:>18}: {v}")


def _scorecard_checks(info, target_kw):
    """Run SEO checks on video metadata. Returns (score, checks_list)."""
    checks = []
    title = (info.get("title") or "").strip()
    desc = (info.get("description") or "").strip()
    tags = info.get("tags") or []
    duration = info.get("duration_seconds")
    upload = info.get("upload_date")
    chapters = info.get("chapters") or []

    kw = (target_kw or "").lower()

    # 1. Title checks
    if not title:
        checks.append(("title_exists", 15, False, "❌ No title"))
    else:
        checks.append(("title_exists", 15, True, f"✅ Title present ({len(title)} chars)"))
        if len(title) > 60:
            checks.append(("title_length", 5, False, f"⚠ Title >60 chars ({len(title)}) — may truncate in search"))
        else:
            checks.append(("title_length", 5, True, f"✅ Title ≤60 chars ({len(title)})"))
        if kw and kw in title.lower():
            checks.append(("title_kw", 15, True, f"✅ Target keyword in title"))
        elif kw:
            checks.append(("title_kw", 15, False, f"❌ Target keyword missing from title"))

    # 2. Description checks
    if not desc:
        checks.append(("desc_exists", 10, False, "❌ No description"))
    else:
        checks.append(("desc_exists", 10, True, f"✅ Description present ({len(desc)} chars)"))
        first_two = "\n".join(desc.split("\n")[:2]).lower()
        if kw and kw in first_two:
            checks.append(("desc_kw_early", 10, True, "✅ Keyword in first 2 lines (above fold)"))
        elif kw:
            checks.append(("desc_kw_early", 10, False, "❌ Keyword not in first 2 lines"))
        if len(desc) < 150:
            checks.append(("desc_length", 5, False, f"⚠ Description very short ({len(desc)} chars)"))
        else:
            checks.append(("desc_length", 5, True, f"✅ Description ≥150 chars"))

    # 3. Tags checks (low weight — YouTube has confirmed tags barely matter for ranking)
    if not tags:
        checks.append(("tags_exist", 3, False, "⚠ No tags (low impact)"))
    else:
        checks.append(("tags_exist", 3, True, f"✅ {len(tags)} tags"))
        if kw and any(kw in t.lower() for t in tags):
            checks.append(("tags_kw", 2, True, "✅ Keyword in tags"))
        elif kw:
            checks.append(("tags_kw", 2, False, "⚠ Keyword not in tags (low impact)"))
        if len(tags) < 5:
            checks.append(("tags_count", 2, False, f"⚠ Only {len(tags)} tags"))
        elif len(tags) > 15:
            checks.append(("tags_count", 2, False, f"⚠ {len(tags)} tags — YouTube ignores after 15"))
        else:
            checks.append(("tags_count", 2, True, f"✅ Tag count in sweet spot (5–15)"))

    # 4. Chapters / timestamps
    if chapters:
        checks.append(("chapters", 5, True, f"✅ {len(chapters)} chapters"))
    elif duration and duration > 600:  # >10 min
        checks.append(("chapters", 5, False, f"⚠ {duration//60} min video — add chapters for retention"))
    else:
        checks.append(("chapters", 5, True, "✅ Short video — chapters optional"))

    # 5. Duration sanity
    if duration:
        if duration < 30:
            checks.append(("duration", 5, False, f"⚠ Very short ({duration}s) — may be a Short"))
        elif duration > 3600:
            checks.append(("duration", 5, False, f"⚠ Very long ({duration//60} min) — consider splitting"))
        else:
            checks.append(("duration", 5, True, f"✅ Duration {duration//60}:{duration%60:02d}"))

    # 6. Upload date freshness (if target kw has year)
    if kw and any(y in kw for y in ("2024", "2025", "2026", "2027", "2028")):
        if upload and upload[:4] in kw:
            checks.append(("freshness", 5, True, f"✅ Upload year matches keyword ({upload[:4]})"))
        elif upload:
            checks.append(("freshness", 5, False, f"⚠ Upload {upload[:4]} vs keyword year"))

    total_w = sum(w for _, w, _, _ in checks)
    earned = sum(w for _, w, ok, _ in checks if ok)
    score = round(100 * earned / total_w) if total_w else 0
    return score, checks


def cmd_scorecard(a):
    vid = _video_id(a.video)
    if not vid:
        print("ERROR: cannot parse video URL or ID", file=sys.stderr)
        sys.exit(1)
    url = f"https://www.youtube.com/watch?v={vid}"

    proc = run_ytdlp(["--skip-download", "--dump-single-json", url])
    if proc.returncode != 0 or not proc.stdout.strip():
        err = (proc.stderr or "").strip().splitlines()
        print(f"ERROR: {err[-1] if err else 'could not fetch info'}", file=sys.stderr)
        sys.exit(1)
    info = json.loads(proc.stdout)

    score, checks = _scorecard_checks(info, a.keyword)

    if a.json:
        print(json.dumps({
            "video_id": vid,
            "target_keyword": a.keyword,
            "score": score,
            "checks": [{"name": n, "weight": w, "pass": ok, "detail": d}
                       for n, w, ok, d in checks]
        }, ensure_ascii=False, indent=2))
        return

    print(f"SEO Scorecard for {vid}" + (f"  (target: {a.keyword})" if a.keyword else "") + f"\n")
    print(f"Overall: {score}/100\n")
    for name, weight, ok, detail in checks:
        mark = "✅" if ok else "❌"
        print(f"  {mark}  [{weight:>2}]  {detail}")


def cmd_outliers(a):
    """Find videos where views/subscriber ratio exceeds threshold."""
    # Resolve handle to channel URL and get subscriber count via fast Innertube API
    from urllib.parse import urlparse
    handle = a.handle.strip()
    if handle.startswith("http"):
        base = handle
    elif handle.startswith("@"):
        base = f"https://www.youtube.com/@{handle[1:]}"
    elif handle.startswith("UC") and len(handle) == 24:
        base = f"https://www.youtube.com/channel/{handle}"
    else:
        base = f"https://www.youtube.com/@{handle}"
    
    base = base.rstrip("/")
    # Strip any tab suffix
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows", "/about"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    
    # First, get channel ID from the initial page's metadata
    channel_id = None
    try:
        html = _http_get(base)
        data = _extract_ytInitialData(html)
        if data:
            # The channel ID is in metadata.channelMetadataRenderer.externalId
            meta = data.get("metadata", {}).get("channelMetadataRenderer", {})
            channel_id = meta.get("externalId")
            if channel_id and channel_id.startswith("UC"):
                pass  # Got it
            else:
                # Fallback: search for channelId in the data
                def find_channel_id(obj):
                    if isinstance(obj, dict):
                        if "channelId" in obj and isinstance(obj["channelId"], str) and obj["channelId"].startswith("UC"):
                            return obj["channelId"]
                        for v in obj.values():
                            r = find_channel_id(v)
                            if r:
                                return r
                    elif isinstance(obj, list):
                        for v in obj:
                            r = find_channel_id(v)
                            if r:
                                return r
                    return None
                channel_id = find_channel_id(data)
    except Exception:
        pass
    
    if not channel_id:
        print("ERROR: could not resolve channel ID", file=sys.stderr)
        sys.exit(1)
    
    # Fetch subscriber count via fast Innertube browse API
    try:
        key, ctx = _innertube_cfg()
        payload = json.dumps({"context": ctx, "browseId": channel_id}).encode("utf-8")
        url = f"https://www.youtube.com/youtubei/v1/browse?key={key}"
        req = urllib.request.Request(url, data=payload, headers=dict(_UA, **{"Content-Type": "application/json"}), method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print(f"ERROR: could not fetch channel profile: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract subscriber count from header metadata
    subs = None
    header_vm = resp.get("header", {}).get("pageHeaderRenderer", {}).get("content", {}).get("pageHeaderViewModel", {})
    for row in header_vm.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", []):
        for part in row.get("metadataParts", []):
            text = part.get("text", {}).get("content", "")
            if "subscriber" in text.lower():
                subs = _parse_count(text)
                break
        if subs:
            break
    
    if not subs:
        print("ERROR: could not determine subscriber count", file=sys.stderr)
        sys.exit(1)

    # Verify subs by also checking a video from this channel (cross-check)
    # Some channels report different counts on profile vs video pages
    if a.verify_subs:
        probe = run_ytdlp(["--skip-download", "--flat-playlist", "--dump-json",
                           f"{base}/videos", "--playlist-end", "1"])
        for line in probe.stdout.strip().splitlines():
            try:
                pv = json.loads(line)
                vproc = run_ytdlp(["--skip-download", "--dump-single-json",
                                   f"https://www.youtube.com/watch?v={pv.get('id')}"])
                if vproc.returncode == 0:
                    vd = json.loads(vproc.stdout)
                    vsubs = vd.get("channel_follower_count")
                    if vsubs and vsubs != subs:
                        print(f"NOTE: profile subs={subs:,} vs video subs={vsubs:,} — using video count",
                              file=sys.stderr)
                        subs = vsubs
                        break
            except Exception:
                pass

    # Fetch videos from the requested tab(s) - flat-playlist already includes view_count!
    tabs_to_scan = ["videos", "shorts"] if a.tab == "all" else [a.tab]
    
    all_videos = []
    for tab in tabs_to_scan:
        tab_suffix = f"/{tab}" if tab in ("videos", "shorts") else ""
        tab_url = base + tab_suffix
        proc = run_ytdlp(["--skip-download", "--flat-playlist", "--dump-json", tab_url,
                          "--playlist-end", str(a.limit)])
        if proc.returncode != 0 or not proc.stdout.strip():
            print(f"WARNING: no videos found in {tab} tab", file=sys.stderr)
            continue
        
        for line in proc.stdout.strip().splitlines():
            try:
                v = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = v.get("id")
            if not vid:
                continue
            v["_source_tab"] = tab  # Track which tab this came from
            all_videos.append(v)

    if not all_videos:
        print("ERROR: no videos found in any tab", file=sys.stderr)
        sys.exit(1)

    outliers = []
    for v in all_videos:
        vid = v.get("id")
        if not vid:
            continue
        # Use view_count directly from flat-playlist (no extra per-video call needed!)
        views = v.get("view_count") or 0
        if views == 0:
            continue
        ratio = views / subs
        if ratio >= a.min_ratio:
            outliers.append({
                "video_id": vid,
                "title": v.get("title"),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "views": views,
                "ratio": round(ratio, 2),
                "duration": v.get("duration"),
                "upload_date": v.get("upload_date") or v.get("timestamp"),
                "source_tab": v.get("_source_tab", "videos"),
            })

    outliers.sort(key=lambda x: -x["ratio"])

    if a.json:
        print(json.dumps({"channel": base, "subscribers": subs,
                          "min_ratio": a.min_ratio, "outliers": outliers},
                         ensure_ascii=False, indent=2))
        return

    if not outliers:
        print(f"No outliers found for {base} (min ratio {a.min_ratio}x, {subs:,} subs)")
        return

    print(f"Outliers for {base}  ({subs:,} subs, min ratio {a.min_ratio}x)\n")
    for o in outliers:
        dur = fmt_duration(o["duration"])
        print(f"  {o['ratio']:.1f}x  {fmt_views(o['views']):>8}  {dur:>8}  {o['title']}")
        print(f"        {o['url']}")


def cmd_gap(a):
    """Content gap: compare my seed keyword ideas vs competitor's profile keywords."""
    # Get my keywords
    class Args:
        pass
    my_args = Args()
    my_args.seed = a.seed
    my_args.letters = ""
    my_args.patterns = True
    my_args.limit = a.limit * 2
    my_args.gl = a.gl
    my_args.hl = a.hl
    my_args.sources = "yt,ddg"
    my_args.json = True

    # Capture keywords output
    import io, sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        cmd_keywords(my_args)
        my_output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout
    my_data = json.loads(my_output)
    my_kws = {k["keyword"].lower(): k for k in my_data["keywords"]}

    # Get competitor profile via fast Innertube API
    comp = a.competitor.strip()
    if comp.startswith("http"):
        base = comp
    elif comp.startswith("@"):
        base = f"https://www.youtube.com/@{comp[1:]}"
    elif comp.startswith("UC") and len(comp) == 24:
        base = f"https://www.youtube.com/channel/{comp}"
    else:
        base = f"https://www.youtube.com/@{comp}"
    
    base = base.rstrip("/")
    for suf in ("/videos", "/shorts", "/streams", "/playlists", "/community", "/posts", "/shows", "/about"):
        if base.endswith(suf):
            base = base[: -len(suf)]
    
    channel_id = None
    if "/channel/" in base:
        channel_id = base.split("/channel/")[-1].split("/")[0]
    
    if not channel_id:
        try:
            html = _http_get(base)
            data = _extract_ytInitialData(html)
            if data:
                def find_channel_id(obj):
                    if isinstance(obj, dict):
                        if "channelId" in obj and isinstance(obj["channelId"], str) and obj["channelId"].startswith("UC"):
                            return obj["channelId"]
                        for v in obj.values():
                            r = find_channel_id(v)
                            if r:
                                return r
                    elif isinstance(obj, list):
                        for v in obj:
                            r = find_channel_id(v)
                            if r:
                                return r
                    return None
                channel_id = find_channel_id(data)
        except Exception:
            pass
    
    if not channel_id:
        print("ERROR: could not resolve competitor channel ID", file=sys.stderr)
        sys.exit(1)
    
    # Fetch profile via fast Innertube browse API
    try:
        key, ctx = _innertube_cfg()
        payload = json.dumps({"context": ctx, "browseId": channel_id}).encode("utf-8")
        url = f"https://www.youtube.com/youtubei/v1/browse?key={key}"
        req = urllib.request.Request(url, data=payload, headers=dict(_UA, **{"Content-Type": "application/json"}), method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print(f"ERROR: could not fetch competitor profile: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Extract tags from metadata
    meta = resp.get("metadata", {}).get("channelMetadataRenderer", {})
    comp_tags = [t.lower() for t in meta.get("keywords", "").split(", ")] if meta.get("keywords") else []

    if a.json:
        print(json.dumps({
            "seed": a.seed,
            "competitor": base,
            "my_keywords": list(my_kws.values())[:a.limit],
            "competitor_keywords": comp_tags,
            "only_me": [k for kw, k in my_kws.items() if kw not in comp_tags][:a.limit],
            "only_them": [kw for kw in comp_tags if kw not in my_kws][:a.limit],
            "both": [k for kw, k in my_kws.items() if kw in comp_tags][:a.limit],
        }, ensure_ascii=False, indent=2))
        return

    only_me = [k for kw, k in my_kws.items() if kw not in comp_tags][:a.limit]
    only_them = [kw for kw in comp_tags if kw not in my_kws][:a.limit]
    both = [k for kw, k in my_kws.items() if kw in comp_tags][:a.limit]

    print(f'Content Gap: "{a.seed}" vs {base}\n')
    print(f"My unique keywords ({len(only_me)}):")
    for k in only_me:
        flags = ("  Y" if k["year_trend"] else "") + ("  Q" if k["question"] else "")
        print(f"  {k['score']:>3}  {k['keyword']}{flags}")
    print(f"\nCompetitor unique keywords ({len(only_them)}):")
    for kw in only_them:
        print(f"  {kw}")
    print(f"\nShared keywords ({len(both)}):")
    for k in both:
        flags = ("  Y" if k["year_trend"] else "") + ("  Q" if k["question"] else "")
        print(f"  {k['score']:>3}  {k['keyword']}{flags}")


# ---- Keyword research via YouTube suggest (free, no API key) ----
# The suggest box runs on real query popularity — the same signal free SEO
# tools approximate volume with. We expand a seed through the alphabet and
# score how often/where each suggestion comes back.

_SUGGEST_URL = "https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q="


def _suggest(q, gl="US", hl="en", timeout=8, lang_filter=None):
    """One YouTube suggest lookup. Returns a list of suggestion strings (empty on any failure).

    lang_filter: if set, only return suggestions matching this script.
      None = auto from hl (e.g. hl=hi allows Devanagari, hl=ja allows Japanese, else Latin-only)
    """
    url = f"{_SUGGEST_URL}{urllib.parse.quote(q)}&gl={gl}&hl={hl}"
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    m = re.search(r"\((\[.*\])\)", text, re.S)
    if not m:
        return []
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    out = []
    for item in payload[1]:
        if isinstance(item, list) and item and isinstance(item[0], str):
            s = item[0]
            if _passes_lang_filter(s, lang_filter or hl):
                out.append(s)
    return out


def _passes_lang_filter(text, hl):
    """Return True if text matches the expected script for the locale."""
    # Map hl to allowed Unicode scripts
    script_map = {
        "hi": "Devanagari", "bn": "Bengali", "ta": "Tamil", "te": "Telugu",
        "kn": "Kannada", "ml": "Malayalam", "gu": "Gujarati", "pa": "Gurmukhi",
        "or": "Oriya", "as": "Assamese", "mr": "Devanagari",
        "ja": ["Hiragana", "Katakana", "Katakana-Hiragana", "Han"],
        "ko": "Hangul", "zh": "Han", "zh-cn": "Han", "zh-tw": "Han",
        "ar": "Arabic", "fa": "Arabic", "ur": "Arabic",
        "ru": "Cyrillic", "uk": "Cyrillic", "bg": "Cyrillic", "sr": "Cyrillic",
        "th": "Thai", "vi": "Latin",  # Vietnamese uses Latin with diacritics
    }
    allowed = script_map.get(hl.lower())
    if allowed is None:
        allowed = "Latin"  # default: Latin only
    if isinstance(allowed, str):
        allowed = [allowed]
    # Normalize allowed scripts to uppercase for comparison
    allowed = [s.upper() for s in allowed]

    import unicodedata
    for ch in text:
        if ch.isalpha():
            script = unicodedata.name(ch, "").split()[0] if unicodedata.name(ch, "") else "Unknown"
            if script not in allowed:  # Latin is already in allowed for en
                return False
    return True


# DuckDuckGo autocomplete — the second opinion. YouTube's suggest tells you what
# people type ON YouTube; DDG tells you what the wider web asks about. Agreement
# across both is a stronger demand signal than either alone, and DDG doubles as
# the safety net when Google's endpoint throttles.

# DDG's kl codes don't map 1:1 from gl/hl (GB is 'uk', not 'gb'; India ships
# 'in-en' and has no 'in-hi'). Unknown codes fail silently DDG-side, so a miss
# here only costs the locale hint — never the request itself.
_DDG_KL = {
    ("US", "en"): "us-en", ("GB", "en"): "uk-en", ("CA", "en"): "ca-en",
    ("AU", "en"): "au-en", ("NZ", "en"): "nz-en", ("IE", "en"): "ie-en",
    ("IN", "en"): "in-en", ("IN", "hi"): "in-en", ("ZA", "en"): "za-en",
    ("DE", "de"): "de-de", ("AT", "de"): "at-de", ("CH", "de"): "ch-de",
    ("FR", "fr"): "fr-fr", ("ES", "es"): "es-es", ("MX", "es"): "mx-es",
    ("IT", "it"): "it-it", ("NL", "nl"): "nl-nl", ("PT", "pt"): "pt-pt",
    ("BR", "pt"): "br-pt", ("JP", "ja"): "jp-jp", ("KR", "ko"): "kr-kr",
    ("RU", "ru"): "ru-ru", ("PL", "pl"): "pl-pl", ("TR", "tr"): "tr-tr",
    ("SE", "sv"): "sv-se", ("NO", "no"): "no-no", ("DK", "da"): "dk-dk",
    ("FI", "fi"): "fi-fi", ("CZ", "cs"): "cz-cz", ("ID", "id"): "id-id",
    ("TH", "th"): "th-th", ("SA", "ar"): "sa-ar", ("AE", "ar"): "ae-ar",
    ("IL", "he"): "il-he",
}

# Trend log — keyword score snapshots across runs (zero deps, pure JSON)
_TREND_LOG = os.path.expanduser("~/.ytdata-trendlog.json")


def _ddg_kl(gl, hl):
    """Map --gl/--hl to a DuckDuckGo kl code, or None to take DDG's own default."""
    gl, hl = (gl or "").upper(), (hl or "").lower()
    return _DDG_KL.get((gl, hl)) or _DDG_KL.get((gl, "en"))


def _suggest_ddg(q, kl=None, timeout=8, lang_filter=None):
    """One DuckDuckGo autocomplete lookup (list form). Empty list on any failure.

    lang_filter: same as _suggest — filter by script.
    """
    url = f"https://duckduckgo.com/ac/?q={urllib.parse.quote(q)}&type=list"
    if kl:
        url += f"&kl={kl}"
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return []
    if isinstance(data, list) and len(data) > 1 and isinstance(data[1], list):
        return [s for s in data[1] if isinstance(s, str) and _passes_lang_filter(s, lang_filter)]
    if isinstance(data, list):   # bare form: [{"phrase": "..."}, ...]
        return [d.get("phrase") for d in data if isinstance(d, dict) and d.get("phrase") and _passes_lang_filter(d.get("phrase", ""), lang_filter)]
    return []


def cmd_keywords(a):
    seed = a.seed.strip()
    year = time.strftime("%Y")
    queries = [seed]
    if a.letters:
        queries += [f"{seed} {c}" for c in a.letters]
    if a.patterns:
        queries += [f"how to {seed}", f"why {seed}", f"best {seed}",
                    f"{seed} for beginners", f"{seed} vs", f"{seed} {year}"]

    use = {s.strip().lower() for s in a.sources.split(",") if s.strip()}
    unknown = use - {"yt", "ddg"}
    if not use or unknown:
        print(f"ERROR: --sources takes a comma list from yt,ddg (got {a.sources!r})",
              file=sys.stderr)
        sys.exit(1)
    kl = _ddg_kl(a.gl, a.hl)

    stats = {}

    def note(s, pos, src):
        """One suggestion from one engine — deduped across queries and engines."""
        key = s.lower().strip()
        if not key:
            return
        rec = stats.get(key)
        if rec is None:
            rec = stats[key] = {"keyword": s, "yt": 0, "ddg": 0, "best_pos": pos}
        rec[src] += 1
        rec["best_pos"] = min(rec["best_pos"], pos)

    for i, q in enumerate(queries):
        if "yt" in use:
            for pos, s in enumerate(_suggest(q, gl=a.gl, hl=a.hl, lang_filter=a.hl)):
                note(s, pos, "yt")
        if "ddg" in use:
            for pos, s in enumerate(_suggest_ddg(q, kl=kl, lang_filter=a.hl)):
                note(s, pos, "ddg")
        if i < len(queries) - 1:
            time.sleep(0.2)  # be polite; both endpoints throttle hard otherwise

    stats.pop(seed.lower(), None)  # the seed trivially suggests itself
    if not stats:
        print("ERROR: suggest returned nothing (rate-limited?) — retry in a bit or fewer queries",
              file=sys.stderr)
        sys.exit(1)

    question_words = ("how", "why", "what", "when", "where", "is", "are", "can", "do", "does", "should")
    rows = []
    for rec in stats.values():
        kw = rec["keyword"]
        # YouTube's own suggest is the platform signal (x10); DDG corroborates
        # web-wide demand (x5). Both counts cap at 5: past that an engine is
        # just repeating itself (DDG returns near-identical lists across the
        # whole a-z sweep), which is list stability, not extra demand.
        score = (min(rec["yt"], 5) * 10 + min(rec["ddg"], 5) * 5
                 + max(0, 25 - rec["best_pos"]))
        rec["year_trend"] = year in kw
        rec["question"] = kw.lower().split()[0] in question_words
        if rec["year_trend"]:
            score += 12
        if rec["question"]:
            score += 5
        rec["score"] = score
        rows.append(rec)
    rows.sort(key=lambda r: (-r["score"], r["keyword"]))
    rows = rows[: a.limit]

    # Append snapshot to trend log (pure JSON, zero deps)
    _append_trend_log(seed, a.gl, a.hl, rows)

    if a.json:
        print(json.dumps({"seed": seed, "gl": a.gl, "hl": a.hl, "sources": sorted(use),
                          "kl": kl, "queries": len(queries), "unique": len(stats),
                          "keywords": rows}, ensure_ascii=False, indent=2))
        return
    print(f'Keyword ideas for "{seed}" — {len(stats)} unique from {len(queries)} queries '
          f'(gl={a.gl} hl={a.hl}, sources: {",".join(sorted(use))})')
    print(f"(score = YouTube suggest x10 + DDG x5 (capped at 5 each) + how high it "
          f"comes back; Y = mentions {year} (trending now), Q = question form)\n")
    print(f"{'score':>5}  {'yt':>3}  {'ddg':>3}  {'pos':>3}  keyword")
    for r in rows:
        flags = ("  Y" if r["year_trend"] else "") + ("  Q" if r["question"] else "")
        print(f"{r['score']:>5}  {r['yt']:>3}  {r['ddg']:>3}  #{r['best_pos']:<3} "
              f"{r['keyword']}{flags}")


def _append_trend_log(seed, gl, hl, rows):
    """Append a keyword score snapshot to the trend log."""
    entry = {
        "seed": seed,
        "gl": gl,
        "hl": hl,
        "ts": time.strftime("%Y-%m-%d %H:%M"),
        "keywords": [{"k": r["keyword"], "s": r["score"],
                      "yt": r["yt"], "ddg": r["ddg"], "pos": r["best_pos"],
                      "Y": r["year_trend"], "Q": r["question"]}
                     for r in rows]
    }
    try:
        with open(_TREND_LOG, encoding="utf-8") as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log = []
    log.append(entry)
    # keep last 500 entries per seed/gl/hl to bound file size
    key = (seed, gl, hl)
    log = [e for e in log if (e["seed"], e["gl"], e["hl"]) != key][-499:] + [entry]
    with open(_TREND_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def cmd_trends(a):
    """Show historical trend for a seed keyword from the trend log."""
    try:
        with open(_TREND_LOG, encoding="utf-8") as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("ERROR: no trend data yet — run `keywords` a few times first", file=sys.stderr)
        sys.exit(1)

    entries = [e for e in log
               if e["seed"].lower() == a.seed.lower()
               and e["gl"].upper() == a.gl.upper()
               and e["hl"].lower() == a.hl.lower()]
    if not entries:
        print(f"ERROR: no trend data for seed={a.seed!r} gl={a.gl} hl={a.hl}", file=sys.stderr)
        sys.exit(1)

    # filter by days
    if a.days:
        cutoff = time.time() - a.days * 86400
        entries = [e for e in entries
                   if time.mktime(time.strptime(e["ts"], "%Y-%m-%d %H:%M")) >= cutoff]

    if not entries:
        print("No entries in the selected window.")
        return

    # collect all keywords ever seen for this seed
    all_kw = {}
    for e in entries:
        for kw in e["keywords"]:
            all_kw.setdefault(kw["k"], []).append((e["ts"], kw["s"], kw["yt"], kw["ddg"], kw["pos"], kw["Y"], kw["Q"]))

    if a.json:
        print(json.dumps({"seed": a.seed, "gl": a.gl, "hl": a.hl,
                          "window_days": a.days, "keywords": all_kw},
                         ensure_ascii=False, indent=2))
        return

    print(f'Trend for "{a.seed}"  (gl={a.gl} hl={a.hl}'
          f'{", last " + str(a.days) + " days" if a.days else ""}) — {len(entries)} snapshots\n')

    # show top 20 by latest score
    latest = entries[-1]
    latest_scores = {kw["k"]: kw["s"] for kw in latest["keywords"]}
    top_kw = sorted(latest_scores.items(), key=lambda x: -x[1])[: a.limit]

    for kw, score in top_kw:
        hist = all_kw[kw]
        scores = [h[1] for h in hist]
        delta = scores[-1] - scores[0] if len(scores) > 1 else 0
        vel = scores[-1] - scores[-2] if len(scores) > 1 else 0
        trend = "↑" if vel > 5 else ("↓" if vel < -5 else "→")
        spark = "".join("█" * min(8, max(1, s // 10)) for s in scores[-8:])
        first_ts, last_ts = hist[0][0], hist[-1][0]
        print(f"  {score:>3}  {trend}  {spark}  {kw}")
        if a.verbose:
            print(f"       {len(hist)} pts  {first_ts} -> {last_ts}  Delta={delta:+d}  vel={vel:+d}")

    if a.verbose:
        print(f"\nAll {len(all_kw)} keywords tracked. Use --limit to see more.")


# ---- Rank tracking: where a video sits for a keyword (no API key) ----

def _video_id(url_or_id):
    # Handle youtu.be/VIDEO_ID
    m = re.search(r"youtu\.be/([\w-]{11})", url_or_id)
    if m:
        return m.group(1)
    # Handle standard watch URLs, shorts, embed, live
    m = re.search(r"(?:[?&]v=|/shorts/|/embed/|/live/)([\w-]{11})", url_or_id)
    if m:
        return m.group(1)
    # Raw 11-character video ID
    if re.fullmatch(r"[\w-]{11}", url_or_id):
        return url_or_id
    return None


def _median(xs):
    s = sorted(xs)
    m = len(s)
    if not m:
        return None
    return s[m // 2] if m % 2 else (s[m // 2 - 1] + s[m // 2]) / 2


def _difficulty_band(score):
    if score <= 25:
        return "EASY"
    if score <= 50:
        return "MEDIUM"
    if score <= 75:
        return "HARD"
    return "SATURATED"


def _serp_stats(entries, query, top=10):
    """Competition metrics for `query` from the top `top` results (already fetched).

    Five signals, each 0-100 where higher = harder to rank:
      views        median views of the incumbents (log scale — raw views across
                   niches are not comparable)
      authority    share of verified channels
      titles       how tightly their titles already match the query (token-level)
      entrenchment how old the incumbents are (old results are hard to displace)
      velocity     median views/day (log scale)

    Signals with no data are dropped and the remaining weights renormalised
    rather than silently counted as zero — the yt-dlp fallback carries no age.
    Returns None when there is nothing to score.
    """
    rows = [e for e in entries[:top] if isinstance(e, dict) and e.get("id")]
    if not rows:
        return None
    n = len(rows)

    views = [e["view_count"] for e in rows
             if isinstance(e.get("view_count"), (int, float)) and e["view_count"] > 0]
    ages = [e["age_days"] for e in rows
            if isinstance(e.get("age_days"), (int, float))]
    # velocity: views per day for each result (where both exist)
    velocities = [e["view_count"] / max(1, e["age_days"])
                  for e in rows
                  if isinstance(e.get("view_count"), (int, float))
                  and e["view_count"] > 0
                  and isinstance(e.get("age_days"), (int, float))
                  and e["age_days"] > 0]
    verified = sum(1 for e in rows if e.get("channel_is_verified"))

    # how much of the query's content already appears in the titles
    stops = {"how", "the", "for", "and", "with", "your", "you", "that", "this",
             "what", "when", "why", "from", "into", "about", "will", "can"}
    toks = [t for t in re.findall(r"[a-z0-9]+", (query or "").lower())
            if len(t) >= 3 and t not in stops]
    
    def _tokenize(text):
        """Tokenize text into words, removing stop words and short tokens."""
        return [t for t in re.findall(r"[a-z0-9]+", text.lower())
                if len(t) >= 3 and t not in stops]
    
    cover = []
    if toks:
        for e in rows:
            title = (e.get("title") or "").lower()
            title_tokens = _tokenize(title)
            cover.append(sum(1 for t in toks if t in title_tokens) / len(toks))

    # brand-query heuristic: single token that MATCHES a channel name in the
    # top results (case-insensitive). Pure informational single words like
    # "python" don't match; "mrbeast" does. This is data-driven, not guesswork.
    is_brand = False
    if len(toks) == 1 and toks[0].isalnum() and " " not in query:
        q_lower = query.lower()
        for e in rows:
            chan = (e.get("channel") or "").lower()
            if chan and q_lower == chan.replace("@", "").replace(" ", ""):
                is_brand = True
                break

    sig = {}  # name -> (weight, value, detail)
    if views:
        med = _median(views)
        # 1k views -> 0, 10M -> 100
        v = max(0.0, min(100.0, (math.log10(med) - 3) / 4 * 100))
        sig["views"] = (35, v, f"median {fmt_views(int(med))} views")
    sig["authority"] = (25, 100.0 * verified / n, f"{verified} of {n} verified")
    if cover:
        c = 100.0 * _median(cover)
        if is_brand:
            detail = "brand query — title match not meaningful"
        elif c >= 60:
            detail = "titles already target this query"
        else:
            detail = "titles barely mention the query"
        sig["titles"] = (20, c, detail)
    if ages:
        med_age = _median(ages)
        # sqrt curve: ~1 month -> 13, 1 year -> 45, 5 years -> 100
        v = min(100.0, math.sqrt(max(med_age, 0) / 1825) * 100)
        sig["entrenchment"] = (15, v, f"median age {_fmt_age(int(med_age))}")
    if velocities:
        med_vel = _median(velocities)
        # log scale: 10 vpd -> ~0, 100K vpd -> 100
        v = max(0.0, min(100.0, (math.log10(max(med_vel, 1)) - 1) / 5 * 100))
        sig["velocity"] = (5, v, f"median {fmt_views(int(med_vel))} views/day")

    if not sig:
        return None
    wsum = sum(w for w, _, _ in sig.values())
    score = sum(w * v for w, v, _ in sig.values()) / wsum

    floor_views = min(views) if views else None
    beatable = sum(1 for x in views if x < 10000)
    return {
        "score": round(score, 1),
        "band": _difficulty_band(score),
        "scored": n,
        "median_views": int(_median(views)) if views else None,
        "verified": verified,
        "median_age_days": int(_median(ages)) if ages else None,
        "floor_views": floor_views,
        "under_10k": beatable,
        "is_brand": is_brand,
        "signals": [{"name": k, "weight": w, "value": round(v, 1), "detail": d}
                    for k, (w, v, d) in sig.items()],
    }


def _fmt_age(days):
    if days is None:
        return "?"
    if days < 45:
        return f"{days}d"
    if days < 730:
        return f"{days // 30}mo"
    return f"{days // 365}y"


def _compete_advice(s):
    """Actionable lines derived from the score — what to actually do about it."""
    out = []
    if s["floor_views"] is not None:
        out.append(f"bar to clear: #{s['scored']} in the top sits at "
                   f"{fmt_views(s['floor_views'])} views")
    if s["under_10k"]:
        out.append(f"{s['under_10k']} of the top {s['scored']} have under 10K views "
                   f"— real slots you can take")
    by = {x["name"]: x for x in s["signals"]}
    # don't give "exact-match title" advice for brand queries — it's the channel,
    # not the title, that owns the query
    if "titles" in by and by["titles"]["value"] < 50 and not s.get("is_brand"):
        out.append("incumbent titles ignore the query — an exact-match title "
                   "is an easy edge here")
    if "entrenchment" in by:
        if s["median_age_days"] is not None and s["median_age_days"] < 45:
            out.append("results are weeks old — the SERP is churning, "
                       "good window to enter")
        elif by["entrenchment"]["value"] >= 70:
            out.append("incumbents are years old and entrenched — "
                       "you need a clearly better title, not a same-but-newer one")
    if "authority" in by and by["authority"]["value"] >= 70:
        out.append("the top is dominated by verified channels — "
                   "authority matters more than usual for this query")
    if "velocity" in by:
        if by["velocity"]["value"] >= 70:
            out.append("this keyword moves FAST — top videos pull huge daily views, "
                       "publish quickly and promote hard in first 48h")
        elif by["velocity"]["value"] <= 20:
            out.append("slow burn keyword — daily views are low, but results stick "
                       "around; evergreen content works here")
    if not out:
        out.append("balanced field — a tighter title and a stronger click-through "
                   "rate are the way in")
    return out


def cmd_compete(a):
    q = a.query.replace(":", " ").strip()
    entries = []
    try:
        entries = _innertube_search(q, a.top, gl=a.gl, hl=a.hl, params=_YT_SEARCH_PARAMS)
    except Exception as e:
        print(f"WARNING: locale search failed ({e})", file=sys.stderr)
    if not entries:
        print(f"WARNING: falling back to yt-dlp — results will follow your IP, "
              f"not gl={a.gl}", file=sys.stderr)
        entries = dump_entries([f"ytsearch{a.top}:{q}"])

    stats = _serp_stats(entries, q, top=a.top)
    if not stats:
        print("ERROR: no results to score", file=sys.stderr)
        sys.exit(1)

    if a.json:
        print(json.dumps({"keyword": q, "gl": a.gl, "hl": a.hl, **stats,
                          "advice": _compete_advice(stats)},
                         ensure_ascii=False, indent=2))
        return

    print(f'Competition for "{q}" — top {stats["scored"]}  (gl={a.gl} hl={a.hl})\n')
    print(f'difficulty: {stats["score"]}/100  {stats["band"]}\n')
    wmax = max(x["weight"] for x in stats["signals"])
    for x in stats["signals"]:
        bar = "#" * int(round(x["value"] / 5)) + "." * (20 - int(round(x["value"] / 5)))
        print(f'  {x["name"]:<13} {x["weight"]:>2}%  {x["value"]:>5.1f}  {bar}  {x["detail"]}')
    print("\nwhat to do:")
    for line in _compete_advice(stats):
        print(f"  - {line}")


def cmd_track(a):
    q = a.query.replace(":", " ").strip()
    entries = []
    try:
        entries = _innertube_search(q, a.top, gl=a.gl, hl=a.hl, params=_YT_SEARCH_PARAMS)
    except Exception as e:
        print(f"WARNING: locale search failed ({e})", file=sys.stderr)
    if not entries:
        print(f"WARNING: falling back to yt-dlp — results will follow your IP, "
              f"not gl={a.gl}", file=sys.stderr)
        entries = dump_entries([f"ytsearch{a.top}:{q}"])
    if not a.video:
        # no target video: just show what currently ranks (SERP view)
        stats = _serp_stats(entries, q, top=a.top)
        if not a.json:
            print(f'Top {min(len(entries), a.top)} for "{q}"  (gl={a.gl} hl={a.hl})')
            if stats:
                print(f"competition: {stats['score']}/100  {stats['band']}  "
                      f"({stats['verified']} of {stats['scored']} verified, "
                      f"median {fmt_views(stats['median_views'])} views)\n")
        print_list([slim(e) for e in entries[: a.top]], a.json)
        return

    vid = _video_id(a.video)
    if not vid:
        print("ERROR: cannot parse video URL or ID", file=sys.stderr)
        sys.exit(1)
    rank = next((i + 1 for i, e in enumerate(entries) if e.get("id") == vid), None)

    log_path = os.path.expanduser(a.log)
    try:
        with open(log_path, encoding="utf-8") as f:
            log = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        log = []
    # history is per-locale: a #3 in the US and a #3 in India are not the same #3
    history = [r for r in log
               if r.get("keyword") == q and r.get("video") == vid
               and r.get("gl", "US") == a.gl and r.get("hl", "en") == a.hl]
    prev = history[-1]["rank"] if history else None
    log.append({"keyword": q, "video": vid, "rank": rank, "gl": a.gl, "hl": a.hl,
                "checked_at": time.strftime("%Y-%m-%d %H:%M")})
    parent = os.path.dirname(log_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    if a.json:
        print(json.dumps({"keyword": q, "video": vid, "rank": rank, "gl": a.gl, "hl": a.hl,
                          "previous": prev, "history": history + log[-1:]},
                         ensure_ascii=False, indent=2))
        return

    pos = f"#{rank}" if rank else f"not in top {a.top}"
    print(f'"{q}" → {pos}   (gl={a.gl} hl={a.hl})')
    stats = _serp_stats(entries, q, top=a.top)
    if stats and not a.json:
        print(f"competition: {stats['score']}/100  {stats['band']}  "
              f"({stats['verified']} of {stats['scored']} verified, "
              f"median {fmt_views(stats['median_views'])} views)")
    if prev is None:
        print("first check — future runs will show movement")
    elif rank is None or prev is None:
        print(f"previous: #{prev if prev else 'not in top ' + str(a.top)}  (→ no comparison)")
    else:
        diff = prev - rank  # positive = moved up the ranks
        mark = "↑" if diff > 0 else ("↓" if diff < 0 else "→")
        print(f"previous: #{prev}  ({mark}{abs(diff)})")
    if history:
        print("\nhistory:")
        for r in history:
            shown = f"#{r['rank']}" if r["rank"] else f">{a.top}"
            print(f"  {r['checked_at']}  {shown}")


def main():
    ap = argparse.ArgumentParser(description="YouTube research via yt-dlp (no API key).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="Search videos")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--gl", default="US", help="region to rank in (US, IN, GB, JP, …)")
    p.add_argument("--hl", default="en", help="interface language (en, hi, ja, …)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("channel", help="List channel uploads")
    p.add_argument("handle", help="@handle, channel URL, or UC... ID")
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--tab", choices=["videos", "shorts", "streams"], default="videos")
    p.add_argument("--with-duration", action="store_true", help="fetch duration per video (slower)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_channel)

    p = sub.add_parser("latest", help="Most recent uploads")
    p.add_argument("handle", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--with-duration", action="store_true", help="fetch duration per video (slower)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("playlist", help="List playlist videos")
    p.add_argument("playlist", help="Playlist URL or ID")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_playlist)

    p = sub.add_parser("profile", help="Channel profile / About section")
    p.add_argument("profile", help="@handle or channel URL")
    p.add_argument("--with-shorts", action="store_true", help="also fetch shorts count (slower)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("posts", help="Community posts (raw scrape; yt-dlp can't do this)")
    p.add_argument("posts", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_posts)

    p = sub.add_parser("sections", help="Count every tab/section of a channel")
    p.add_argument("sections", help="@handle or channel URL")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_sections)

    p = sub.add_parser("shows", help="List a channel's Shows (episode collections)")
    p.add_argument("shows", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_shows)

    p = sub.add_parser("home", help="Home tab shelves (featured video, sections, Featured Channels)")
    p.add_argument("home", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10, help="max items listed per shelf")
    p.add_argument("--verbose", action="store_true", help="also list each shelf's video/playlist items")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_home)

    p = sub.add_parser("info", help="Full metadata for one video")
    p.add_argument("info", help="Video URL or ID")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("scorecard", help="SEO checklist for a video (title/desc/tags/keyword fit)")
    p.add_argument("video", help="Video URL or ID")
    p.add_argument("--keyword", help="target keyword to check fit against")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scorecard)

    p = sub.add_parser("outliers", help="Find videos overperforming their channel (views/subs ratio)")
    p.add_argument("handle", help="@handle, channel URL, or UC... ID")
    p.add_argument("--min-ratio", type=float, default=3.0,
                   help="minimum views/subscriber ratio (default 3.0)")
    p.add_argument("--limit", type=int, default=20, help="max videos to scan per tab")
    p.add_argument("--tab", choices=["videos", "shorts", "all"], default="all",
                   help="which tab to scan (default: all)")
    p.add_argument("--verify-subs", action="store_true",
                   help="cross-check subscriber count against a video from the channel")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_outliers)

    p = sub.add_parser("gap", help="Content gap: my seed keywords vs competitor's profile keywords")
    p.add_argument("seed", help="Your seed keyword")
    p.add_argument("--competitor", required=True, help="Competitor @handle, URL, or UC... ID")
    p.add_argument("--gl", default="US", help="region for suggestions (US, IN, GB, …)")
    p.add_argument("--hl", default="en", help="suggestion language (en, hi, ja, …)")
    p.add_argument("--limit", type=int, default=20, help="keywords to show per side")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_gap)

    p = sub.add_parser("keywords", help="Keyword ideas + relative volume from YouTube suggest (no API key)")
    p.add_argument("seed", help="Seed keyword, e.g. \"thumbnail ideas\"")
    p.add_argument("--letters", default="abcdefghijklmnopqrstuvwxyz",
                   help="alphabet-soup suffixes to expand with ('' to disable)")
    p.add_argument("--patterns", action="store_true",
                   help="also try how/why/best/for-beginners/vs/year patterns")
    p.add_argument("--limit", type=int, default=25)
    p.add_argument("--gl", default="US", help="region for suggestions (US, IN, GB, …)")
    p.add_argument("--hl", default="en", help="suggestion language (en, hi, ja, …)")
    p.add_argument("--sources", default="yt,ddg",
                   help="engines to merge: yt (YouTube suggest), ddg (DuckDuckGo)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_keywords)

    p = sub.add_parser("compete", help="Competition score for a keyword (0-100, from the live SERP)")
    p.add_argument("query", help="keyword to score")
    p.add_argument("--top", type=int, default=10, help="how many results to score")
    p.add_argument("--gl", default="US", help="region to rank in (US, IN, GB, JP, …)")
    p.add_argument("--hl", default="en", help="interface language (en, hi, ja, …)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_compete)

    p = sub.add_parser("trends", help="Historical trend for a seed keyword (from keywords runs)")
    p.add_argument("seed", help="Seed keyword, e.g. \"youtube seo\"")
    p.add_argument("--gl", default="US", help="region (US, IN, GB, …)")
    p.add_argument("--hl", default="en", help="suggestion language (en, hi, ja, …)")
    p.add_argument("--days", type=int, help="only show last N days")
    p.add_argument("--limit", type=int, default=20, help="how many top keywords to show")
    p.add_argument("--verbose", action="store_true", help="show full history per keyword")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_trends)

    p = sub.add_parser("track", help="Rank tracking — where a video sits for a keyword")
    p.add_argument("query", help="keyword to search")
    p.add_argument("--video", help="your video URL/ID to track (omit: show current top results)")
    p.add_argument("--top", type=int, default=20, help="how many results to search")
    p.add_argument("--gl", default="US", help="region to rank in (US, IN, GB, JP, …)")
    p.add_argument("--hl", default="en", help="interface language (en, hi, ja, …)")
    p.add_argument("--log", default="~/.ytdata-ranklog.json", help="rank history file")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_track)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
