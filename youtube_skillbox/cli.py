#!/usr/bin/env python3
"""
YouTube Skillbox - CLI entry point.
"""
import sys
import os

# Add the skills/youtube/scripts directory to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.dirname(script_dir)
skills_dir = os.path.join(repo_root, "skills", "youtube", "scripts")
sys.path.insert(0, skills_dir)

# Import and run main
from ytdata import main

if __name__ == "__main__":
    main()