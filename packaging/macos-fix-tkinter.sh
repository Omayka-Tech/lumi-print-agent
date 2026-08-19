#!/usr/bin/env bash
# Repara tkinter en macOS cuando pyenv busca libtk8.6 y Homebrew tiene Tcl/Tk 9.
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Solo aplica a macOS." >&2
  exit 1
fi
brew install tcl-tk@8
PREFIX="$(brew --prefix tcl-tk@8)"
LIB="${PREFIX}/lib"
if [[ ! -e "${LIB}/libtk8.6.dylib" ]]; then
  echo "No está ${LIB}/libtk8.6.dylib después de brew install tcl-tk@8." >&2
  exit 1
fi
echo "export DYLD_FALLBACK_LIBRARY_PATH=\"${LIB}\${DYLD_FALLBACK_LIBRARY_PATH:+:\$DYLD_FALLBACK_LIBRARY_PATH}\""
echo
echo "Pegá esa línea en esta shell y corré: python -m lumi_print_gui"
echo "Para hacerlo permanente, añadila a ~/.zshrc"
echo
echo "Alternativa: venv con /opt/homebrew/bin/python3.13 (brew install python-tk@3.13)"
