#!/usr/bin/env python3
"""
YouTube Skillbox - CLI entry point.
"""
import os
import sys
import sysconfig


def get_version():
    """Return the installed distribution version when available."""
    try:
        from importlib.metadata import version
        return version("youtube-skillbox")
    except Exception:
        return "unknown"


def find_skills_dir():
    """Locate ytdata.py in an installed wheel or a source checkout."""
    candidates = []

    # Wheels install the standalone engine under the interpreter's data prefix.
    data_prefix = sysconfig.get_path("data")
    if data_prefix:
        candidates.append(
            os.path.join(
                data_prefix, "share", "youtube-skillbox", "skills",
                "youtube", "scripts"
            )
        )

    # Editable installs and source checkouts keep skills/ at the repository root.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    candidates.append(os.path.join(repo_root, "skills", "youtube", "scripts"))

    for skills_dir in candidates:
        if os.path.isfile(os.path.join(skills_dir, "ytdata.py")):
            return skills_dir

    raise RuntimeError(
        "Could not locate ytdata.py. Reinstall youtube-skillbox or run from "
        "a complete source checkout."
    )


def main():
    if "--version" in sys.argv or "-v" in sys.argv:
        print(f"ytdata {get_version()}")
        return

    skills_dir = find_skills_dir()
    sys.path.insert(0, skills_dir)

    from ytdata import main as ytdata_main
    ytdata_main()


if __name__ == "__main__":
    main()