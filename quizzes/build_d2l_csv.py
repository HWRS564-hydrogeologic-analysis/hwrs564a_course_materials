#!/usr/bin/env python3
"""Convert a quiz YAML file into a D2L Brightspace question-import CSV.

Usage
-----
    python quizzes/build_d2l_csv.py quizzes/week03.yml
    python quizzes/build_d2l_csv.py quizzes/*.yml -o build/

Importing into D2L
------------------
1. Course → Quizzes → (new or existing quiz) → Add/Edit Questions
2. Import → Upload a File → drop the generated .csv
3. Review the imported questions, then save

The CSV is written UTF-8 with a BOM, which is what D2L's importer expects for
non-ASCII characters (en dashes, ≥, Greek letters).

Supported question types
------------------------
    mc  multiple choice (one correct answer)
    ms  multiselect (several correct answers)
    tf  true/false
    sa  short answer
    wr  written response

Notes on the D2L format
-----------------------
Each question is a block of rows. Column 1 is a field name; the meaning of the
remaining columns depends on the field. HTML is opt-in: you put the literal
string "HTML" in the column immediately after any text column that contains
markup. This script handles that flag for you.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required:  uv add pyyaml   (or)   pip install pyyaml")


# --------------------------------------------------------------------------
# text handling
# --------------------------------------------------------------------------

_BACKTICK = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
# Single-asterisk italics. Must run *after* bold or it would eat the markers.
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")


def render(text: str) -> tuple[str, bool]:
    """Convert light markdown to HTML.

    Returns ``(text, is_html)``. ``is_html`` is True when the result contains
    markup, in which case the caller must emit the "HTML" flag in the next
    column or D2L will show the tags literally.
    """
    if text is None:
        return "", False

    text = str(text).strip()
    had_markup = "<" in text and ">" in text  # author wrote raw HTML

    text, n_code = _BACKTICK.subn(r"<code>\1</code>", text)
    text, n_bold = _BOLD.subn(r"<strong>\1</strong>", text)
    text, n_ital = _ITALIC.subn(r"<em>\1</em>", text)

    is_html = bool(n_code or n_bold or n_ital or had_markup)

    # A <pre> block or explicit markup means newlines are already meaningful.
    # Otherwise collapse hard-wrapped YAML into flowing text.
    if not had_markup:
        text = re.sub(r"\s*\n\s*", " ", text).strip()

    return text, is_html


def text_cells(value: str) -> list[str]:
    """Return ``[text, "HTML" or ""]`` for a text field and its flag column."""
    body, is_html = render(value)
    return [body, "HTML" if is_html else ""]


# --------------------------------------------------------------------------
# per-type row builders
# --------------------------------------------------------------------------


def common_rows(q: dict, default_points: int) -> list[list[str]]:
    """Rows shared by every question type, in the order D2L expects."""
    rows: list[list[str]] = [
        ["NewQuestion", q["type"].upper()],
        ["ID", ""],
        # Title must be plain text — D2L ignores HTML here.
        ["Title", render(q.get("title", ""))[0]],
        ["QuestionText", *text_cells(q.get("text", ""))],
        ["Points", str(q.get("points", default_points))],
        ["Difficulty", str(q.get("difficulty", 1))],
        ["Image", q.get("image", "")],
    ]
    if q.get("hint"):
        rows.append(["Hint", *text_cells(q["hint"])])
    if q.get("feedback"):
        rows.append(["Feedback", *text_cells(q["feedback"])])
    return rows


def build_mc(q: dict) -> list[list[str]]:
    """Multiple choice. Option column 2 is a *percentage* of the points."""
    rows = []
    n_correct = sum(1 for o in q["options"] if o.get("correct"))
    if n_correct != 1:
        raise ValueError(
            f"mc question {q.get('title')!r} has {n_correct} correct options; "
            "exactly 1 is required (use type: ms for multiple answers)"
        )
    for opt in q["options"]:
        weight = "100" if opt.get("correct") else "0"
        rows.append(["Option", weight, *text_cells(opt["text"]),
                     *text_cells(opt.get("feedback", ""))])
    return rows


def build_ms(q: dict) -> list[list[str]]:
    """Multiselect. Option column 2 is 1 or 0, not a percentage."""
    rows = [["Scoring", q.get("scoring", "RightAnswers")]]
    if not any(o.get("correct") for o in q["options"]):
        raise ValueError(f"ms question {q.get('title')!r} has no correct options")
    for opt in q["options"]:
        flag = "1" if opt.get("correct") else "0"
        rows.append(["Option", flag, *text_cells(opt["text"]),
                     *text_cells(opt.get("feedback", ""))])
    return rows


def build_tf(q: dict) -> list[list[str]]:
    """True/False. Each row carries the weight and the feedback for that choice."""
    if "answer" not in q:
        raise ValueError(f"tf question {q.get('title')!r} needs an `answer:` key")
    answer = bool(q["answer"])
    return [
        ["True", "100" if answer else "0", *text_cells(q.get("true_feedback", ""))],
        ["False", "0" if answer else "100", *text_cells(q.get("false_feedback", ""))],
    ]


def build_sa(q: dict) -> list[list[str]]:
    """Short answer. Correct answers must be plain text — no HTML."""
    rows = [["InputBox", str(q.get("input_rows", 1)), str(q.get("input_width", 40))]]
    answers = q.get("answers") or ([q["answer"]] if "answer" in q else [])
    if not answers:
        raise ValueError(f"sa question {q.get('title')!r} needs `answers:`")
    # D2L uses only the option from the LAST Answer row, so every row gets the
    # same case-sensitivity value.
    sensitivity = q.get("case_sensitivity", "insensitive")
    for ans in answers:
        rows.append(["Answer", "", str(ans), sensitivity])
    return rows


def build_wr(q: dict) -> list[list[str]]:
    rows = []
    if q.get("initial_text"):
        rows.append(["InitialText", *text_cells(q["initial_text"])])
    if q.get("answer_key"):
        rows.append(["AnswerKey", *text_cells(q["answer_key"])])
    return rows


BUILDERS = {"mc": build_mc, "ms": build_ms, "tf": build_tf,
            "sa": build_sa, "wr": build_wr}


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def convert(path: Path, outdir: Path | None = None) -> Path:
    spec = yaml.safe_load(path.read_text())
    meta = spec.get("quiz", {})
    questions = spec.get("questions") or []
    if not questions:
        raise ValueError(f"{path}: no questions found")

    default_points = meta.get("default_points", 1)
    rows: list[list[str]] = []

    for i, q in enumerate(questions, start=1):
        qtype = str(q.get("type", "")).lower()
        if qtype not in BUILDERS:
            raise ValueError(
                f"{path}: question {i} has unsupported type {qtype!r}. "
                f"Supported: {', '.join(sorted(BUILDERS))}"
            )
        try:
            rows.extend(common_rows({**q, "type": qtype}, default_points))
            rows.extend(BUILDERS[qtype](q))
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{path}: question {i} ({q.get('title')!r}): {exc}") from exc
        rows.append([])  # blank row separates questions

    outdir = outdir or path.parent / "build"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / f"{path.stem}_d2l_import.csv"

    # utf-8-sig: D2L wants the BOM to read non-ASCII correctly.
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        csv.writer(fh).writerows(rows)

    counts: dict[str, int] = {}
    for q in questions:
        counts[q["type"]] = counts.get(q["type"], 0) + 1
    breakdown = ", ".join(f"{n}×{t}" for t, n in sorted(counts.items()))
    total = sum(q.get("points", default_points) for q in questions)

    print(f"{out}")
    print(f"  {meta.get('title', path.stem)} — {meta.get('covers', '')}")
    print(f"  {len(questions)} questions ({breakdown}), {total} points total")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("yaml_files", nargs="+", type=Path)
    ap.add_argument("-o", "--outdir", type=Path, default=None,
                    help="output directory (default: <yaml dir>/build)")
    args = ap.parse_args()

    failed = 0
    for path in args.yaml_files:
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            failed += 1
            continue
        try:
            convert(path, args.outdir)
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
