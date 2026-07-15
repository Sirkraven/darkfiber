#!/usr/bin/env python3
"""Pre-publication audit: run this before the first push to a public remote.

Checks (per PLAN_V_5_1_2.md, Block D4):
  1. No absolute local filesystem paths leaked into tracked files.
  2. No obvious credentials/tokens/API keys.
  3. No unwanted personal emails (only the ones in CITATION.cff/pyproject.toml
     are expected).
  4. No data files (.h5/.npz/.sgy/.db) tracked by git.
  5. Total repo size under a sane threshold.

Exits non-zero (and prints exactly what to fix) if anything looks wrong.
Doesn't touch git history — read-only over the current working tree plus
`git ls-files` for what's actually tracked.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_TOTAL_MB = 50

ALLOWED_EMAILS = {"Sirkraven@users.noreply.github.com"}

# Windows and POSIX absolute-path patterns. Deliberately conservative: a
# false positive here just means "look at this line", not "fail the build".
ABS_PATH_PATTERNS = [
    re.compile(r"[A-Za-z]:\\Users\\[^\\]+"),
    re.compile(r"/home/[^/\s]+"),
    re.compile(r"/Users/[^/\s]+"),
    re.compile(r"C:/Users/[^/\s]+"),
]

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key
    re.compile(r"ghp_[A-Za-z0-9]{36}"),  # GitHub PAT
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # generic API-key-shaped secret
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

DATA_EXTENSIONS = {".h5", ".hdf5", ".npz", ".npy", ".sgy", ".segy", ".db", ".sqlite", ".sqlite3"}


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("WARN: not a git repo yet (or git not on PATH) — scanning the working tree instead.")
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]
    return [ROOT / line for line in out.stdout.splitlines() if line]


def check_data_files(files: list[Path]) -> list[str]:
    problems = []
    for f in files:
        if f.suffix.lower() in DATA_EXTENSIONS:
            problems.append(f"data file tracked: {f.relative_to(ROOT)}")
    return problems


def check_text_content(files: list[Path]) -> list[str]:
    problems = []
    for f in files:
        if f.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".ico"}:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        rel = f.relative_to(ROOT)
        # Este mismo script define los patrones como texto — se excluye del
        # chequeo de rutas absolutas para no matchear su propia definición.
        if str(rel).replace("\\", "/") != "scripts/pre_publish_audit.py":
            for pat in ABS_PATH_PATTERNS:
                if pat.search(text):
                    problems.append(f"possible absolute local path in {rel}")
                    break
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                problems.append(f"possible credential/secret in {rel}")
                break
        for m in EMAIL_PATTERN.finditer(text):
            if m.group(0) not in ALLOWED_EMAILS and str(rel) not in {
                "CITATION.cff",
                "pyproject.toml",
                "scripts/pre_publish_audit.py",
            }:
                problems.append(f"unexpected email '{m.group(0)}' in {rel}")
    return problems


def check_total_size(files: list[Path]) -> list[str]:
    total_mb = sum(f.stat().st_size for f in files if f.exists()) / (1024 * 1024)
    if total_mb > MAX_TOTAL_MB:
        return [f"tracked content is {total_mb:.1f} MB, over the {MAX_TOTAL_MB} MB budget"]
    return []


def main() -> int:
    files = tracked_files()
    problems: list[str] = []
    problems += check_data_files(files)
    problems += check_text_content(files)
    problems += check_total_size(files)

    if problems:
        print(f"Pre-publish audit: {len(problems)} issue(s) found\n")
        for p in problems:
            print(f"  - {p}")
        print("\nFix these before pushing to a public remote.")
        return 1

    print(f"Pre-publish audit: clean ({len(files)} tracked files checked).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
