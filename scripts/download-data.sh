#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="$ROOT_DIR/data/raw"
FILE="$DATA_DIR/kaikki-english.jsonl"
GZ_FILE="$FILE.gz"
URL="https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz"

mkdir -p "$DATA_DIR"

if [ -f "$FILE" ] && [ "$1" != "--force" ] 2>/dev/null; then
    echo "Data already exists at $FILE"
    echo "Use --force to re-download."
    exit 0
fi

echo "Downloading Kaikki English dump..."
curl -L --progress-bar -o "$GZ_FILE" "$URL"

echo "Extracting..."
gunzip -f "$GZ_FILE"

echo "Done. File: $FILE"
wc -l "$FILE"
