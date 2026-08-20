#!/usr/bin/env python3
"""Validate assignment Markdown and render it to PDF with Pandoc.

Usage
-----
    python d2l/generate_assignments.py d2l/assignments/hw01.md
    python d2l/generate_assignments.py d2l/assignments/hw*.md --check

The script does not connect to D2L. It checks the student-facing Markdown and,
unless ``--check`` is supplied, renders each document to a PDF in
``d2l/build/assignments/``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = Path(__file__).parent / "build" / "assignments"


def pandoc_command() -> list[str] | None:
    """Return a command prefix for Pandoc, using Quarto as a fallback."""
    if shutil.which("pandoc"):
        return ["pandoc"]
    if shutil.which("quarto"):
        return ["quarto", "pandoc"]
    return None


def assignment_title(text: str) -> str | None:
    """Return the first ATX heading, which is the document title."""
    match = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return match.group(1) if match else None


def validate(path: Path) -> tuple[str | None, list[str]]:
    """Return the title and any problems found in an assignment source."""
    problems: list[str] = []

    if not path.exists():
        return None, [f"assignment source does not exist: {path}"]
    if path.suffix.lower() != ".md":
        problems.append("assignment source must use the `.md` extension")

    text = path.read_text(encoding="utf-8")
    if not text.strip():
        problems.append("assignment source is empty")
        return None, problems

    title = assignment_title(text)
    if title is None:
        problems.append("source must begin with a level-one Markdown title")

    if "blank Jupyter notebook" not in text:
        problems.append("source must tell students to create a blank notebook")
    if re.search(r"starter (cell|notebook|headings|scaffold)", text, re.I):
        problems.append("source still refers to starter material")

    return title, problems


def build(path: Path, check_only: bool) -> bool:
    """Validate one Markdown source and optionally render its PDF."""
    source = path.expanduser().resolve()
    title, problems = validate(source)
    label = title or source.stem

    if problems:
        print(f"[!] {label} ({source.name}) — {len(problems)} issue(s):")
        for problem in problems:
            print(f"    {problem}")
        return False

    if check_only:
        print(f"[ok] {label} ({source.name})")
        return True

    pandoc = pandoc_command()
    if pandoc is None:
        print(
            "Pandoc or Quarto is required to generate assignment PDFs.",
            file=sys.stderr,
        )
        return False

    OUTDIR.mkdir(parents=True, exist_ok=True)
    output = OUTDIR / f"{source.stem}.pdf"
    command = pandoc + [
        str(source),
        "--from=markdown+tex_math_dollars",
        "--to=pdf",
        "--standalone",
        "--pdf-engine=xelatex",
        "--variable=geometry:margin=1in",
        f"--output={output}",
    ]

    try:
        subprocess.run(command, check=True, cwd=ROOT)
    except subprocess.CalledProcessError as exc:
        print(f"[!] Pandoc failed for {source.name} (exit {exc.returncode})")
        return False

    print(f"[ok] {label} ({source.name}) -> {output}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("markdown_files", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    clean = True
    for path in args.markdown_files:
        clean = build(path, args.check) and clean
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
