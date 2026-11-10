#!/usr/bin/env python3
"""
Title preview simulator — shows how a title actually renders on the three
surfaces YouTube uses. Pure offline rendering; no network, no API keys.

Usage:
  python preview.py "Your radically honest title here" [--thumb "THUMB"]
  python preview.py --file titles.txt --json
  python preview.py "Title" --html out.html

Honesty rules:
  - Truncation is computed per-surface from real character budgets
    (Search ~60, Suggested ~55-60, Shorts ~100). A title that passes
    desktop does NOT pass mobile — show both.
  - This simulates text rendering only. Thumbnail pixels are NOT evaluated.
  - Never present the preview as a CTR or ranking prediction.
"""
import argparse
import html
import json
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Character budgets — desktop search vs mobile viewport. These are
# conservative approximations, not guarantees; real rendering varies by
# browser font. The keyword is always lower-limit pessimistic.
BUDGETS = {
    "search_desktop": 60,
    "search_mobile": 40,
    "suggested_desktop": 60,
    "suggested_mobile": 40,
    "shorts": 100,
}


def truncate(title: str, n: int):
    if len(title) <= n:
        return title, False
    return title[: n - 1].rstrip() + "…", True


def render(title: str, thumb: str = ""):
    surfaces = []
    for name, budget in BUDGETS.items():
        cut, truncated = truncate(title, budget)
        surfaces.append({
            "surface": name,
            "budget": budget,
            "rendered": cut,
            "truncated": truncated,
            "chars": len(cut),
        })
    return surfaces


def to_html(title: str, thumb: str = ""):
    esc = html.escape(title)
    thumb_esc = html.escape(thumb)
    rows = []
    for s in render(title, thumb):
        cls = "bad" if s["truncated"] else "ok"
        rows.append(
            f'<div class="card {cls}"><div class="surface">{s["surface"]} '
            f'<span class="budget">≤{s["budget"]} chars</span></div>'
            f'<div class="title">{html.escape(s["rendered"])}</div>'
            + ('<div class="flag">✂ truncates here</div>' if s["truncated"] else '<div class="flag ok">fits ✓</div>')
            + '</div>'
        )
    body = "\n".join(rows)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Title preview — {esc}</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#0f0f0f; color:#eee; padding:24px; max-width:900px }}
h1 {{ font-size:18px; font-weight:600; margin:0 0 4px }}
.note {{ color:#aaa; font-size:13px; margin-bottom:16px }}
.card {{ background:#1f1f1f; border-radius:8px; padding:12px 14px; margin:10px 0; border-left:4px solid #2e7d32 }}
.card.bad {{ border-left-color:#c62828 }}
.surface {{ font-size:11px; color:#9cdcfe; text-transform:uppercase; letter-spacing:.06em }}
.budget {{ color:#777; margin-left:8px }}
.title {{ font-size:17px; margin:6px 0; line-height:1.35 }}
.flag {{ font-size:12px; color:#ff8a80 }}
.flag.ok {{ color:#69f0ae }}
.badge {{ display:inline-block; background:#333; padding:2px 8px; border-radius:10px; font-size:12px }}
</style></head><body>
<h1>Title preview</h1>
<div class="note">Thumbnail text (text only — image not evaluated): <span class="badge">{thumb_esc or '(none supplied)'}</span><br>
Truncation shown for three surfaces. This is a text sim — no ranking or CTR claim.</div>
{body}
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Preview a title across search/suggested/Shorts surfaces")
    ap.add_argument("title", nargs="?", help="the exact title string to preview")
    ap.add_argument("--thumb", default="", help="thumbnail text (max 3 words — image not evaluated)")
    ap.add_argument("--file", help="UTF-8/BOM-tolerant file with one title per line")
    ap.add_argument("--html", metavar="OUT", help="write a self-contained HTML preview to this path")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    # tolerate utf-8 / utf-8-sig / utf-16 / utf-16le inputs (PowerShell > writes utf-16)
    def read_text(path):
        raw = open(path, "rb").read()
        for enc in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    titles = []
    if args.file:
        for line in read_text(args.file).splitlines():
            if line.strip():
                titles.append(line.strip())
    elif args.title:
        titles = [args.title]
    else:
        ap.error("provide a title or --file")

    if args.html and len(titles) == 1:
        out = to_html(titles[0], args.thumb)
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"wrote {args.html}")
        return

    if args.json:
        print(json.dumps([{"title": t, "thumb": args.thumb, "surfaces": render(t, args.thumb)}
                          for t in titles], indent=2, ensure_ascii=False))
        return

    for t in titles:
        print(f"\nTitle: {t}")
        for s in render(t, args.thumb):
            mark = "✂" if s["truncated"] else "✓"
            print(f"  [{s['surface']:<16} ≤{s['budget']:>2}] {mark} {s['rendered']}")
        if args.thumb:
            print(f"  thumbnail text: {args.thumb} (image not evaluated)")


if __name__ == "__main__":
    main()
