#!/usr/bin/env bash
set -euo pipefail

# Phase 2: move logic assets into Pillar 03 and apply immediate path fixes.
# Run from repository root.

if [[ ! -d .git ]]; then
  echo "ERROR: Run this script from the repository root." >&2
  exit 1
fi

mkdir -p docs/03_Logic_Core

# Move requested logic assets.
for p in app alembic alembic.ini utils requirements.txt Procfile; do
  if [[ -e "$p" ]]; then
    git mv "$p" docs/03_Logic_Core/
  else
    echo "WARN: $p not found at repo root; skipping"
  fi
done

# Post-move runtime fix:
# NOTE: docs.03_Logic_Core.app.main:app is NOT a valid Python module path.
# Keep module as app.main and point PYTHONPATH at docs/03_Logic_Core.
if [[ -f docs/03_Logic_Core/Procfile ]]; then
  cat > docs/03_Logic_Core/Procfile <<'EOF'
web: export PYTHONPATH=$PYTHONPATH:docs/03_Logic_Core && gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT --workers 2
EOF
fi

# Post-move migration fix:
# Ensure Alembic resolves scripts and app package from the new location.
if [[ -f docs/03_Logic_Core/alembic.ini ]]; then
  sed -i 's#^script_location\s*=.*#script_location = %(here)s/alembic#' docs/03_Logic_Core/alembic.ini
  sed -i 's#^prepend_sys_path\s*=.*#prepend_sys_path = %(here)s#' docs/03_Logic_Core/alembic.ini
fi

# Optional but strongly recommended deploy config fix (DigitalOcean app spec).
if [[ -f app.yaml ]]; then
  sed -i 's#app\.main:app#app.main:app#' app.yaml
  sed -i 's#PYTHONPATH=\$PYTHONPATH:\.#PYTHONPATH=$PYTHONPATH:docs/03_Logic_Core#' app.yaml
fi

cat <<'EOF'

Phase 2 move complete.

Recommended validation commands:
  git status --short
  PYTHONPATH=docs/03_Logic_Core python -m app.main
  alembic -c docs/03_Logic_Core/alembic.ini current

EOF
