#!/usr/bin/env python3
"""Prepare a release: bump version strings and stamp the CHANGELOG.

Usage:  python scripts/release.py 0.2.0

Does three things, all local (review the diff before committing):
  1. backend/app/main.py       version="..."
  2. frontend/package.json     "version": "..."
  3. CHANGELOG.md              "## [Unreleased]" -> "## [x.y.z] - <today>"
                               (a fresh Unreleased heading is added above)

Then: commit, tag `vX.Y.Z`, push the tag — the Release workflow drafts the
GitHub Release from the CHANGELOG section automatically.
"""

from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def fail(msg: str) -> None:
    sys.exit(f"error: {msg}")


def bump_backend(version: str) -> None:
    path = ROOT / "backend" / "app" / "main.py"
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(r'version="[^"]+"', f'version="{version}"', text, count=1)
    if n != 1:
        fail(f'could not find version="..." in {path}')
    path.write_text(new, encoding="utf-8")


def bump_frontend(version: str) -> None:
    path = ROOT / "frontend" / "package.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def stamp_changelog(version: str) -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    if f"## [{version}]" in text:
        fail(f"CHANGELOG.md already has a section for {version}")
    if "## [Unreleased]" not in text:
        fail("CHANGELOG.md has no [Unreleased] section to stamp")
    today = datetime.date.today().isoformat()
    text = text.replace(
        "## [Unreleased]",
        f"## [Unreleased]\n\nNothing yet.\n\n## [{version}] - {today}",
        1,
    )
    path.write_text(text, encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+", sys.argv[1]):
        fail("usage: python scripts/release.py X.Y.Z")
    version = sys.argv[1]
    bump_backend(version)
    bump_frontend(version)
    stamp_changelog(version)
    print(f"Prepared {version}. Next steps:")
    print("  1. Review the diff (versions + CHANGELOG stamp).")
    print(f'  2. git commit -am "Release v{version}"')
    print(f"  3. git tag -a v{version} -m \"Blackline v{version}\"")
    print(f"  4. git push && git push origin v{version}")
    print("  5. The Release workflow drafts the GitHub Release — review and publish.")


if __name__ == "__main__":
    main()
