PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS Books (
    book_id          INTEGER PRIMARY KEY,
    title            TEXT NOT NULL,
    authors          TEXT NOT NULL,
    isbn             TEXT,
    publication_year INTEGER,
    language_code    TEXT,
    average_rating   REAL,
    total_copies     INTEGER NOT NULL DEFAULT 3 CHECK (total_copies >= 0),
    available_copies INTEGER NOT NULL DEFAULT 3 CHECK (available_copies >= 0)
);

CREATE TABLE IF NOT EXISTS Members (
    member_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    phone       TEXT,
    joined_date TEXT NOT NULL DEFAULT (date('now'))
);

CREATE TABLE IF NOT EXISTS Issued_Books (
    issue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id     INTEGER NOT NULL REFERENCES Books(book_id),
    member_id   INTEGER NOT NULL REFERENCES Members(member_id),
    issue_date  TEXT NOT NULL,
    due_date    TEXT NOT NULL,
    return_date TEXT,                      -- NULL means still issued
    fine_amount INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_books_title   ON Books(title);
CREATE INDEX IF NOT EXISTS idx_books_authors ON Books(authors);
CREATE INDEX IF NOT EXISTS idx_issued_book   ON Issued_Books(book_id);
CREATE INDEX IF NOT EXISTS idx_issued_member ON Issued_Books(member_id);
