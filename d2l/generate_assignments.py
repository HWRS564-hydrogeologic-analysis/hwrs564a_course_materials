#!/usr/bin/env python3
"""Validate D2L assignment settings and build HTML instructions from Markdown.

Usage
-----
    python d2l/generate_assignments.py d2l/assignments/hw01.yml
    python d2l/generate_assignments.py d2l/assignments/*.yml --check

The script does not connect to D2L. It generates the HTML that is pasted into
an Assignment's Instructions field and validates the settings entered manually.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = Path(__file__).with_name("assignment_template.html")
OUTDIR = Path(__file__).parent / "build" / "assignments"

REQUIRED_D2L = {
    "category",
    "grade_item",
    "score_out_of",
    "assignment_type",
    "submission_type",
    "allowed_extensions",
    "files_per_submission",
    "attempts",
    "attempt_to_grade",
    "timezone",
    "available_from",
    "due",
}


def validate(path: Path) -> tuple[dict, Path, list[str]]:
    spec = yaml.safe_load(path.read_text(encoding="utf-8"))
    problems: list[str] = []

    for key in ("assignment", "title", "source", "output", "d2l",
                "student_submission", "rubric"):
        if key not in spec:
            problems.append(f"missing `{key}`")

    source = ROOT / str(spec.get("source", "missing"))
    if not source.exists():
        problems.append(f"source does not exist: {source}")
        text = ""
    else:
        text = source.read_text(encoding="utf-8")

    d2l = spec.get("d2l") or {}
    for key in sorted(REQUIRED_D2L - set(d2l)):
        problems.append(f"d2l: missing `{key}`")

    score = d2l.get("score_out_of")
    criteria = (spec.get("rubric") or {}).get("criteria") or []
    criterion_total = sum(item.get("points", 0) for item in criteria)
    if score is not None and criterion_total != score:
        problems.append(
            f"rubric criteria total {criterion_total}, expected {score}"
        )

    submission = spec.get("student_submission") or {}
    if submission.get("starter_notebook") is not False:
        problems.append("student_submission: `starter_notebook` must be false")
    if d2l.get("allowed_extensions") != [".ipynb"]:
        problems.append("d2l: allowed_extensions must be exactly ['.ipynb']")

    if text:
        if "blank Jupyter notebook" not in text:
            problems.append("source must tell students to create a blank notebook")
        if re.search(r"starter (cell|notebook|headings|scaffold)", text, re.I):
            problems.append("source still refers to starter material")
        total_match = re.search(
            r"\|\s*\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|", text
        )
        if not total_match:
            problems.append("could not find rubric total in source Markdown")
        elif score is not None and int(total_match.group(1)) != score:
            problems.append(
                f"source rubric total {total_match.group(1)}, expected {score}"
            )

    for resource in spec.get("resources") or []:
        if not (ROOT / resource).exists():
            problems.append(f"resource does not exist: {resource}")

    return spec, source, problems


def pandoc_command() -> list[str] | None:
    if shutil.which("pandoc"):
        return ["pandoc"]
    if shutil.which("quarto"):
        return ["quarto", "pandoc"]
    return None


def build(path: Path, check_only: bool) -> bool:
    spec, source, problems = validate(path)
    label = f"HW {spec.get('assignment', '?')}"

    if problems:
        print(f"[!] {label} ({path.name}) — {len(problems)} issue(s):")
        for problem in problems:
            print(f"    {problem}")
        return False

    if check_only:
        print(f"[ok] {label} ({path.name})")
        return True

    pandoc = pandoc_command()
    if pandoc is None:
        print("pandoc or quarto is required to generate assignment HTML", file=sys.stderr)
        return False

    OUTDIR.mkdir(parents=True, exist_ok=True)
    output = OUTDIR / spec["output"]
    command = pandoc + [
        str(source),
        "--from=gfm+tex_math_dollars",
        "--to=html5",
        "--standalone",
        "--mathml",
        f"--metadata=title:{spec['title']}",
        f"--template={TEMPLATE}",
        f"--output={output}",
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    print(f"[ok] {label} ({path.name}) -> {output}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("yaml_files", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    clean = True
    for path in args.yaml_files:
        clean = build(path, args.check) and clean
    return 0 if clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
