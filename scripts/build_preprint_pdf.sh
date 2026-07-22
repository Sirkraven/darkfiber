#!/usr/bin/env bash
# Builds docs/writeup_v1.1.0_preprint.pdf from docs/writeup.md.
#
# Not a general-purpose tool -- this is the exact recipe used for the
# FASE F4/F4.1/F4.2 preprint PDF, kept as a script instead of ad hoc
# shell commands because it's already been re-run more than once as the
# writeup was revised. Requires: pandoc, Google Chrome (headless
# print-to-pdf). Neither LaTeX nor wkhtmltopdf/weasyprint is assumed --
# none were available when this was first built.
#
# The generated .html/.pdf are gitignored (regenerable, like figures/) --
# only this script and docs/preprint_cover.html / docs/preprint_style.css
# are source, tracked in git.
#
# Usage: bash scripts/build_preprint_pdf.sh

set -euo pipefail
cd "$(dirname "$0")/.."

CHROME="/c/Program Files/Google/Chrome/Application/chrome.exe"
OUT_BASENAME="docs/writeup_v1.1.0_preprint"
TITLE="darkfiber v1.1.0 — a physics-first coherence engine for DAS, with measured per-installation detection limits and honest abstention"

if [ ! -x "$CHROME" ]; then
  echo "Chrome not found at: $CHROME (edit this script if it's elsewhere)" >&2
  exit 1
fi

TMP_FRAGMENT="$(mktemp)"
pandoc docs/writeup.md -f markdown -t html5 --resource-path=docs \
  --embed-resources --standalone=false -o "$TMP_FRAGMENT"

{
  echo '<!doctype html>'
  echo '<html lang="en"><head><meta charset="utf-8">'
  echo "<title>${TITLE}</title>"
  echo '<style>'
  cat docs/preprint_style.css
  echo '</style></head><body>'
  cat docs/preprint_cover.html
  cat "$TMP_FRAGMENT"
  echo '</body></html>'
} > "${OUT_BASENAME}.html"
rm -f "$TMP_FRAGMENT"

# Chrome on Windows needs a real Windows path in the file:// URL --
# git-bash's own /d/... mount-style pwd is NOT valid here (silently
# produces a near-empty "page not found" PDF, not an error). cygpath
# converts POSIX -> Windows.
WIN_PDF_PATH="$(cygpath -w "$(pwd)/${OUT_BASENAME}.pdf")"
WIN_HTML_PATH="$(cygpath -w "$(pwd)/${OUT_BASENAME}.html")"

"$CHROME" --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$WIN_PDF_PATH" --print-to-pdf-no-header \
  "file:///$WIN_HTML_PATH"

echo "Built: ${OUT_BASENAME}.html and ${OUT_BASENAME}.pdf"
echo "Verify visually before this goes to the author or anywhere external --"
echo "  python -c \"import fitz; d=fitz.open('${OUT_BASENAME}.pdf'); print(d.page_count, 'pages')\""
echo "then render+Read a sample of pages (see FASE F4.1's report for the method)."
