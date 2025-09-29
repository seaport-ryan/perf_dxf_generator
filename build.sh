#!/usr/bin/env bash
# build.sh — Build Perf DXF Generator GUI into a Windows .exe via PyInstaller.
# Run from Git Bash at the repo root:  ./build.sh
#
# Env overrides:
#   CLEAN=0            # don’t delete build/ and dist/
#   ONEFILE=1          # package as a single exe (default 1)
#   CONSOLE=0          # hide console window (default 0 = windowed app)
#   PYTHON="py -3.11"  # python launcher to use (default: python)
#   APP_NAME=perf_dxf_generator
#   ENTRYPOINT=perf_dxf_gui.py
#   ICON=perf.ico

set -Eeuo pipefail

# -------- Defaults -------------------------------------------------------------
APP_NAME="${APP_NAME:-perf_dxf_generator}"
ENTRYPOINT="${ENTRYPOINT:-perf_dxf_gui.py}"
ICON="${ICON:-perf.ico}"
PYTHON_BIN="${PYTHON:-python}"

CLEAN="${CLEAN:-1}"
ONEFILE="${ONEFILE:-1}"
CONSOLE="${CONSOLE:-0}"   # 0 => --windowed, 1 => console

# -------- Helpers --------------------------------------------------------------
say() { printf "\033[1;36m%s\033[0m\n" "$*"; }
ok()  { printf "\033[1;32m%s\033[0m\n" "$*"; }
err() { printf "\033[1;31m%s\033[0m\n" "$*" >&2; }

# -------- Preflight ------------------------------------------------------------
if [[ ! -f "$ENTRYPOINT" ]]; then
  err "Cannot find entrypoint: $ENTRYPOINT"
  exit 1
fi

if ! command -v $PYTHON_BIN >/dev/null 2>&1; then
  err "Python not found: $PYTHON_BIN"
  exit 1
fi

say "Using Python: $($PYTHON_BIN -V 2>&1)"

# Ensure pyinstaller is available
if ! $PYTHON_BIN -c "import PyInstaller" >/dev/null 2>&1; then
  say "Installing PyInstaller..."
  $PYTHON_BIN -m pip install --upgrade pip
  $PYTHON_BIN -m pip install pyinstaller
fi

# Shapely / ezdxf are required by the generator
$PYTHON_BIN -m pip install --upgrade ezdxf shapely >/dev/null

# -------- Clean old artifacts --------------------------------------------------
if [[ "$CLEAN" == "1" ]]; then
  say "Cleaning build/ and dist/..."
  rm -rf build dist
fi

# -------- PyInstaller options --------------------------------------------------
WINMODE="--windowed"
if [[ "$CONSOLE" == "1" ]]; then
  WINMODE="--console"
fi

PACKMODE="--onefile"
if [[ "$ONEFILE" != "1" ]]; then
  PACKMODE="--onedir"
fi

ICON_ARG=""
if [[ -f "$ICON" ]]; then
  ICON_ARG="--icon=$ICON"
  say "Using icon: $ICON"
else
  say "Icon not found ($ICON); continuing without custom icon."
fi

# Collect all data/hooks for shapely & ezdxf to avoid missing libs at runtime
COLLECT_ARGS="
  --collect-all shapely
  --collect-all ezdxf
"

# -------- Build ----------------------------------------------------------------
say "Building $APP_NAME from $ENTRYPOINT ..."
set -x
$PYTHON_BIN -m PyInstaller \
  --noconfirm \
  --clean \
  $PACKMODE \
  $WINMODE \
  --name "$APP_NAME" \
  $ICON_ARG \
  $COLLECT_ARGS \
  "$ENTRYPOINT"
set +x

# -------- Result ----------------------------------------------------------------
if [[ -f "dist/${APP_NAME}.exe" ]]; then
  ok "Build complete → dist/${APP_NAME}.exe"
elif [[ -f "dist/${APP_NAME}/${APP_NAME}.exe" ]]; then
  ok "Build complete → dist/${APP_NAME}/${APP_NAME}.exe"
else
  err "Could not find the built exe. See PyInstaller output above."
  exit 1
fi

