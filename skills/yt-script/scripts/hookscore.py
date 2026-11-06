#!/usr/bin/env python3
"""
Pure Mathematical Hook Analysis for YouTube Videos

Pure statistical analysis of first N seconds of transcript.
NO formulas, NO biases, NO heuristics - pure mathematical analysis.

Outputs raw statistical features that ANY channel type can use.
"""
import json
import os
import re
import sys
import argparse
import statistics
from collections import Counter
from typing import Dict, List, Tuple
from pathlib import Path


def extract_first_n_seconds(transcript: List[Dict], n_seconds: int = 15) -> str:
    """Extract transcript text from first N seconds."""
    segments = []
    for seg in transcript:
        if seg.get("start", 0) <= n_seconds:
            segments.append(seg.get("text", ""))
        else:
            break
    return " ".join(segments)


def analyze_text_statistics(text: str, n_seconds: int) -> Dict:
    """Pure statistical analysis of hook text."""
    if not text.strip():
        return {"error": "Empty text"}
    
    words = text.split()
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Basic counts
    char_count = len(text)
    word_count = len(words)
    sentence_count = len(sentences)
    unique_words = len(set(w.lower() for w in words))
    
    # Rates
    words_per_second = word_count / n_seconds if n_seconds > 0 else 0
    words_per_sentence = word_count / sentence_count if sentence_count > 0 else 0
    lexical_diversity = unique_words / word_count if word_count > 0 else 0
    
    # Sentence lengths
    sentence_lengths = [len(s.split()) for s in sentences]
    avg_sentence_length = statistics.mean(sentence_lengths) if sentence_lengths else 0
    median_sentence_length = statistics.median(sentence_lengths) if sentence_lengths else 0
    
    # Word length distribution
    word_lengths = [len(w) for w in words]
    avg_word_length = statistics.mean(word_lengths) if word_lengths else 0
    max_word_length = max(word_lengths) if word_lengths else 0
    
    # Punctuation analysis
    question_marks = text.count('?')
    exclamation_marks = text.count('!')
    commas = text.count(',')
    periods = text.count('.')
    colons = text.count(':')
    semicolons = text.count(';')
    dashes = text.count('-')
    parentheses = text.count('(') + text.count(')')
    brackets = text.count('[') + text.count(']')
    quotes = text.count('"') + text.count("'")
    
    # Capitalization analysis
    words_upper = [w for w in words if w.isupper() and len(w) > 1]
    words_title = [w for w in words if w.istitle()]
    all_caps_ratio = len(words_upper) / word_count if word_count > 0 else 0
    title_case_ratio = len(words_title) / word_count if word_count > 0 else 0
    
    # Number detection
    numbers = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?\b', text)
    numbers_with_units = re.findall(r'\d+(?:,\d{3})*(?:\.\d+)?\s*(?:km/h|mph|km|miles|feet|meters|seconds?|minutes?|hours?|days?|years?|dollars?|\$|percent|%|times?|x\b|people|users|viewers|subscribers?)', text, re.IGNORECASE)
    
    # Time references
    time_refs = re.findall(r'\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b', text, re.IGNORECASE)
    
    # Question detection
    questions = text.count('?')
    question_words = len(re.findall(r'\b(why|how|what|when|where|who|which)\b', text, re.IGNORECASE))
    
    # Imperative/command detection
    imperatives = len(re.findall(r'\b(watch|subscribe|follow|click|tap|check|look|see|try|start|begin|join|download|get|grab|subscribe)\b', text, re.IGNORECASE))
    
    # Personal pronoun density
    personal_pronouns = len(re.findall(r'\b(you|your|you\'re|you\'ll|you\'ve|you\'d|i|me|my|mine|we|our|us)\b', text, re.IGNORECASE))
    second_person = len(re.findall(r'\b(you|your|you\'re|you\'ll|you\'ve|you\'d)\b', text, re.IGNORECASE))
    
    # Negation density
    negations = len(re.findall(r'\b(not|no|never|nothing|nobody|nowhere|neither|nor|don\'t|doesn\'t|didn\'t|won\'t|wouldn\'t|couldn\'t|shouldn\'t|isn\'t|aren\'t|wasn\'t|weren\'t)\b', text, re.IGNORECASE))
    
    # Certainty/uncertainty markers
    certainty = len(re.findall(r'\b(definitely|certainly|absolutely|clearly|obviously|undoubtedly|surely|guaranteed)\b', text, re.IGNORECASE))
    uncertainty = len(re.findall(r'\b(maybe|perhaps|possibly|might|could|seems|appears|probably|likely|unclear|uncertain)\b', text, re.IGNORECASE))
    
    # Temporal markers
    past_tense = len(re.findall(r'\b(was|were|had|did|went|made|said|told|gave|took|came|saw|knew|thought)\b', text, re.IGNORECASE))
    present_tense = len(re.findall(r'\b(is|are|am|have|has|do|does|say|tell|give|take|see|know|think|feel)\b', text, re.IGNORECASE))
    future_tense = len(re.findall(r'\b(will|would|shall|going to|gonna)\b', text, re.IGNORECASE))
    
    # Emotional intensity words (neutral list - just counts intensity markers)
    intensity_markers = len(re.findall(r'\b(very|really|extremely|incredibly|absolutely|totally|completely|utterly|absolutely|truly|genuinely)\b', text, re.IGNORECASE))
    
    # Superlatives/comparatives
    superlatives = len(re.findall(r'\b(best|worst|biggest|smallest|fastest|slowest|greatest|least|most|highest|lowest|greatest|maximum|minimum|only|first|last|#1|number one)\b', text, re.IGNORECASE))
    comparatives = len(re.findall(r'\b(better|worse|bigger|smaller|faster|slower|higher|lower|more|less|greater|fewer|stronger|weaker)\b', text, re.IGNORECASE))
    
    # Negation + superlative combo (e.g. "not the best")
    negation_superlative = len(re.findall(r'(not|never|no)\s+\w*(?:best|worst|biggest|smallest|fastest|slowest|greatest|most)', text, re.IGNORECASE))
    
    # First person vs second person vs third person
    first_person = len(re.findall(r'\b(i|me|my|mine|we|us|our|ours)\b', text, re.IGNORECASE))
    third_person = len(re.findall(r'\b(he|she|it|they|them|their|his|her|its)\b', text, re.IGNORECASE))
    
    # Conjunctions (flow markers)
    conjunctions = len(re.findall(r'\b(and|but|or|so|because|since|therefore|thus|however|yet|still|also|then|when|while|if|unless)\b', text, re.IGNORECASE))
    
    return {
        "basic_counts": {
            "characters": char_count,
            "words": word_count,
            "sentences": sentence_count,
            "unique_words": unique_words,
        },
        "rates": {
            "words_per_second": round(words_per_second, 2),
            "words_per_sentence": round(words_per_sentence, 2),
            "lexical_diversity": round(lexical_diversity, 4),
        },
        "sentence_structure": {
            "avg_sentence_length": round(avg_sentence_length, 2),
            "median_sentence_length": round(median_sentence_length, 2),
            "sentence_lengths": sentence_lengths,
            "avg_word_length": round(avg_word_length, 2),
            "max_word_length": max_word_length,
        },
        "punctuation": {
            "questions": question_marks,
            "exclamations": exclamation_marks,
            "commas": commas,
            "periods": periods,
            "colons": colons,
            "semicolons": semicolons,
            "dashes": dashes,
            "parentheses": parentheses,
            "brackets": brackets,
            "quotes": quotes,
        },
        "capitalization": {
            "all_caps_words": len(words_upper),
            "all_caps_ratio": round(all_caps_ratio, 4),
            "title_case_words": len(words_title),
            "title_case_ratio": round(title_case_ratio, 4),
        },
        "numbers": {
            "raw_numbers": len(numbers),
            "numbers_with_units": len(numbers_with_units),
            "numbers_list": numbers,
            "numbers_with_units_list": numbers_with_units,
        },
        "time_references": {
            "count": len(time_refs),
            "details": time_refs,
        },
        "questions": {
            "question_marks": questions,
            "question_words": question_words,
        },
        "imperatives": {
            "count": imperatives,
        },
        "pronouns": {
            "personal_total": personal_pronouns,
            "second_person": second_person,
            "first_person": first_person,
            "third_person": third_person,
            "second_person_ratio": round(second_person / word_count, 4) if word_count > 0 else 0,
        },
        "negations": {
            "count": negations,
        },
        "certainty": {
            "certainty_markers": certainty,
            "uncertainty_markers": uncertainty,
            "certainty_ratio": round(certainty / (certainty + uncertainty), 4) if (certainty + uncertainty) > 0 else 0,
        },
        "temporal_markers": {
            "past_tense": past_tense,
            "present_tense": present_tense,
            "future_tense": future_tense,
        },
        "intensity": {
            "intensity_markers": intensity_markers,
        },
        "comparisons": {
            "superlatives": superlatives,
            "comparatives": comparatives,
            "negation_superlative": negation_superlative,
        },
        "flow_markers": {
            "conjunctions": conjunctions,
        },
        "emotional_intensity_words": intensity_markers,
        "superlatives": superlatives,
        "comparatives": comparatives,
    }


def extract_first_n_seconds(transcript: List[Dict], n_seconds: int = 15) -> str:
    """Extract transcript text from first N seconds."""
    segments = []
    for seg in transcript:
        if seg.get("start", 0) <= n_seconds:
            segments.append(seg.get("text", ""))
        else:
            break
    return " ".join(segments)


def resolve_gettranscript():
    """Find gettranscript.py relative to THIS file — cwd-independent.

    Repo layout: skills/yt-script/scripts/hookscore.py
    -> skills/transcript/scripts/gettranscript.py (skills root = parents[2]).
    Installed layout (opencode skills dir) mirrors it. Walk up as fallback
    so a repo checkout at any depth still resolves.
    """
    here = Path(__file__).resolve()
    # here: .../yt-script/scripts/hookscore.py ; skills root = parents[2]
    skills_root = here.parents[2]
    cand = skills_root / "transcript" / "scripts" / "gettranscript.py"
    if cand.exists():
        return cand
    for parent in here.parents:
        cand = parent / "skills" / "transcript" / "scripts" / "gettranscript.py"
        if cand.exists():
            return cand
        cand = parent / "transcript" / "scripts" / "gettranscript.py"
        if cand.exists():
            return cand
    return cand  # last resort: expected repo path (for a clear error message)


def run_fetcher(args, timeout=180):
    """Run gettranscript.py and decode its output ROBUSTLY.

    Windows consoles default to cp1252; yt-dlp may emit non-UTF-8 bytes
    (observed 0x8f). Without explicit encoding/errors the OS locale decoder
    raises UnicodeDecodeError inside subprocess's reader thread and
    result.stdout comes back None. Always decode UTF-8 with replacement.
    """
    import subprocess
    return subprocess.run(
        [sys.executable, str(resolve_gettranscript())] + list(args),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout)


def _read_text_tolerant(path):
    """Read a text file tolerating UTF-8, UTF-8-BOM, UTF-16LE/BE (PowerShell `>`).

    Returns the decoded string; never raises UnicodeDecodeError on a
    well-formed text file. Raises ValueError only if no BOM/encoding matches
    (caller converts to a clean exit).
    """
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe"):
        return raw[2:].decode("utf-16-le", errors="replace")
    if raw.startswith(b"\xfe\xff"):
        return raw[2:].decode("utf-16-be", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace")
    # utf-16le without BOM is common from PS `>`; detect NUL pattern.
    if len(raw) >= 2 and raw[1] == 0 and raw[0] != 0:
        return raw.decode("utf-16-le", errors="replace")
    return raw.decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Pure mathematical hook analysis - first N seconds")
    parser.add_argument("input", nargs="?", help="Transcript JSON file or video ID")
    parser.add_argument("--hook", default=None,
                        help="Single hook line to score (compat with installed CLI: `--hook \"line\"`)")
    parser.add_argument("--file", default=None,
                        help="Line-delimited text file of hook candidates (compat: `hookscore.py hooks.txt`)")
    parser.add_argument("--seconds", type=int, default=15, help="Seconds to analyze (default 15)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    # --- compat modes: --hook / --file (score a literal probe line) ---
    probe_lines = []
    if args.hook:
        probe_lines = [args.hook]
    elif args.file:
        text = _read_text_tolerant(args.file)
        probe_lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    if args.input and args.input.endswith(".txt") and not probe_lines:
        # Plain-text transcript line file passed positionally.
        text = _read_text_tolerant(args.input)
        probe_lines = [ln.strip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n") if ln.strip()]
    if probe_lines:
        out = []
        for line in probe_lines:
            stats = analyze_text_statistics(line, args.seconds)
            stats["hook"] = line
            stats["seconds_analyzed"] = args.seconds
            out.append(stats)
        if args.json:
            print(json.dumps(out, ensure_ascii=False, indent=2))
        else:
            for stats in out:
                print(f"\nHOOK: {stats['hook']}")
                print(f"  words: {stats['basic_counts']['words']}  wps: {stats['rates']['words_per_second']}")
            print(f"\nScored {len(out)} hook(s) (compat mode: --hook / --file).")
        return

    if not args.input:
        parser.error("input file/ID (or --hook / --file) is required")

    # Load transcript
    if args.input.endswith((".json", ".json3", ".txt")):
        text = _read_text_tolerant(args.input)
        data = json.loads(text)
        transcript = data.get("transcript", data.get("transcripts", []))
        if isinstance(transcript, dict) and "transcript" in transcript:
            transcript = transcript["transcript"]
    else:
        # Fetch transcript via gettranscript.py (cwd-independent resolution)
        gt = resolve_gettranscript()
        if not gt.exists():
            print(f"ERROR: gettranscript.py not found (resolved: {gt}). "
                  f"Expected it under the skills/ tree next to this script; "
                  f"cwd={os.getcwd()}", file=sys.stderr)
            sys.exit(1)
        result = run_fetcher([args.input, "--format", "json"])
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        data = json.loads(result.stdout)
        transcript = data.get("transcript", [])
        if isinstance(transcript, list) and transcript and "transcript" in transcript[0]:
            transcript = transcript[0]["transcript"]

    # Extract first N seconds
    hook_text = extract_first_n_seconds(transcript, args.seconds)
    
    if not hook_text.strip():
        print("ERROR: No transcript text in first N seconds", file=sys.stderr)
        sys.exit(1)

    # Pure statistical analysis
    result = analyze_text_statistics(hook_text, args.seconds)
    result["seconds_analyzed"] = args.seconds
    result["raw_text_preview"] = hook_text[:500] + "..." if len(hook_text) > 500 else hook_text

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== PURE STATISTICAL HOOK ANALYSIS (first {args.seconds}s) ===")
        print(f"\nBasic Counts:")
        for k, v in result["basic_counts"].items():
            print(f"  {k}: {v}")
        print(f"\nRates:")
        for k, v in result["rates"].items():
            print(f"  {k}: {v}")
        print(f"\nSentence Structure:")
        for k, v in result["sentence_structure"].items():
            print(f"  {k}: {v}")
        print(f"\nPunctuation:")
        for k, v in result["punctuation"].items():
            print(f"  {k}: {v}")
        print(f"\nCapitalization:")
        for k, v in result["capitalization"].items():
            print(f"  {k}: {v}")
        print(f"\nNumbers:")
        for k, v in result["numbers"].items():
            print(f"  {k}: {v}")
        print(f"\nTime References:")
        for k, v in result["time_references"].items():
            print(f"  {k}: {v}")
        print(f"\nQuestions & Imperatives:")
        for k, v in {**result["questions"], **result["imperatives"]}.items():
            print(f"  {k}: {v}")
        print(f"\nPronouns:")
        for k, v in result["pronouns"].items():
            print(f"  {k}: {v}")
        print(f"\nNegations: {result['negations']['count']}")
        print(f"\nCertainty: {result['certainty']['certainty_markers']} certain, {result['certainty']['uncertainty_markers']} uncertain (ratio: {result['certainty']['certainty_ratio']})")
        print(f"\nTemporal Markers:")
        for k, v in result["temporal_markers"].items():
            print(f"  {k}: {v}")
        print(f"\nIntensity Markers: {result['intensity_markers']}")
        print(f"\nComparisons:")
        for k, v in result["comparisons"].items():
            print(f"  {k}: {v}")
        print(f"\nFlow Markers: {result['flow_markers']['conjunctions']}")
        print(f"\nSuperlatives: {result['superlatives']}, Comparatives: {result['comparatives']}")


if __name__ == "__main__":
    main()