#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/raw"
FILE="$DATA_DIR/raw-wiktextract-data.jsonl"
GZ_FILE="$FILE.gz"
URL="https://kaikki.org/dictionary/raw-wiktextract-data.jsonl.gz"

FORCE=false
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
    esac
done

mkdir -p "$DATA_DIR"

if [ -f "$FILE" ] && [ "$FORCE" = false ]; then
    echo "Data already exists at $FILE"
    echo "Use --force to re-download."
    exit 0
fi

if [ -f "$GZ_FILE" ] && [ "$FORCE" = false ]; then
    echo "Compressed file already exists, extracting..."
    gunzip -f "$GZ_FILE"
    echo "Done. File: $FILE"
    wc -l "$FILE"
    exit 0
fi

echo "Downloading full Kaikki Wiktionary dump..."
echo "This is a large file (~3GB compressed). Please be patient."
curl -L --progress-bar -o "$GZ_FILE" "$URL"

echo "Extracting..."
gunzip -f "$GZ_FILE"

echo "Done. File: $FILE"
wc -l "$FILE"
