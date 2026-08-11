#!/usr/bin/env bash
# Convert a PDF to markdown with marker, in page-range chunks.
#
# Marker stalls indefinitely on this 302-page book: it loads its models, then blocks at
# 0% CPU and never finishes. The same invocation with --page_range completes fine, so
# the work is split into chunks and the markdown concatenated. Each chunk pays the
# ~90 second model load again, which is the price of a run that actually terminates.
#
# Usage: scripts/convert_pdf.sh <pdf> <output-dir> [pages-per-chunk] [total-pages]

set -euo pipefail

PDF="${1:?usage: convert_pdf.sh <pdf> <output-dir> [chunk] [pages]}"
OUT="${2:?usage: convert_pdf.sh <pdf> <output-dir> [chunk] [pages]}"
CHUNK="${3:-30}"
MARKER="${MARKER_BIN:-$HOME/Documents/marker-ocr/venv/bin/marker_single}"

if [ -n "${4:-}" ]; then
  PAGES="$4"
else
  PAGES=$(mdls -raw -name kMDItemNumberOfPages "$PDF" 2>/dev/null || echo 0)
fi
[ "$PAGES" -gt 0 ] || { echo "could not determine page count; pass it as argument 4" >&2; exit 1; }

BASE=$(basename "${PDF%.pdf}")
WORK="$OUT/.chunks/$BASE"
mkdir -p "$WORK" "$OUT"

echo "converting $BASE: $PAGES pages in chunks of $CHUNK"
started=$(date +%s)

for (( first=0; first<PAGES; first+=CHUNK )); do
  last=$(( first + CHUNK - 1 ))
  [ "$last" -ge "$PAGES" ] && last=$(( PAGES - 1 ))
  target="$WORK/$(printf '%04d' "$first")-$(printf '%04d' "$last")"

  # Chunks already done are skipped, so an interrupted run resumes where it stopped.
  if [ -f "$target/$BASE/$BASE.md" ]; then
    echo "  pages $first-$last: already done"
    continue
  fi

  chunk_started=$(date +%s)
  if HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 timeout 900 "$MARKER" \
      --mode fast --disable_multiprocessing --page_range "$first-$last" \
      --output_format markdown --output_dir "$target" "$PDF" >"$target.log" 2>&1; then
    echo "  pages $first-$last: $(( $(date +%s) - chunk_started ))s"
  else
    echo "  pages $first-$last: FAILED (see $target.log)" >&2
  fi
done

# Concatenate in page order. A page-range marker between chunks keeps the ingest step
# able to tell where each one came from.
FINAL="$OUT/$BASE.md"
: > "$FINAL"
for dir in "$WORK"/*/; do
  range=$(basename "$dir")
  md="$dir$BASE/$BASE.md"
  [ -f "$md" ] || continue
  printf '\n\n<!-- pages %s -->\n\n' "$range" >> "$FINAL"
  cat "$md" >> "$FINAL"
done

echo "done in $(( $(date +%s) - started ))s -> $FINAL ($(wc -c < "$FINAL") bytes)"
