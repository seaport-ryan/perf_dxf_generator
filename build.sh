#!/usr/bin/env bash
# build.sh — Clean build + Windows .exe (PyInstaller) for perf_dxf_generator
# Run from Git Bash at repo root:
#   ./build.sh
# Optional env overrides:
#   CLEAN=0 ./build.sh                 # keep previous build
#   CONSOLE=0 ./build.sh               # hide console (windowed)
#   FORCE_SPEC_REGEN=1 ./build.sh      # ignore .spec; rebuild from args
#   VENV_DIR=.venv PYTHON="py -3.11" ./build.sh

set -Eeuo pipefail

# ----- App-specific defaults --------------------------------------------------
APP_NAME="${APP_NAME:-perf_dxf_generator}"
ENTRYPOINT="${ENTRYPOINT:-perf_dxf_generator.py}"
SPEC_FILE="${SPEC_FILE:-perf_dxf_generator.spec}"
ICON_FILE="${ICON_FILE:-perf.ico}"

# Behavior toggles
CLEAN="${CLEAN:-1}"            # 1=rm -rf build/ dist/
CONSOLE="${CONSOLE:-1}"        # 1=console app (CLI), 0=windowed
FORCE_SPEC_REGEN="${FORCE_SPEC_REGEN:-}"  # non-empty = ignore .spec, rebuild from args

# Python / venv
VENV_DIR="${VENV_DIR:-.venv}"
PYTHON="${PYTHON:-}"           # e.g., "py -3.11" or "C:/Python311/python.exe"

say() { printf "\033[1;36m%s\033[0m\n" "$*"; }
err() { printf "\033[1;31m%s\033[0m\n" "$*" >&2; }
exists() { command -v "$1" >/dev/null 2>&1; }

# ----- Resolve Python ---------------------------------------------------------
if [[ -z "$PYTHON" ]]; then
  if exists py; then
    PYTHON="py -3"
  elif exists python3; then
    PYTHON="python3"
  elif exists python; then
    PYTHON="python"
  else
    err "No Python found on PATH. Install Python 3.x."
    exit 1
  fi
fi

# ----- Enter repo root --------------------------------------------------------
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ----- Create / activate venv -------------------------------------------------
if [[ ! -d "$VENV_DIR" ]]; then
  say "Creating venv at $VENV_DIR"
  eval "$PYTHON -m venv \"$VENV_DIR\""
fi

# shellcheck disable=SC1091
source "$VENV_DIR/Scripts/activate" 2>/dev/null || source "$VENV_DIR/bin/activate"

# ----- Dependencies -----------------------------------------------------------
say "Upgrading pip & wheel…"
python -m pip install --upgrade pip wheel >/dev/null

if [[ -f "requirements.txt" ]]; then
  say "Installing requirements.txt…"
  python -m pip install -r "requirements.txt"
fi

python -c "import PyInstaller" 2>/dev/null || {
  say "Installing PyInstaller…"
  python -m pip install pyinstaller
}

# ----- Clean previous build ---------------------------------------------------
if [[ "$CLEAN" == "1" ]]; then
  say "Cleaning build artifacts…"
  rm -rf "build/" "dist/"
fi

# ----- Build with spec if available (unless forced off) -----------------------
USE_SPEC=""
if [[ -z "$FORCE_SPEC_REGEN" && -f "$SPEC_FILE" ]]; then
  USE_SPEC="$SPEC_FILE"
fi

if [[ -n "$USE_SPEC" ]]; then
  say "Building with spec: $USE_SPEC"
  # --noconfirm overwrites previous outputs without prompt
  pyinstaller --noconfirm "$USE_SPEC"
else
  say "Building from CLI args (no spec)…"
  # Compose PyInstaller args
  ARGS=( --noconfirm --clean --onefile --name "$APP_NAME" )
  if [[ "$CONSOLE" == "0" ]]; then
    ARGS+=( --noconsole )
  fi
  if [[ -f "$ICON_FILE" ]]; then
    ARGS+=( --icon "$ICON_FILE" )
  fi

  # Ensure entrypoint exists
  if [[ ! -f "$ENTRYPOINT" ]]; then
    err "Entrypoint not found: $ENTRYPOINT"
    exit 1
  fi

  pyinstaller "${ARGS[@]}" "$ENTRYPOINT"
fi

# ----- Convenience: ensure dist/<name>.exe exists at top-level dist ----------
if [[ -f "dist/${APP_NAME}/${APP_NAME}.exe" ]]; then
  cp -f "dist/${APP_NAME}/${APP_NAME}.exe" "dist/${APP_NAME}.exe"
fi

# ----- Done -------------------------------------------------------------------
if [[ -f "dist/${APP_NAME}.exe" ]]; then
  say "Build complete → dist/${APP_NAME}.exe"
else
  # Some specs output directly to dist/appname.exe already
  if [[ -f "dist/${APP_NAME}/${APP_NAME}.exe" ]]; then
    say "Build complete → dist/${APP_NAME}/${APP_NAME}.exe"
  else
    err "Could not find the built exe. Check PyInstaller output above."
    exit 1
  fi
fi

