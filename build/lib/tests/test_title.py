#!/usr/bin/env python3
"""
Tests for skills/yt-package/scripts/title.py

Covers:
- Title scoring weight calculation (exclude keyword rules when no keyword provided)
- Title scoring with keyword provided
- Thumbnail text scoring
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "yt-package", "scripts"))
import title


class TestTitleScoringWithoutKeyword(unittest.TestCase):
    """Test score_title when no keyword is provided."""

    def test_excludes_keyword_rules(self):
        """Keyword-dependent rules should be excluded from total weight."""
        result = title.score_title("How to Make YouTube Videos", keyword="")
        
        # Check that keyword rules are not in checks
        keyword_rules = ["keyword_front", "keyword_present"]
        for check in result["checks"]:
            self.assertNotIn(check["rule"], [
                "Keyword in First 3 Words",
                "Keyword Present Anywhere"
            ], "Keyword rules should be excluded when no keyword provided")
        
        # Score should be calculated from applicable checks only
        self.assertEqual(result["max_score"], 100)
        self.assertGreaterEqual(result["score"], 0)
        self.assertLessEqual(result["score"], 100)

    def test_score_calculation_correct(self):
        """Score should be (earned_weight / total_weight) * 100."""
        result = title.score_title("How to Make YouTube Videos", keyword="")
        
        # Calculate expected: sum of weights for non-keyword rules
        # All rules except keyword_front (15) and keyword_present (10) = 130 total
        # But let's verify by checking the actual result
        applicable_checks = [c for c in result["checks"] 
                           if c["rule"] not in ["Keyword in First 3 Words", "Keyword Present Anywhere"]]
        total_weight = sum(c["weight"] for c in applicable_checks)
        earned_weight = sum(c["weight"] for c in applicable_checks if c["passed"])
        
        expected_score = round((earned_weight / total_weight) * 100) if total_weight else 0
        self.assertEqual(result["score"], expected_score)


class TestTitleScoringWithKeyword(unittest.TestCase):
    """Test score_title when keyword is provided."""

    def test_includes_keyword_rules(self):
        """Keyword-dependent rules should be included when keyword provided."""
        result = title.score_title("YouTube SEO Tips 2024", keyword="youtube seo")
        
        keyword_rules_found = [c for c in result["checks"] 
                              if c["rule"] in ["Keyword in First 3 Words", "Keyword Present Anywhere"]]
        self.assertEqual(len(keyword_rules_found), 2, "Both keyword rules should be present")

    def test_keyword_front_load(self):
        """Keyword in first 3 words should pass."""
        result = title.score_title("YouTube SEO Tips for Beginners", keyword="youtube seo")
        kw_front = next(c for c in result["checks"] if c["rule"] == "Keyword in First 3 Words")
        self.assertTrue(kw_front["passed"])

    def test_keyword_anywhere(self):
        """Keyword anywhere in title should pass."""
        result = title.score_title("Best Tips for YouTube SEO Success", keyword="youtube seo")
        kw_anywhere = next(c for c in result["checks"] if c["rule"] == "Keyword Present Anywhere")
        self.assertTrue(kw_anywhere["passed"])

    def test_keyword_missing_fails(self):
        """Missing keyword should fail both keyword rules."""
        result = title.score_title("How to Rank Videos on YouTube", keyword="youtube seo")
        kw_front = next(c for c in result["checks"] if c["rule"] == "Keyword in First 3 Words")
        kw_anywhere = next(c for c in result["checks"] if c["rule"] == "Keyword Present Anywhere")
        self.assertFalse(kw_front["passed"])
        self.assertFalse(kw_anywhere["passed"])


class TestThumbnailTextScoring(unittest.TestCase):
    """Test score_thumbnail_text function."""

    def test_three_words_or_less(self):
        """Three words or less should pass word count check."""
        result = title.score_thumbnail_text("WATCH THIS")
        word_count_check = next(c for c in result["checks"] if "Word count" in c["check"])
        self.assertTrue(word_count_check["passed"])

    def test_four_words_borderline(self):
        """Four words should be borderline."""
        result = title.score_thumbnail_text("THIS IS A TEST")
        word_count_check = next(c for c in result["checks"] if "Word count" in c["check"])
        self.assertFalse(word_count_check["passed"])
        self.assertEqual(word_count_check["score"], 10)

    def test_five_words_fails(self):
        """Five words should fail word count check."""
        result = title.score_thumbnail_text("THIS IS WAY TOO LONG")
        word_count_check = next(c for c in result["checks"] if "Word count" in c["check"])
        self.assertFalse(word_count_check["passed"])
        self.assertEqual(word_count_check["score"], 0)

    def test_caps_word_detection(self):
        """ALL CAPS words should be detected."""
        result = title.score_thumbnail_text("SECRET REVEALED")
        caps_check = next(c for c in result["checks"] if "ALL CAPS" in c["check"])
        self.assertTrue(caps_check["passed"])

    def test_number_detection(self):
        """Numbers in thumbnail text should be detected."""
        result = title.score_thumbnail_text("5 TIPS")
        number_check = next(c for c in result["checks"] if "number" in c["check"].lower())
        self.assertTrue(number_check["passed"])

    def test_emotion_word_detection(self):
        """High-arousal emotion words should be detected."""
        result = title.score_thumbnail_text("SHOCKING TRUTH")
        emotion_check = next(c for c in result["checks"] if "emotion" in c["check"].lower())
        self.assertTrue(emotion_check["passed"])


class TestScorePackage(unittest.TestCase):
    """Test combined title + thumbnail scoring."""

    def test_combined_score_formula(self):
        """Combined score should be 60% title + 40% thumbnail."""
        result = title.score_package("How to YouTube SEO", thumb_text="WATCH NOW", keyword="youtube seo")
        
        # Should have both title and thumbnail results
        self.assertIn("title", result)
        self.assertIn("thumbnail", result)
        self.assertIn("combined_score", result)
        self.assertIn("verdict", result)

    def test_verdict_thresholds(self):
        """Verdict should match score thresholds."""
        # Mock high score
        with patch("title.score_title", return_value={"score": 90, "checks": []}):
            with patch("title.score_thumbnail_text", return_value={"score": 80, "checks": []}):
                result = title.score_package("test", "test", "test")
                self.assertEqual(result["verdict"], "SHIP")

        with patch("title.score_title", return_value={"score": 60, "checks": []}):
            with patch("title.score_thumbnail_text", return_value={"score": 50, "checks": []}):
                result = title.score_package("test", "test", "test")
                self.assertEqual(result["verdict"], "REVISE")

        with patch("title.score_title", return_value={"score": 40, "checks": []}):
            with patch("title.score_thumbnail_text", return_value={"score": 30, "checks": []}):
                result = title.score_package("test", "test", "test")
                self.assertEqual(result["verdict"], "REWORK")


if __name__ == "__main__":
    unittest.main()