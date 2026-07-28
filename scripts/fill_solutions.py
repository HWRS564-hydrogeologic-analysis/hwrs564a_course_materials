#!/usr/bin/env python3
"""Generate the filled-in copy of a lab notebook from its `solutions:` metadata.

Why this exists: keeping a hand-maintained `_solutions.ipynb` alongside every
lab means two files that must be edited together, and they drift within about
three weeks. Instead the answers live in the notebook's own metadata and the
released copy is *generated*, so it cannot disagree with the student version.

The generated copy is also what `pytest --nbmake` runs — the student version is
full of `...` placeholders and is not supposed to execute.

Usage:
    python scripts/fill_solutions.py labs/week02/week02_lab_python_basics.ipynb
    python scripts/fill_solutions.py labs/**/*.ipynb --check   # validate only

Output:
    labs/weekNN/_solutions/<same name>.ipynb      (gitignored)

How a notebook declares its answers
-----------------------------------
In the notebook's *notebook-level* metadata (Edit → Notebook Metadata in
Jupyter, or `nb["metadata"]` in the JSON):

    "solutions": {
        "1": "well_id = \\"A-14\\"\\nscreen_top = 44.5",
        "2": "total_depth = float(depth_text) + 12.0"
    }

Keys are the exercise number, in document order, matching the `### YOUR TURN N`
headings. Values replace the block after the `# YOUR TURN` marker line — so any
givens written above the marker survive, and so does anything after the block at
a shallower indent (a trailing `return`, for instance).

Write answers flush-left; they are re-indented to the marker's level.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import textwrap
from pathlib import Path

MARKER = "# YOUR TURN"
SOLUTIONS_KEY = "solutions"


def is_your_turn(cell: dict) -> bool:
    if cell.get("cell_type") != "code":
        return False
    return any(line.strip().startswith(MARKER) for line in cell.get("source", []))


def split_at_marker(source: list[str]) -> tuple[list[str], str, list[str]]:
    """Split a YOUR TURN cell into (head, indent, tail).

    `head` is everything up to and including the marker line. The replaceable
    region is the run of lines after it indented at least as deeply as the
    marker; `tail` is whatever follows at a shallower indent.

    That rule is what lets an exercise sit inside a loop:

        for n in range(n_steps):
            # YOUR TURN
            S[n + 1] = ...        <- replaced
        return S                  <- kept

    Without it, the `return` would be swallowed by the answer and every
    exercise would have to be the last thing in its cell.
    """
    for i, line in enumerate(source):
        if not line.strip().startswith(MARKER):
            continue
        indent = line[: len(line) - len(line.lstrip())]
        j = i + 1
        while j < len(source):
            stripped = source[j].strip()
            if stripped and not source[j].startswith(indent):
                break
            j += 1
        return source[: i + 1], indent, source[j:]
    raise AssertionError("called on a cell with no marker")


def reindent(text: str, indent: str) -> list[str]:
    """Dedent the author's answer, then re-indent it to the marker's level.

    Answers are written flush-left in the `solutions:` block so they read like
    ordinary code; this puts them back where they belong in the cell.
    """
    lines = textwrap.dedent(text).rstrip("\n").split("\n")
    return [(indent + line if line.strip() else "") + "\n" for line in lines]


def fill(path: Path, check_only: bool) -> list[str]:
    problems: list[str] = []
    nb = json.loads(path.read_text())
    solutions = nb.get("metadata", {}).get(SOLUTIONS_KEY)

    turns = [i for i, c in enumerate(nb["cells"]) if is_your_turn(c)]

    if solutions is None:
        if turns:
            problems.append(
                f"{len(turns)} `{MARKER}` cell(s) but no `solutions:` block in the "
                "notebook metadata — nothing to generate, and nbmake has nothing "
                "runnable to test"
            )
        return report(path, problems, 0)

    if not isinstance(solutions, dict):
        problems.append("notebook metadata `solutions` must be a mapping of number -> code")
        return report(path, problems, 0)

    # ---- the two directions of drift this script exists to catch -------------
    expected = {str(n) for n in range(1, len(turns) + 1)}
    provided = set(map(str, solutions))
    for missing in sorted(expected - provided, key=int):
        line = turns[int(missing) - 1]
        problems.append(f"cell {line}: YOUR TURN {missing} has no entry in `solutions`")
    for extra in sorted(provided - expected):
        problems.append(
            f"`solutions` has an entry for exercise {extra}, but the notebook only "
            f"has {len(turns)} YOUR TURN cell(s)"
        )

    # The playbook asks for 3-6 exercises per lab; flag rather than fail.
    if turns and not 3 <= len(turns) <= 6:
        problems.append(
            f"note: {len(turns)} YOUR TURN cells — the playbook targets 3-6 "
            "(fewer and students coast, more and nobody finishes)"
        )

    if problems or check_only:
        return report(path, problems, len(turns))

    # ---- build the filled copy ----------------------------------------------
    out_nb = copy.deepcopy(nb)
    out_nb["metadata"].pop(SOLUTIONS_KEY, None)

    for n, idx in enumerate(turns, start=1):
        cell = out_nb["cells"][idx]
        head, indent, tail = split_at_marker(cell["source"])
        head[-1] = head[-1].rstrip("\n").replace(MARKER, "# SOLUTION") + "\n"
        cell["source"] = head + reindent(solutions[str(n)], indent) + tail
        if cell["source"]:
            cell["source"][-1] = cell["source"][-1].rstrip("\n")
        cell["outputs"] = []
        cell["execution_count"] = None

    for cell in out_nb["cells"]:
        if cell.get("cell_type") == "code":
            cell["outputs"] = []
            cell["execution_count"] = None

    leftover = [
        n
        for n, idx in enumerate(turns, start=1)
        if "= ..." in "".join(out_nb["cells"][idx]["source"])
    ]
    if leftover:
        problems.append(
            f"exercise(s) {leftover} still contain `= ...` after filling — the "
            "solution text probably doesn't cover every blank"
        )
        return report(path, problems, len(turns))

    out_dir = path.parent / "_solutions"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / path.name
    out_path.write_text(json.dumps(out_nb, indent=1, ensure_ascii=False) + "\n")
    print(f"[ok] {path} -> {out_path}  ({len(turns)} exercises filled)")
    return []


def report(path: Path, problems: list[str], n_turns: int) -> list[str]:
    flag = "!" if problems else "ok"
    print(f"[{flag}] {path} — {n_turns} YOUR TURN cell(s)")
    for p in problems:
        print(f"      {p}")
    # "note:" lines are advisory and must not fail the build.
    return [p for p in problems if not p.startswith("note:")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument(
        "--check",
        action="store_true",
        help="validate the solutions metadata without writing anything",
    )
    args = ap.parse_args()

    total = 0
    for path in args.files:
        if "_solutions" in path.parts:
            continue  # don't recurse over our own output
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            total += 1
            continue
        total += len(fill(path, args.check))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
