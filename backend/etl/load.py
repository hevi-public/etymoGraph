"""Load Kaikki JSONL data into MongoDB."""

import json
import sys
from pathlib import Path
from pymongo import MongoClient, IndexModel, TEXT

MONGO_URI = "mongodb://mongodb:27017/etymology"
DATA_FILE = "/data/raw/kaikki-english.jsonl"
BATCH_SIZE = 1000


def main():
    data_path = Path(DATA_FILE)
    if not data_path.exists():
        print(f"ERROR: Data file not found: {DATA_FILE}")
        print("Run ./scripts/download-data.sh first.")
        sys.exit(1)

    client = MongoClient(MONGO_URI)
    db = client.etymology
    col = db.words

    # Drop existing data for clean reload
    existing = col.estimated_document_count()
    if existing > 0:
        print(f"Dropping {existing} existing documents...")
        col.drop()

    print(f"Loading {DATA_FILE}...")
    batch = []
    count = 0

    with open(data_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                batch.append(doc)
            except json.JSONDecodeError:
                continue

            if len(batch) >= BATCH_SIZE:
                col.insert_many(batch, ordered=False)
                count += len(batch)
                batch = []
                if count % 10000 == 0:
                    print(f"  {count:,} documents loaded...")

    if batch:
        col.insert_many(batch, ordered=False)
        count += len(batch)

    print(f"Loaded {count:,} documents.")

    print("Creating indexes...")
    col.create_indexes([
        IndexModel([("word", 1), ("lang", 1)]),
        IndexModel([("word", TEXT)]),
    ])
    print("Done.")


if __name__ == "__main__":
    main()
