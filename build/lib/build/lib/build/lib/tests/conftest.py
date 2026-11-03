#!/usr/bin/env python3
"""
Regression test suite for YouTube Skillbox.

Run with: python -m pytest tests/ -v
Or: python -m unittest discover tests/
"""

import sys
import os

# Add repo root to path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, "skills", "youtube", "scripts"))
sys.path.insert(0, os.path.join(repo_root, "skills", "yt-package", "scripts"))
sys.path.insert(0, os.path.join(repo_root, "skills", "yt-retention", "scripts"))
sys.path.insert(0, os.path.join(repo_root, "skills", "yt-viral", "scripts"))