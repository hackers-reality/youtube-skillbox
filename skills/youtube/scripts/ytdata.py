#!/usr/bin/env python3
"""
YouTube research via yt-dlp + raw page scraping: search, channels, playlists,
metadata, community posts (paginated), home sections, shows, keyword research
and rank tracking. No API key, no credits.

Subcommands:
  search   <query>              Search YouTube videos.
  keywords <seed>               Keyword ideas + relative demand (YouTube + DDG suggest).
  track    <query> --video URL  Rank position for a keyword, with ↑↓ history.
  profile  <handle-or-url>      Channel About/profile section.
  sections <handle-or-url>      Count every tab (videos/shorts/shows/playlists/posts).
  channel  <handle-or-url>      List a channel's uploads.
  latest   <handle-or-url>      Most recent uploads (reverse-chronological).
  posts    <handle-or-url>      Community posts — paginates past the first page.
  home     <handle-or-url>      Home tab shelves (Featured Channels, sections).
  shows    <handle-or-url>      Channel Shows (episode collections).
  playlist <url-or-id>          List a playlist's videos.
  info     <url-or-id>          Full metadata for one video (views, likes, date, tags).

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
    cmd = [sys.executable, "-m", "yt_dlp"] + args + ["--no-warnings"]
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
    verified = any("VERIFIED" in ((b.get("metadataBadgeRenderer") or {}).get("badgeStyleType") or "")
                   for b in v.get("badges") or [])
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
    print_list([slim(e) for e in entries[: a.limit]], a.json)


def cmd_latest(a):
    # /videos tab is reverse-chronological by default, so the head is "latest".
    base = a.handle if a.handle.startswith("http") else f"https://www.youtube.com/{a.handle}"
    if not base.rstrip("/").endswith(("/videos", "/shorts")):
        base = base.rstrip("/") + "/videos"
    args = [base, "--playlist-items", f"1-{a.limit}"]
    entries = dump_entries(args)
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
    for tab in tabs:
        proc = run_ytdlp(["--flat-playlist", "--dump-json", f"{base}/{tab}"])
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        count = len(lines)
        # yt-dlp errors when a tab doesn't exist (e.g. no streams tab).
        if count == 0 and ("does not have" in (proc.stderr or "") or proc.returncode != 0):
            result[tab] = None  # tab doesn't exist
        else:
            result[tab] = count

    # Shows tab: yt-dlp can't parse gridShowRenderer, so count via raw scrape.
    try:
        shows_html = _http_get(base + "/shows")
        shows_data = _extract_ytInitialData(shows_html)
        n_shows = sum(1 for _ in _find_renderers(shows_data or {}, "gridShowRenderer"))
        # A channel without a Shows tab gets redirected to a page with no shows.
        result["shows"] = n_shows if n_shows else None
    except Exception:
        result["shows"] = None

    # Community posts: page 1 + one continuation probe for an honest count.
    n_posts, has_more = _count_community(base)
    result["community_posts"] = n_posts
    result["community_posts_more"] = has_more

    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    def fmt(v, none="no tab"):
        return none if v is None else v

    print(f"Channel: {base}")
    print(f"  videos   : {fmt(result['videos'])}")
    print(f"  shorts   : {fmt(result['shorts'])}")
    print(f"  streams  : {fmt(result['streams'])}")
    print(f"  shows    : {fmt(result['shows'])}")
    print(f"  playlists: {fmt(result['playlists'])}")
    more = "+" if result["community_posts_more"] else ""
    print(f"  community: {result['community_posts']}{more} posts (use `posts` to read them)")


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
    base = a.profile if a.profile.startswith("http") else f"https://www.youtube.com/{a.profile}"
    proc = run_ytdlp(["--skip-download", "--dump-single-json", base])
    if proc.returncode != 0 or not proc.stdout.strip():
        err = (proc.stderr or "").strip().splitlines()
        print(f"ERROR: {err[-1] if err else 'could not fetch channel profile'}", file=sys.stderr)
        sys.exit(1)
    d = json.loads(proc.stdout)
    payload = {
        "name": d.get("channel") or d.get("uploader"),
        "handle": d.get("id"),
        "channel_url": d.get("webpage_url") or d.get("channel_url"),
        "subscribers": d.get("channel_follower_count"),
        "video_count": d.get("playlist_count") or d.get("upload_count"),
        "total_views": d.get("view_count"),
        "description": d.get("channel_description") or d.get("description"),
        "tags": d.get("tags"),
        "country": d.get("channel_country") or d.get("country"),
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


# ---- Keyword research via YouTube suggest (free, no API key) ----
# The suggest box runs on real query popularity — the same signal free SEO
# tools approximate volume with. We expand a seed through the alphabet and
# score how often/where each suggestion comes back.

_SUGGEST_URL = "https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q="


def _suggest(q, gl="US", hl="en", timeout=8):
    """One YouTube suggest lookup. Returns a list of suggestion strings (empty on any failure)."""
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
            out.append(item[0])
    return out


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


def _ddg_kl(gl, hl):
    """Map --gl/--hl to a DuckDuckGo kl code, or None to take DDG's own default."""
    gl, hl = (gl or "").upper(), (hl or "").lower()
    return _DDG_KL.get((gl, hl)) or _DDG_KL.get((gl, "en"))


def _suggest_ddg(q, kl=None, timeout=8):
    """One DuckDuckGo autocomplete lookup (list form). Empty list on any failure."""
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
        return [s for s in data[1] if isinstance(s, str)]
    if isinstance(data, list):   # bare form: [{"phrase": "..."}, ...]
        return [d.get("phrase") for d in data if isinstance(d, dict) and d.get("phrase")]
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
            for pos, s in enumerate(_suggest(q, gl=a.gl, hl=a.hl)):
                note(s, pos, "yt")
        if "ddg" in use:
            for pos, s in enumerate(_suggest_ddg(q, kl=kl)):
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


# ---- Rank tracking: where a video sits for a keyword (no API key) ----

def _video_id(url_or_id):
    m = re.search(r"(?:[?&]v=|/shorts/|/embed/|/live/)([\w-]{11})", url_or_id)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w-]{11}", url_or_id):
        return url_or_id
    return None


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
        if not a.json:
            print(f'Top {min(len(entries), a.top)} for "{q}"  (gl={a.gl} hl={a.hl})\n')
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
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_channel)

    p = sub.add_parser("latest", help="Most recent uploads")
    p.add_argument("handle", help="@handle or channel URL")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_latest)

    p = sub.add_parser("playlist", help="List playlist videos")
    p.add_argument("playlist", help="Playlist URL or ID")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_playlist)

    p = sub.add_parser("profile", help="Channel profile / About section")
    p.add_argument("profile", help="@handle or channel URL")
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
