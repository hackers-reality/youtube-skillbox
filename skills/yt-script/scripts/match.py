#!/usr/bin/env python3
"""
Match titles against the 21 hook formulas in hooks.json.

Title-agnostic. Pure logic, no network — callers can feed channel.json from
`ytdata channel --json`, a plain text file (one title per line) or stdin.

Usage:
  python match.py --channel channel.json --json          # rank each title
  python match.py titles.txt --json                      # one title per line
  python match.py --hook "What if Earth stopped for 1 second?" --json
  python match.py --channel channel.json --top 10 --json # only first N titles

Judgment note: a match means the title *follows the shape* of a proven formula.
It is NOT a promise the video will perform. The 21 patterns are heuristic
tigers — treat output as a ranked shortlist, never as a guarantee.
"""
import argparse
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
HOOKS_PATH = os.path.join(HERE, "..", "hooks.json")


def load_hooks(path=HOOKS_PATH):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    hooks = data.get("hooks", [])
    compiled = []
    for h in hooks:
        pats = []
        for p in h.get("match", []):
            try:
                pats.append(re.compile(p, re.I | re.S))
            except re.error:
                continue
        compiled.append({**h, "_patterns": pats})
    return compiled


def score_title(title, hooks):
    """Return list of (formula, hits) per formula, sorted best-first."""
    results = []
    t = title.strip()
    if not t:
        return []
    for h in hooks:
        hits = sum(1 for p in h["_patterns"] if p.search(t))
        if hits:
            results.append({
                "id": h["id"],
                "name": h["name"],
                "hits": hits,
                "shape": h.get("shape", ""),
                "example": h.get("example", ""),
                "fails_when": h.get("fails_when", ""),
            })
    results.sort(key=lambda r: (-r["hits"], r["name"]))
    return results


def classify(title, hooks):
    """Best hook for a transcript/title, plus confidence (hits count)."""
    scored = score_title(title, hooks)
    if not scored:
        return None, 0
    return scored[0]["name"], scored[0]["hits"]


def main():
    ap = argparse.ArgumentParser(description="Match titles against the 21 hook formulas")
    ap.add_argument("input", nargs="?", help="titles.txt (one title per line) or channel.json")
    ap.add_argument("--channel", dest="channel_json", help="channel.json from ytdata (reads titles from it)")
    ap.add_argument("--hook", help="single literal title to match")
    ap.add_argument("--top", type=int, default=0, help="only score the first N titles")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--hooks", default=HOOKS_PATH, help="hooks.json path (default: bundled)")
    args = ap.parse_args()

    hooks = load_hooks(args.hooks)

    titles = []
    if args.hook:
        titles = [args.hook]
    elif args.channel_json:
        with open(args.channel_json, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        vids = data if isinstance(data, list) else data.get("videos", data.get("uploads", []))
        for v in vids:
            if isinstance(v, dict) and v.get("title"):
                titles.append(v["title"])
    elif args.input:
        with open(args.input, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line:
                    titles.append(line)
    else:
        ap.error("provide --hook, --channel, or a titles file")

    if args.top > 0:
        titles = titles[: args.top]

    rows = []
    for t in titles:
        matches = score_title(t, hooks)
        rows.append({"title": t, "matches": matches})

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return

    for r in rows:
        title = r["title"]
        clip = title if len(title) <= 64 else title[:61] + "…"
        if not r["matches"]:
            print(f"— {clip}\n     NO FORMULA MATCH (these are usually summaries, not hooks)")
            continue
        top = r["matches"][0]
        others = ", ".join(f"{m['name']} ({m['hits']})" for m in r["matches"][1:4])
        print(f"✓ {top['name']} ({top['hits']} match{'es' if top['hits'] > 1 else ''})  {clip}")
        if others:
            print(f"     also: {others}")


if __name__ == "__main__":
    main()
