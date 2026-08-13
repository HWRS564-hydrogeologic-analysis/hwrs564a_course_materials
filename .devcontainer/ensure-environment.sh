#!/usr/bin/env bash
# Fast check on every container start. Re-run the full idempotent bootstrap if
# a stopped/rebuilt Codespace has lost its project environment or kernel.
set -euo pipefail

COURSE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$COURSE_ROOT"
export PATH="$COURSE_ROOT/.venv/bin:$HOME/.local/bin:$PATH"

ready=true
command -v uv >/dev/null 2>&1 || ready=false
[[ -x "$COURSE_ROOT/.venv/bin/python" ]] || ready=false
[[ -x "$COURSE_ROOT/modflow/mf2005" ]] || ready=false

if [[ "$ready" == true ]]; then
    "$COURSE_ROOT/.venv/bin/python" - <<'PYCHECK' >/dev/null 2>&1 || ready=false
import importlib

for name in ("numpy", "pandas", "matplotlib", "scipy", "flopy", "ipykernel"):
    importlib.import_module(name)
PYCHECK
fi

if [[ "$ready" == true ]]; then
    # Refreshing an existing kernelspec is cheap and ensures it follows the
    # current workspace path if Codespaces recreated or renamed the checkout.
    "$COURSE_ROOT/.venv/bin/python" -m ipykernel install --user \
        --name hwrs564a --display-name "Python 3 (hwrs564a)" >/dev/null
    echo "HWRS 564a environment ready: $COURSE_ROOT/.venv/bin/python"
else
    echo "HWRS 564a environment incomplete; repairing it now..."
    bash "$COURSE_ROOT/postbuild.sh"
fi
