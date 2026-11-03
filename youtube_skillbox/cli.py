#!/usr/bin/env python3
"""
YouTube Skillbox - CLI entry point.
"""
import sys
import os
import importlib.util

# Find the skills directory from the installed package
def find_skills_dir():
    """Find the skills/youtube/scripts directory from the installed package."""
    try:
        import youtube_skillbox
        pkg_path = os.path.dirname(youtube_skillbox.__file__)
        skills_dir = os.path.join(pkg_path, "skills", "youtube", "scripts")
        if os.path.isdir(skills_dir):
            return skills_dir
    except ImportError:
        pass
    # Fallback: try relative to this file (editable install from source)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    skills_dir = os.path.join(repo_root, "skills", "youtube", "scripts")
    if os.path.isdir(skills_dir):
        return skills_dir
    raise RuntimeError("Could not locate skills/youtube/scripts directory")

skills_dir = find_skills_dir()
sys.path.insert(0, skills_dir)

# Import and run main
from ytdata import main

if __name__ == "__main__":
    main()