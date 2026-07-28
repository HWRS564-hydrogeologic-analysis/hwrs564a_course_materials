"""Restrict nbmake to the *generated* solution notebooks.

The student copy of every lab has `...` placeholders in its YOUR TURN cells, so
it is not supposed to execute — running it would fail on the first CHECK cell.
The runnable copy is what `scripts/fill_solutions.py` writes into
`labs/weekNN/_solutions/`, and that is what proves the lab survives a restart.

    python scripts/fill_solutions.py labs/*/*.ipynb
    pytest labs/
"""

from __future__ import annotations

from pathlib import Path


def pytest_ignore_collect(collection_path: Path, config) -> bool | None:
    if collection_path.name == ".ipynb_checkpoints":
        return True
    if collection_path.suffix == ".ipynb":
        return "_solutions" not in collection_path.parts
    return None
