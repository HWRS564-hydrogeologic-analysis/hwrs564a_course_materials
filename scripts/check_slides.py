#!/usr/bin/env python3
"""Static checks on Quarto slide decks.

Catches the quarto-live mistakes that are easy to make and annoying to find by
eye: an exercise with a hint that points at nothing, a blank written with too
few underscores, an unbalanced fenced div.

Usage:
    python scripts/check_slides.py slides/*.qmd
    python scripts/check_slides.py slides/*.qmd --quiet   # only report problems
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required:  uv add pyyaml")

FENCE = re.compile(r"^\s*```+\s*\{?([a-zA-Z0-9_-]*)\}?")
CELL_OPT = re.compile(r"^\s*#\|\s*([a-zA-Z0-9_-]+)\s*:\s*(.*)$")
DIV_OPEN = re.compile(r"^\s*(:::+)\s*\{([^}]*)\}\s*$")
DIV_BARE = re.compile(r"^\s*(:::+)\s*$")
DIV_ATTR_EX = re.compile(r'exercise\s*=\s*"([^"]+)"')
# A blank is a standalone run of underscores. The negative lookarounds keep
# dunder names like __name__ and identifiers like my_var from matching.
BLANK_RUN = re.compile(r"(?<![A-Za-z0-9_])_{2,}(?![A-Za-z0-9_])")

# quarto-live cell options, from
# https://r-wasm.github.io/quarto-live/reference/cell-options.html
KNOWN_OPTS = {
    "autorun", "caption", "canvas", "completion", "echo", "edit", "envir",
    "error", "eval", "fig-width", "fig-height", "fig-dpi", "include", "persist",
    "output", "runbutton", "startover", "timelimit", "warning", "min-lines",
    "max-lines", "check", "exercise", "hint", "setup", "solution",
    # standard quarto options that are still valid inside a cell
    "label", "classes", "code-fold", "code-line-numbers",
}


def check(path: Path, quiet: bool) -> list[str]:
    text = path.read_text()
    lines = text.splitlines()
    problems: list[str] = []

    # ---- front matter -----------------------------------------------------
    if not lines or lines[0].strip() != "---":
        problems.append("line 1: no YAML front matter")
    else:
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is None:
            problems.append("front matter is never closed")
        else:
            try:
                fm = yaml.safe_load("\n".join(lines[1:end])) or {}
                if not fm.get("title"):
                    problems.append("front matter: no `title`")
            except yaml.YAMLError as exc:
                problems.append(f"front matter is not valid YAML: {exc}")

    # ---- walk the file ----------------------------------------------------
    exercises: dict[str, int] = {}        # label -> line of the exercise cell
    setups: dict[str, list[int]] = {}     # label -> lines of setup cells
    referenced: list[tuple[str, int, str]] = []   # label, line, kind
    div_stack: list[tuple[str, int]] = []
    in_fence = False
    fence_lang = ""
    fence_start = 0
    cell_opts: dict[str, str] = {}
    cell_body: list[str] = []
    n_slides = 1                          # the title slide, from the front matter
    n_sections = 0                        # H1 section breaks, which cost no time

    def close_cell():
        """Validate one just-finished code cell."""
        nonlocal cell_opts, cell_body
        if fence_lang in {"pyodide", "webr"}:
            label = cell_opts.get("exercise")
            is_setup = str(cell_opts.get("setup", "")).lower() in {"true", "yes"}
            if label:
                label = label.strip().strip("\"'")
                if is_setup:
                    setups.setdefault(label, []).append(fence_start)
                else:
                    if label in exercises:
                        problems.append(
                            f"line {fence_start}: duplicate exercise label "
                            f"{label!r} (also line {exercises[label]})"
                        )
                    exercises[label] = fence_start
            elif is_setup:
                problems.append(
                    f"line {fence_start}: `setup: true` with no `exercise:` label "
                    "— the setup code will never run"
                )

            body = "\n".join(cell_body)
            for run in BLANK_RUN.findall(body):
                if len(run) < 6:
                    problems.append(
                        f"line {fence_start}: blank written with {len(run)} "
                        "underscores; quarto-live needs at least 6"
                    )
            if label and not is_setup and "_" * 6 not in body:
                problems.append(
                    f"line {fence_start}: exercise {label!r} has no ______ blank "
                    "— students get nothing to fill in"
                )

            for key in cell_opts:
                if key not in KNOWN_OPTS:
                    problems.append(
                        f"line {fence_start}: unknown cell option {key!r}"
                    )
        cell_opts, cell_body = {}, []

    for n, line in enumerate(lines, start=1):
        m = FENCE.match(line)
        if m:
            if in_fence:
                close_cell()
                in_fence = False
            else:
                in_fence, fence_lang, fence_start = True, m.group(1), n
            continue

        if in_fence:
            opt = CELL_OPT.match(line)
            if opt:
                cell_opts[opt.group(1)] = opt.group(2)
            else:
                cell_body.append(line)
            continue

        m = DIV_OPEN.match(line)
        if m:
            attrs = m.group(2)
            div_stack.append((m.group(1), n))
            ex = DIV_ATTR_EX.search(attrs)
            if ex:
                kind = ("hint" if ".hint" in attrs
                        else "solution" if ".solution" in attrs else "div")
                referenced.append((ex.group(1), n, kind))
            elif ".hint" in attrs or ".solution" in attrs:
                problems.append(
                    f'line {n}: hint/solution div has no exercise="..." '
                    "attribute, so it will never be linked"
                )
            continue

        # An H1 renders as a section-break slide and an H2 as an ordinary one;
        # both count. Only reached outside a code fence, so `# comment` lines
        # inside Python cells don't inflate the total — and a heading nested in
        # a fenced div is a callout title (`## Hint`), not a slide.
        if re.match(r"^#{1,2}\s+\S", line):
            if not div_stack:
                n_slides += 1
                if line.startswith("# "):
                    n_sections += 1
            continue

        if DIV_BARE.match(line):
            if div_stack:
                div_stack.pop()
            else:
                problems.append(f"line {n}: closing ::: with nothing open")

    if in_fence:
        problems.append(f"line {fence_start}: code fence is never closed")
    for marker, n in div_stack:
        problems.append(f"line {n}: fenced div {marker} is never closed")

    # ---- cross-references -------------------------------------------------
    for label, n, kind in referenced:
        if label not in exercises:
            problems.append(
                f"line {n}: {kind} points at exercise {label!r}, which is not "
                "defined in this file"
            )
    for label, n in setups.items():
        if label not in exercises:
            problems.append(
                f"line {n[0]}: setup block for exercise {label!r}, "
                "which is not defined in this file"
            )
    for label, n in exercises.items():
        has_solution = any(l == label and k == "solution" for l, _, k in referenced)
        if not has_solution:
            problems.append(
                f"line {n}: exercise {label!r} has no solution block "
                "(intentional? students can't self-check)"
            )

    # ---- deck-level targets from the playbook -----------------------------
    # Advisory, not fatal: a deck can have a good reason to sit outside these,
    # but drifting outside them by accident is the failure mode.
    # Section breaks take seconds to deliver, so judge the target against the
    # content slides rather than the raw total.
    n_content = n_slides - n_sections
    if not 12 <= n_content <= 18:
        problems.append(
            f"note: {n_content} content slides (+{n_sections} section breaks) "
            "— the playbook targets 12-18 for a 75-minute session"
        )
    if not 3 <= len(exercises) <= 4:
        problems.append(
            f"note: {len(exercises)} live exercises — the playbook targets 3-4"
        )

    # "note:" lines are advisory and must not fail CI.
    fatal = [p for p in problems if not p.lstrip().startswith("note:")]

    if not quiet or problems:
        status = f"{len(fatal)} issue(s)" if fatal else "ok"
        print(f"[{'!' if fatal else 'ok'}] {path.name} — "
              f"{len(exercises)} exercises, {len(referenced)} hint/solution "
              f"blocks — {status}")
        for p in problems:
            print(f"      {p}")
    return fatal


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    total = 0
    for path in args.files:
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            total += 1
            continue
        total += len(check(path, args.quiet))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
