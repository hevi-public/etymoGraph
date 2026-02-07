"""Load Kaikki JSONL data into MongoDB."""

import json
import sys
from pathlib import Path

from pymongo import TEXT, IndexModel, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

MONGO_URI = "mongodb://mongodb:27017/etymology"
DATA_FILE = "/data/raw/raw-wiktextract-data.jsonl"
BATCH_SIZE = 1000


def load_documents(col: Collection, data_path: Path) -> int:
    """Read JSONL file and batch-insert documents into MongoDB.

    Returns the total number of documents loaded.
    """
    print(f"Loading {data_path}...")
    batch = []
    count = 0

    with open(data_path) as f:
        for raw_line in f:
            line = raw_line.strip()
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
    return count


def create_indexes(col: Collection) -> None:
    """Create search and lookup indexes on the words collection."""
    print("Creating indexes...")
    col.create_indexes(
        [
            IndexModel([("word", 1), ("lang", 1)]),
            IndexModel([("word", 1)]),
            IndexModel([("word", TEXT)]),
            IndexModel([("etymology_templates.args.2", 1), ("etymology_templates.args.3", 1)]),
            IndexModel(
                [
                    ("etymology_templates.name", 1),
                    ("etymology_templates.args.2", 1),
                    ("etymology_templates.args.3", 1),
                ]
            ),
        ]
    )


def build_language_table(db: Database) -> None:
    """Aggregate unique lang_code/lang pairs into a languages collection."""
    print("Building language code lookup table...")
    lang_col = db.languages
    lang_col.drop()
    pipeline = [
        {"$group": {"_id": {"lang_code": "$lang_code", "lang": "$lang"}}},
        {"$project": {"_id": 0, "lang_code": "$_id.lang_code", "lang": "$_id.lang"}},
    ]
    lang_docs = list(db.words.aggregate(pipeline, allowDiskUse=True))
    if lang_docs:
        lang_col.insert_many(lang_docs)
        lang_col.create_index("lang_code")
        lang_col.create_index("lang")
    print(f"  {len(lang_docs)} language mappings stored.")


def main() -> None:
    """Validate data file, connect to MongoDB, load documents and build indexes."""
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

    load_documents(col, data_path)
    create_indexes(col)
    build_language_table(db)

    print("Done.")


if __name__ == "__main__":
    main()
