#!/usr/bin/env bash
# Comprueba la sintaxis de los scripts de bash y de Python de bin/. Con --shellcheck pasa ademas shellcheck.
# (bin/ mezcla scripts de bash y alguno de Python, como pcpi-config: cada uno se comprueba con lo suyo.)
set -eu
cd "$(dirname "${BASH_SOURCE[0]}")/.."
bash_files=(install.sh uninstall.sh)
for f in bin/*; do
  case "$(head -n1 "$f")" in
    *bash*) bash_files+=("$f") ;;
    *python*) python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$f" ;;
  esac
done
for f in "${bash_files[@]}"; do bash -n "$f"; done
if [ "${1:-}" = "--shellcheck" ]; then shellcheck -S warning "${bash_files[@]}"; fi
echo "lint de shell OK (${#bash_files[@]} scripts de bash)"
