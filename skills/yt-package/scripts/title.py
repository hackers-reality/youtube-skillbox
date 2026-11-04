#!/usr/bin/env python3
"""
Title & Thumbnail Scoring for YouTube Videos

Scores 0-100 based on CTR optimization heuristics:
- Length (mobile/desktop truncation)
- Keyword presence & position
- Emotional hooks
- Clarity vs clickbait balance
- Thumbnail-text synergy
"""
import json
import re
import sys
import argparse
from typing import Dict, List, Tuple
from pathlib import Path


# ============================================================
# TITLE SCORING RULES
# ============================================================

TITLE_RULES = [
    {
        "id": "length_desktop",
        "name": "Desktop Length (≤60 chars)",
        "check": lambda t: len(t) <= 60,
        "weight": 15,
        "fail_msg": f"Title too long for desktop search ({{len}} chars > 60)",
        "pass_msg": "Optimal desktop length"
    },
    {
        "id": "length_mobile",
        "name": "Mobile Length (≤40 chars)",
        "check": lambda t: len(t) <= 40,
        "weight": 10,
        "fail_msg": f"Title truncates on mobile ({{len}} chars > 40)",
        "pass_msg": "Optimal mobile length"
    },
    {
        "id": "keyword_front",
        "name": "Keyword in First 3 Words",
        "check": lambda t, kw: kw.lower() in " ".join(t.lower().split()[:3]) if kw else False,
        "weight": 15,
        "fail_msg": "Target keyword not in first 3 words",
        "pass_msg": "Keyword positioned for SEO",
        "requires_kw": True
    },
    {
        "id": "keyword_present",
        "name": "Keyword Present Anywhere",
        "check": lambda t, kw: kw.lower() in t.lower() if kw else False,
        "weight": 10,
        "fail_msg": "Target keyword missing from title",
        "pass_msg": "Keyword present",
        "requires_kw": True
    },
    {
        "id": "number_specificity",
        "name": "Specific Number Present",
        "check": lambda t: bool(re.search(r'\d+(?:,\d{3})*(?:\.\d+)?', t)),
        "weight": 10,
        "fail_msg": "No specific number (add quantity, percentage, year, etc.)",
        "pass_msg": "Specific number adds credibility"
    },
    {
        "id": "year_current",
        "name": "Current Year Mentioned",
        "check": lambda t: str(__import__('datetime').datetime.now().year) in t,
        "weight": 8,
        "fail_msg": "No current year (adds freshness signal)",
        "pass_msg": "Current year signals freshness"
    },
    {
        "id": "question_format",
        "name": "Question Format",
        "check": lambda t: t.strip().endswith("?") or t.lower().startswith(("what", "why", "how", "where", "when", "who")),
        "weight": 8,
        "fail_msg": "Not a question (questions drive 14% higher CTR)",
        "pass_msg": "Question format drives curiosity"
    },
    {
        "id": "emotional_word",
        "name": "High-Arousal Emotion Word",
        "check": lambda t: any(w in t.lower() for w in [
            "shocking", "insane", "insane", "crazy", "insane", "wild", "insane",
            "shocking", "mind-blowing", "devastating", "incredible", "unbelievable",
            "secret", "hidden", "banned", "forbidden", "censored", "shocking",
            "terrifying", "devastating", "amazing", "incredible", "insane"
        ]),
        "weight": 8,
        "fail_msg": "No high-arousal emotion word",
        "pass_msg": "Emotional trigger present"
    },
    {
        "id": "bracket_clarity",
        "name": "Brackets for Clarity",
        "check": lambda t: bool(re.search(r'\[.*?\]|\(.*?\)', t)),
        "weight": 5,
        "fail_msg": "No brackets for format/clarity (e.g., [Tutorial], (2024))",
        "pass_msg": "Brackets clarify format"
    },
    {
        "id": "series_branding",
        "name": "Series/Brand Consistency",
        "check": lambda t: bool(re.search(r'(ep\.?|episode|part|#)\s*\d+', t, re.I)),
        "weight": 5,
        "fail_msg": "No episode/part numbering for series",
        "pass_msg": "Series branding present"
    },
    {
        "id": "no_clickbait_words",
        "name": "Avoids Clickbait Red Flags",
        "check": lambda t: not any(w in t.lower() for w in [
            "gone wrong", "gone sexual", "you won't believe", "shocking!!",
            "omg", "omfg", "lmao", "literally died", "i can't even"
        ]),
        "weight": 10,
        "fail_msg": "Contains clickbait red flags (hurts trust)",
        "pass_msg": "Clean title, builds trust"
    },
    {
        "id": "no_all_caps",
        "name": "Avoids All-Caps Spam",
        "check": lambda t: not (len([w for w in t.split() if w.isupper() and len(w) > 2]) > 2),
        "weight": 5,
        "fail_msg": "Too many ALL CAPS words (looks spammy)",
        "pass_msg": "Normal capitalization"
    },
    {
        "id": "front_loaded_value",
        "name": "Value Front-Loaded",
        "check": lambda t: any(t.lower().startswith(p) for p in [
            "how to", "why ", "what ", "the secret", "the truth", 
            "stop ", "don't ", "never ", "always ", "the best", "the worst"
        ]),
        "weight": 8,
        "fail_msg": "Value not front-loaded (first 3 words should promise value)",
        "pass_msg": "Value proposition front-loaded"
    },
]


def score_title(title: str, keyword: str = "") -> Dict:
    """Score a title against all rules.
    
    When no keyword is provided, keyword-dependent rules are excluded from both
    earned weight and total possible weight (score is calculated from applicable checks only).
    """
    results = []
    total_weight = 0
    earned_weight = 0
    
    for rule in TITLE_RULES:
        weight = rule["weight"]
        
        # Skip keyword-dependent rules if no keyword provided
        if rule.get("requires_kw") and not keyword:
            continue
        
        # Only count weight for rules that are actually evaluated
        total_weight += weight
        
        if rule.get("requires_kw"):
            passed = rule["check"](title, keyword)
        else:
            passed = rule["check"](title)
        
        earned = weight if passed else 0
        earned_weight += earned
        
        results.append({
            "rule": rule["name"],
            "passed": passed,
            "weight": weight,
            "earned": earned,
            "message": rule["pass_msg"].format(len=len(title)) if passed 
                       else rule["fail_msg"].format(len=len(title))
        })
    
    score = round((earned_weight / total_weight) * 100) if total_weight else 0
    
    return {
        "score": score,
        "max_score": 100,
        "checks": results,
        "title_length": len(title),
        "word_count": len(title.split())
    }


def score_thumbnail_text(thumb_text: str) -> Dict:
    """Score thumbnail text (max 3 words, high contrast)."""
    words = thumb_text.split()
    checks = []
    
    # Word count
    word_count = len(words)
    if word_count <= 3:
        checks.append({"check": "Word count ≤ 3", "passed": True, "score": 20})
    elif word_count <= 4:
        checks.append({"check": "Word count ≤ 3", "passed": False, "score": 10, "note": "4 words - borderline"})
    else:
        checks.append({"check": "Word count ≤ 3", "passed": False, "score": 0, "note": f"{word_count} words - too many"})
    
    # All caps for emphasis
    caps_words = sum(1 for w in words if w.isupper() and len(w) > 1)
    if caps_words >= 1:
        checks.append({"check": "Has ALL CAPS emphasis word", "passed": True, "score": 15})
    else:
        checks.append({"check": "Has ALL CAPS emphasis word", "passed": False, "score": 0})
    
    # Number present
    if any(re.search(r'\d', w) for w in words):
        checks.append({"check": "Contains number", "passed": True, "score": 15})
    else:
        checks.append({"check": "Contains number", "passed": False, "score": 0})
    
    # Emotion word
    emotion_words = {"SHOCKING", "INSANE", "WILD", "CRAZY", "SECRET", "BANNED", "HIDDEN", "BANNED"}
    if any(w.upper() in emotion_words for w in words):
        checks.append({"check": "High-arousal emotion word", "passed": True, "score": 15})
    else:
        checks.append({"check": "High-arousal emotion word", "passed": False, "score": 0})
    
    # No long words
    long_words = [w for w in words if len(w) > 10]
    if not long_words:
        checks.append({"check": "No words > 10 chars", "passed": True, "score": 10})
    else:
        checks.append({"check": "No words > 10 chars", "passed": False, "score": 0, "note": f"Long words: {long_words}"})
    
    total = sum(c.get("score", 0) for c in checks)
    
    return {
        "score": min(100, total),
        "word_count": word_count,
        "words": words,
        "checks": checks
    }


def score_package(title: str, thumb_text: str = "", keyword: str = "") -> Dict:
    """Combined title + thumbnail score."""
    title_result = score_title(title, keyword)
    thumb_result = score_thumbnail_text(thumb_text) if thumb_text else {"score": 0, "checks": []}
    
    # Combined: 60% title, 40% thumbnail
    combined = round(title_result["score"] * 0.6 + thumb_result["score"] * 0.4)
    
    return {
        "combined_score": combined,
        "title": title_result,
        "thumbnail": thumb_result,
        "verdict": "SHIP" if combined >= 70 else "REVISE" if combined >= 50 else "REWORK"
    }


def main():
    parser = argparse.ArgumentParser(description="Score YouTube title + thumbnail")
    parser.add_argument("title", nargs="?", help="Video title")
    parser.add_argument("--thumb", help="Thumbnail text (max 3 words)")
    parser.add_argument("--keyword", help="Target keyword for SEO")
    parser.add_argument("--file", help="JSON file with titles array")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
        titles = data.get("titles", [])
        results = []
        for t in titles:
            kw = t.get("keyword", "") if isinstance(t, dict) else ""
            thumb = t.get("thumb", "") if isinstance(t, dict) else ""
            title = t.get("title", t) if isinstance(t, dict) else t
            results.append(score_package(title, thumb, kw))
        if args.json:
            print(json.dumps(results, indent=2))
        else:
            for r in results:
                print(f"{r['combined_score']}/100 - {r['title']['checks'][0]['message'] if r['title']['checks'] else ''}")
    elif args.title:
        result = score_package(args.title, args.thumb or "", args.keyword or "")
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"\nTitle: {args.title}")
            print(f"Thumbnail: {args.thumb or '(none)'}")
            print(f"Keyword: {args.keyword or '(none)'}")
            print(f"\nCOMBINED SCORE: {result['combined_score']}/100 - {result['verdict']}")
            print(f"\nTitle Analysis ({result['title']['score']}/100):")
            for c in result['title']['checks']:
                status = "✅" if c['passed'] else "❌"
                print(f"  {status} [{c['weight']}] {c['message']}")
            if result['thumbnail']['score']:
                print(f"\nThumbnail Analysis ({result['thumbnail']['score']}/100):")
                for c in result['thumbnail']['checks']:
                    status = "✅" if c.get('passed', False) else "❌"
                    print(f"  {status} {c['check']}: {c.get('score', 0)}pts")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()