#!/usr/bin/env bash
# Codespace / devcontainer setup. Runs once when the container is created.
set -euo pipefail

COURSE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$COURSE_ROOT"

# The devcontainer image includes uv, but keep setup self-healing for a clone
# opened in a generic Codespace or another compatible Linux container.
export PATH="$COURSE_ROOT/.venv/bin:$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv was not supplied by the container; installing it from Astral..."
    if ! command -v curl >/dev/null 2>&1; then
        echo "ERROR: curl is required to install uv." >&2
        exit 1
    fi
    curl -LsSf https://astral.sh/uv/0.11.32/install.sh \
        | env UV_UNMANAGED_INSTALL="$HOME/.local/bin" sh
fi

echo "=============================================="
echo "HWRS 564a — setting up your environment"
echo "working directory: $(pwd)"
echo "=============================================="

# 1. Python environment ---------------------------------------------------
echo "[1/4] Building the Python environment with uv..."
echo "  uv            $(uv --version)"
uv sync --frozen

PYTHON="$COURSE_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: uv sync completed without creating $PYTHON" >&2
    exit 1
fi

# 2. MODFLOW binaries ----------------------------------------------------
# Needed from Week 10. Downloading now means class time isn't spent on it.
echo "[2/4] Downloading MODFLOW executables..."
if [[ -x "$COURSE_ROOT/modflow/mf2005" ]]; then
    echo "  ok   modflow/mf2005 already present"
else
    mkdir -p "$COURSE_ROOT/modflow"
    "$PYTHON" -c "from flopy.utils import get_modflow; get_modflow('$COURSE_ROOT/modflow')"
fi

# 3. Jupyter kernel ------------------------------------------------------
echo "[3/4] Registering the Jupyter kernel..."
"$PYTHON" -m ipykernel install --user --name hwrs564a \
    --display-name "Python 3 (hwrs564a)"

# 4. Sanity check --------------------------------------------------------
echo "[4/4] Verifying the install..."
"$PYTHON" - <<'PYCHECK'
import importlib, sys
required = [
    "numpy", "pandas", "matplotlib", "scipy", "flopy", "yaml",
    "ipykernel", "dataretrieval", "sklearn",
]
missing = []
for name in required:
    try:
        m = importlib.import_module(name)
        print(f"  ok   {name:12s} {getattr(m, '__version__', '?')}")
    except ImportError:
        missing.append(name)
        print(f"  FAIL {name}")
if missing:
    sys.exit(f"missing packages: {', '.join(missing)}")
PYCHECK

if command -v quarto >/dev/null 2>&1; then
    echo "  ok   quarto       $(quarto --version)"
    # live-revealjs / live-html come from this extension. No-op if already present.
    quarto add --no-prompt r-wasm/quarto-live >/dev/null 2>&1 \
        && echo "  ok   quarto-live extension" \
        || echo "  note could not install quarto-live (offline?)"
else
    echo "  note quarto not found — only needed if you build the slides yourself"
fi

echo
echo "=============================================="
echo "Ready. Open a notebook in labs/ and pick the"
echo "'Python 3 (hwrs564a)' kernel."
echo "Python: $PYTHON"
echo "=============================================="
