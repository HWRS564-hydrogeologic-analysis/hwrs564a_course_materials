#!/usr/bin/env bash
# Codespace / devcontainer setup. Runs once when the container is created.
set -euo pipefail

echo "=============================================="
echo "HWRS 564a — setting up your environment"
echo "working directory: $(pwd)"
echo "=============================================="

# 1. Python environment ---------------------------------------------------
echo "[1/4] Building the Python environment with uv..."
uv venv
uv sync
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. MODFLOW binaries ----------------------------------------------------
# Needed from Week 10. Downloading now means class time isn't spent on it.
echo "[2/4] Downloading MODFLOW executables..."
mkdir -p ./modflow
python -c "from flopy.utils import get_modflow; get_modflow('./modflow')"

# 3. Jupyter kernel ------------------------------------------------------
echo "[3/4] Registering the Jupyter kernel..."
python -m ipykernel install --user --name hwrs564a \
    --display-name "Python 3 (hwrs564a)"

# 4. Sanity check --------------------------------------------------------
echo "[4/4] Verifying the install..."
python - <<'PYCHECK'
import importlib, sys
required = ["numpy", "pandas", "matplotlib", "scipy", "flopy", "yaml"]
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
echo "=============================================="
