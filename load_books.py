"""Load the Kaggle Goodbooks-10k books.csv into the Books table.

Usage:  python load_books.py books.csv
"""
import csv
import os
import sqlite3
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "library.db")
SCHEMA = os.path.join(BASE_DIR, "schema.sql")


def to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def clean_isbn(v):
    """The CSV stores ISBNs as numbers, so leading zeros are lost; restore them."""
    v = (v or "").strip()
    if not v:
        return None
    if v.isdigit() and len(v) < 10:
        v = v.zfill(10)
    return v


def main(csv_path):
    conn = sqlite3.connect(DB)
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append((
                to_int(r["id"]),  # 1..10000: short IDs that are easy to type
                r["title"].strip(),
                r["authors"].strip(),
                clean_isbn(r.get("isbn")),
                to_int(r.get("original_publication_year")),
                (r.get("language_code") or "").strip() or None,
                to_float(r.get("average_rating")),
            ))

    # 3 copies of each book by default (total_copies / available_copies defaults)
    conn.executemany(
        """INSERT OR IGNORE INTO Books
           (book_id, title, authors, isbn, publication_year, language_code, average_rating)
           VALUES (?,?,?,?,?,?,?)""",
        rows,
    )
    conn.commit()
    count = conn.execute("SELECT COUNT(*) FROM Books").fetchone()[0]
    print(f"Done. Books table now has {count} rows.")
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python load_books.py books.csv")
    main(sys.argv[1])
