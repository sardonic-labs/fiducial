#!/usr/bin/env bash
# fiducial bootstrap - wires this repo into the host project.
# Run once after cloning/submoduling:  ./fiducial/bootstrap.sh
# Idempotent; remove with              ./fiducial/bootstrap.sh --remove
set -euo pipefail

FIDUCIAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$FIDUCIAL_DIR")"
FIDUCIAL_NAME="$(basename "$FIDUCIAL_DIR")"
AGENTS_PATH="$PROJECT_ROOT/AGENTS.md"
IMPORT_LINE="@$FIDUCIAL_NAME/AGENTS.md"

is_imported() {
  [ -f "$AGENTS_PATH" ] && grep -qxF "$IMPORT_LINE" "$AGENTS_PATH"
}

case "${1:-}" in
--remove)
  if ! is_imported; then
    echo "Not installed (no '$IMPORT_LINE' in AGENTS.md). Nothing to do."
    exit 0
  fi
  grep -vxF "$IMPORT_LINE" "$AGENTS_PATH" > "$AGENTS_PATH.tmp" && mv "$AGENTS_PATH.tmp" "$AGENTS_PATH"
  echo "Removed fiducial import from $AGENTS_PATH"
  exit 0
  ;;
esac

touch "$AGENTS_PATH"

if is_imported; then
  echo "Already imported ($IMPORT_LINE). Nothing to do."
else
  printf '\n%s\n' "$IMPORT_LINE" >> "$AGENTS_PATH"
  echo "Added '$IMPORT_LINE' to $AGENTS_PATH"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 "$FIDUCIAL_DIR/scripts/fiducial.py" doctor || true
else
  echo "WARNING: python3 not found on PATH; fiducial.py tools need Python 3" >&2
fi
