#!/usr/bin/env bash

set -euo pipefail

MAX_PARALLEL_DOWNLOADS="${MAX_PARALLEL_DOWNLOADS:-4}"
VIDEOS_FILE="${VIDEOS_FILE:-./videos.txt}"
COOKIES_FILE="${COOKIES_FILE:-./yt_cookies.txt}"

if [[ ! -f "$VIDEOS_FILE" ]]; then
    printf 'Not found: %s\n' "$VIDEOS_FILE" >&2
    exit 1
fi

export COOKIES_FILE

awk '!/^[[:space:]]*(#|$)/' "$VIDEOS_FILE" |
    xargs -r -P "$MAX_PARALLEL_DOWNLOADS" -n 1 bash -c '
        yt-dlp -o "%(playlist)s/%(title)s.%(ext)s" --yes-playlist --no-check-certificates -N 12 --js-runtime node --remote-components ejs:github --extractor-args generic:impersonate --cookies "$COOKIES_FILE" "$1"
    ' _
