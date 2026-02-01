#!/usr/bin/env bash
set -euo pipefail

input="${1-}"
if [[ -z "$input" ]]; then
  if ! read -r input; then
    echo "Usage: $0 '[1,2],[3,4]'" >&2
    exit 1
  fi
fi

awk -v input="$input" 'BEGIN {
  gsub(/\],\[/, "\n", input)
  gsub(/^\[/, "", input)
  gsub(/\]$/, "", input)
  nrows = split(input, rows, "\n")
  for (r = 1; r <= nrows; r++) {
    ncols = split(rows[r], cells, ",")
    if (ncols > maxc) {
      maxc = ncols
    }
    for (c = 1; c <= ncols; c++) {
      data[r, c] = cells[c]
    }
  }
  for (c = 1; c <= maxc; c++) {
    printf "["
    for (r = 1; r <= nrows; r++) {
      printf "%s", data[r, c]
      if (r < nrows) {
        printf ","
      }
    }
    printf "]"
    if (c < maxc) {
      printf ","
    }
  }
  printf "\n"
}'
