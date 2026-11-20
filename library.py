"""Library Management System - core logic + command-line menu (Python + SQLite).

Run the menu:       python library.py
Run the web app:    streamlit run app.py
"""
import os
import sqlite3
from datetime import date, datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "library.db")
SCHEMA = os.path.join(BASE_DIR, "schema.sql")

LOAN_DAYS = 14       # a book can be kept for 14 days
FINE_PER_DAY = 2     # Rs. 2 for every day after the due date


def connect(check_same_thread=True):
    conn = sqlite3.connect(DB, check_same_thread=check_same_thread)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    with open(SCHEMA, encoding="utf-8") as f:
        conn.executescript(f.read())
    return conn


def _rows(cur):
    return [dict(r) for r in cur.fetchall()]


def _to_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def calculate_fine(due_date, return_date):
    """Rs. 2 per day for every day after the due date, never negative."""
    return max(0, (return_date - due_date).days) * FINE_PER_DAY


# ------------------------------------------------------------------ books

def get_book(conn, book_id):
    row = conn.execute("SELECT * FROM Books WHERE book_id=?", (book_id,)).fetchone()
    return dict(row) if row else None


def add_book(conn, title, authors, isbn=None, year=None, copies=3):
    title, authors = (title or "").strip(), (authors or "").strip()
    if not title or not authors:
        raise ValueError("Title and author are required.")
    if copies < 1:
        raise ValueError("A book needs at least 1 copy.")
    new_id = conn.execute("SELECT COALESCE(MAX(book_id), 0) + 1 FROM Books").fetchone()[0]
    conn.execute(
        """INSERT INTO Books (book_id, title, authors, isbn, publication_year,
                              total_copies, available_copies)
           VALUES (?,?,?,?,?,?,?)""",
        (new_id, title, authors, (isbn or "").strip() or None, year, copies, copies))
    conn.commit()
    return new_id


def update_book(conn, book_id, title, authors, isbn=None, year=None, total_copies=None):
    book = get_book(conn, book_id)
    if not book:
        raise ValueError("Book not found.")
    title, authors = (title or "").strip(), (authors or "").strip()
    if not title or not authors:
        raise ValueError("Title and author are required.")
    if total_copies is None:
        total_copies = book["total_copies"]
    issued = book["total_copies"] - book["available_copies"]
    if total_copies < max(issued, 1):
        raise ValueError(
            f"{issued} cop{'y is' if issued == 1 else 'ies are'} currently issued, so "
            f"total copies cannot be less than {max(issued, 1)}.")
    conn.execute(
        """UPDATE Books SET title=?, authors=?, isbn=?, publication_year=?,
                            total_copies=?, available_copies=?
           WHERE book_id=?""",
        (title, authors, (isbn or "").strip() or None, year,
         total_copies, total_copies - issued, book_id))
    conn.commit()


def delete_book(conn, book_id):
    if not get_book(conn, book_id):
        raise ValueError("Book not found.")
    active = conn.execute(
        "SELECT COUNT(*) FROM Issued_Books WHERE book_id=? AND return_date IS NULL",
        (book_id,)).fetchone()[0]
    if active:
        raise ValueError("This book is currently issued and cannot be deleted.")
    history = conn.execute(
        "SELECT COUNT(*) FROM Issued_Books WHERE book_id=?", (book_id,)).fetchone()[0]
    if history:
        raise ValueError(
            "This book has borrowing history, so it cannot be deleted "
            "(the records must stay intact).")
    conn.execute("DELETE FROM Books WHERE book_id=?", (book_id,))
    conn.commit()


def search_books(conn, keyword, limit=50):
    """Search by title, author or ISBN (a number also matches the book ID)."""
    keyword = (keyword or "").strip()
    like = f"%{keyword}%"
    book_id = int(keyword) if keyword.isdigit() else -1
    return _rows(conn.execute(
        """SELECT book_id, title, authors, publication_year, average_rating,
                  available_copies, total_copies
           FROM Books
           WHERE title LIKE ? OR authors LIKE ? OR isbn LIKE ? OR book_id = ?
           ORDER BY (book_id = ?) DESC, average_rating DESC, book_id
           LIMIT ?""", (like, like, like, book_id, book_id, limit)))


def check_availability(conn, book_id):
    book = get_book(conn, book_id)
    if not book:
        raise ValueError("Book not found.")
    next_due = None
    if book["available_copies"] <= 0:
        row = conn.execute(
            """SELECT MIN(due_date) FROM Issued_Books
               WHERE book_id=? AND return_date IS NULL""", (book_id,)).fetchone()
        next_due = row[0]
    return {
        "book_id": book_id,
        "title": book["title"],
        "authors": book["authors"],
        "available": book["available_copies"] > 0,
        "available_copies": book["available_copies"],
        "total_copies": book["total_copies"],
        "next_due_date": next_due,   # earliest date a copy is expected back
    }


# ---------------------------------------------------------------- members

def get_member(conn, member_id):
    row = conn.execute("SELECT * FROM Members WHERE member_id=?", (member_id,)).fetchone()
    return dict(row) if row else None


def _check_member_fields(name, email):
    name, email = (name or "").strip(), (email or "").strip().lower()
    if not name:
        raise ValueError("Member name is required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Please enter a valid email address.")
    return name, email


def add_member(conn, name, email, phone=None):
    name, email = _check_member_fields(name, email)
    try:
        cur = conn.execute(
            "INSERT INTO Members (name, email, phone) VALUES (?,?,?)",
            (name, email, (phone or "").strip() or None))
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError("A member with this email already exists.")


def update_member(conn, member_id, name, email, phone=None):
    if not get_member(conn, member_id):
        raise ValueError("Member not found.")
    name, email = _check_member_fields(name, email)
    try:
        conn.execute(
            "UPDATE Members SET name=?, email=?, phone=? WHERE member_id=?",
            (name, email, (phone or "").strip() or None, member_id))
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("Another member already uses this email.")


def delete_member(conn, member_id):
    if not get_member(conn, member_id):
        raise ValueError("Member not found.")
    active = conn.execute(
        "SELECT COUNT(*) FROM Issued_Books WHERE member_id=? AND return_date IS NULL",
        (member_id,)).fetchone()[0]
    if active:
        raise ValueError("This member still has books issued and cannot be deleted.")
    history = conn.execute(
        "SELECT COUNT(*) FROM Issued_Books WHERE member_id=?", (member_id,)).fetchone()[0]
    if history:
        raise ValueError(
            "This member has borrowing history, so they cannot be deleted "
            "(the records must stay intact).")
    conn.execute("DELETE FROM Members WHERE member_id=?", (member_id,))
    conn.commit()


def list_members(conn, keyword=""):
    like = f"%{(keyword or '').strip()}%"
    return _rows(conn.execute(
        """SELECT member_id, name, email, phone, joined_date
           FROM Members
           WHERE name LIKE ? OR email LIKE ? OR phone LIKE ?
           ORDER BY member_id""", (like, like, like)))


# ---------------------------------------------------- issue / return / fines

def issue_book(conn, book_id, member_id, today=None):
    today = today or date.today()
    book = get_book(conn, book_id)
    if not book:
        raise ValueError("Book not found.")
    if not get_member(conn, member_id):
        raise ValueError("Member not found.")
    if book["available_copies"] <= 0:
        raise ValueError("No copies of this book are available right now.")
    already = conn.execute(
        """SELECT 1 FROM Issued_Books
           WHERE book_id=? AND member_id=? AND return_date IS NULL""",
        (book_id, member_id)).fetchone()
    if already:
        raise ValueError("This member already has this book issued.")

    due = today + timedelta(days=LOAN_DAYS)
    conn.execute(
        """INSERT INTO Issued_Books (book_id, member_id, issue_date, due_date)
           VALUES (?,?,?,?)""",
        (book_id, member_id, today.isoformat(), due.isoformat()))
    conn.execute(
        "UPDATE Books SET available_copies = available_copies - 1 WHERE book_id=?",
        (book_id,))
    conn.commit()
    return due


def return_book(conn, book_id, member_id, today=None):
    today = today or date.today()
    row = conn.execute(
        """SELECT issue_id, due_date FROM Issued_Books
           WHERE book_id=? AND member_id=? AND return_date IS NULL""",
        (book_id, member_id)).fetchone()
    if not row:
        raise ValueError("No active issue found for this book and member.")
    fine = calculate_fine(_to_date(row["due_date"]), today)
    conn.execute(
        "UPDATE Issued_Books SET return_date=?, fine_amount=? WHERE issue_id=?",
        (today.isoformat(), fine, row["issue_id"]))
    conn.execute(
        "UPDATE Books SET available_copies = available_copies + 1 WHERE book_id=?",
        (book_id,))
    conn.commit()
    return fine


# ---------------------------------------------------------------- reports

def currently_issued(conn, today=None):
    """Books that are out right now, with days overdue and fine so far."""
    today = today or date.today()
    rows = _rows(conn.execute(
        """SELECT ib.issue_id, b.book_id, b.title, m.member_id, m.name AS member,
                  m.email, m.phone, ib.issue_date, ib.due_date
           FROM Issued_Books ib
           JOIN Books   b ON b.book_id   = ib.book_id
           JOIN Members m ON m.member_id = ib.member_id
           WHERE ib.return_date IS NULL
           ORDER BY ib.due_date, ib.issue_id"""))
    for r in rows:
        late = (today - _to_date(r["due_date"])).days
        r["days_overdue"] = max(0, late)
        r["fine_so_far"] = r["days_overdue"] * FINE_PER_DAY
    return rows


def overdue_books(conn, today=None):
    """Only the issued books whose due date has passed, worst first."""
    rows = [r for r in currently_issued(conn, today) if r["days_overdue"] > 0]
    return sorted(rows, key=lambda r: -r["days_overdue"])


def member_history(conn, member_id, today=None):
    """Every book the member has ever borrowed (newest first)."""
    today = today or date.today()
    rows = _rows(conn.execute(
        """SELECT ib.issue_id, b.book_id, b.title, b.authors, ib.issue_date,
                  ib.due_date, ib.return_date, ib.fine_amount
           FROM Issued_Books ib
           JOIN Books b ON b.book_id = ib.book_id
           WHERE ib.member_id = ?
           ORDER BY ib.issue_date DESC, ib.issue_id DESC""", (member_id,)))
    for r in rows:
        if r["return_date"] is None:
            late = max(0, (today - _to_date(r["due_date"])).days)
            r["status"] = "Overdue" if late else "Issued"
            r["fine_amount"] = late * FINE_PER_DAY   # running fine, not yet paid
        else:
            r["status"] = "Returned"
    return rows


def stats(conn, today=None):
    one = lambda sql: conn.execute(sql).fetchone()[0]
    issued = currently_issued(conn, today)
    return {
        "titles": one("SELECT COUNT(*) FROM Books"),
        "copies": one("SELECT COALESCE(SUM(total_copies), 0) FROM Books"),
        "members": one("SELECT COUNT(*) FROM Members"),
        "issued": len(issued),
        "overdue": sum(1 for r in issued if r["days_overdue"] > 0),
        "fines_collected": one("SELECT COALESCE(SUM(fine_amount), 0) FROM Issued_Books "
                               "WHERE return_date IS NOT NULL"),
    }


# -------------------------------------------------------------------- CLI

MENU = """
========= Library Management System =========
 BOOKS                         MEMBERS
  1. Add book                   5. Add member
  2. Update book                6. Update member
  3. Delete book                7. Delete member
  4. Search books               8. List members
 ISSUE / RETURN                REPORTS
  9. Issue book                12. Check availability
 10. Return book               13. Currently issued books
 11. Member borrowing history  14. Overdue books
  0. Exit
"""


def ask_int(prompt, default=None):
    while True:
        raw = input(prompt).strip()
        if not raw and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("Please enter a number.")


def ask_text(prompt, current=None):
    """Press Enter to keep the current value when updating."""
    shown = f"{prompt} [{current}]: " if current not in (None, "") else f"{prompt}: "
    raw = input(shown).strip()
    return raw if raw else (current or "")


def print_table(rows, columns, empty="Nothing found."):
    """Print rows as an aligned table so long titles never overlap."""
    if not rows:
        print(empty)
        return
    heads = [c[1] for c in columns]
    data = [[str(r.get(c[0]) if r.get(c[0]) is not None else "-") for c in columns]
            for r in rows]
    widths = [max(len(h), *(len(row[i]) for row in data)) for i, h in enumerate(heads)]
    line = "-+-".join("-" * w for w in widths)
    print(" | ".join(h.ljust(w) for h, w in zip(heads, widths)))
    print(line)
    for row in data:
        print(" | ".join(v.ljust(w) for v, w in zip(row, widths)))
    print(f"({len(rows)} row{'s' if len(rows) != 1 else ''})")


BOOK_COLS = [("book_id", "ID"), ("title", "Title"), ("authors", "Author(s)"),
             ("available_copies", "Avail"), ("total_copies", "Total")]
MEMBER_COLS = [("member_id", "ID"), ("name", "Name"), ("email", "Email"),
               ("phone", "Phone"), ("joined_date", "Joined")]
ISSUED_COLS = [("issue_id", "Issue#"), ("title", "Book"), ("member", "Member"),
               ("issue_date", "Issued"), ("due_date", "Due"),
               ("days_overdue", "Days late"), ("fine_so_far", "Fine (Rs.)")]
HISTORY_COLS = [("title", "Book"), ("issue_date", "Issued"), ("due_date", "Due"),
                ("return_date", "Returned"), ("status", "Status"),
                ("fine_amount", "Fine (Rs.)")]


def main():
    conn = connect()
    while True:
        print(MENU)
        choice = input("Choose: ").strip()
        try:
            if choice == "1":
                year = input("Publication year (optional): ").strip()
                bid = add_book(conn, input("Title: "), input("Author(s): "),
                               input("ISBN (optional): "),
                               int(year) if year.isdigit() else None,
                               ask_int("Copies [3]: ", 3))
                print(f"Book added with ID {bid}.")
            elif choice == "2":
                book = get_book(conn, ask_int("Book ID: "))
                if not book:
                    raise ValueError("Book not found.")
                year = ask_text("Publication year", book["publication_year"])
                update_book(conn, book["book_id"],
                            ask_text("Title", book["title"]),
                            ask_text("Author(s)", book["authors"]),
                            ask_text("ISBN", book["isbn"]),
                            int(year) if str(year).isdigit() else None,
                            ask_int(f"Total copies [{book['total_copies']}]: ",
                                    book["total_copies"]))
                print("Book updated.")
            elif choice == "3":
                delete_book(conn, ask_int("Book ID: "))
                print("Book deleted.")
            elif choice == "4":
                print_table(search_books(conn, input("Search title / author / ISBN: ")),
                            BOOK_COLS)
            elif choice == "5":
                mid = add_member(conn, input("Name: "), input("Email: "),
                                 input("Phone (optional): "))
                print(f"Member added with ID {mid}.")
            elif choice == "6":
                member = get_member(conn, ask_int("Member ID: "))
                if not member:
                    raise ValueError("Member not found.")
                update_member(conn, member["member_id"],
                              ask_text("Name", member["name"]),
                              ask_text("Email", member["email"]),
                              ask_text("Phone", member["phone"]))
                print("Member updated.")
            elif choice == "7":
                delete_member(conn, ask_int("Member ID: "))
                print("Member deleted.")
            elif choice == "8":
                print_table(list_members(conn, input("Filter (Enter for all): ")),
                            MEMBER_COLS, "No members yet.")
            elif choice == "9":
                due = issue_book(conn, ask_int("Book ID: "), ask_int("Member ID: "))
                print(f"Issued. Due on {due}.")
            elif choice == "10":
                fine = return_book(conn, ask_int("Book ID: "), ask_int("Member ID: "))
                print(f"Returned. Fine: Rs. {fine}")
            elif choice == "11":
                mid = ask_int("Member ID: ")
                member = get_member(conn, mid)
                if not member:
                    raise ValueError("Member not found.")
                print(f"Borrowing history of {member['name']}:")
                print_table(member_history(conn, mid), HISTORY_COLS,
                            "This member has not borrowed any book yet.")
            elif choice == "12":
                info = check_availability(conn, ask_int("Book ID: "))
                if info["available"]:
                    print(f"'{info['title']}' is AVAILABLE "
                          f"({info['available_copies']} of {info['total_copies']} copies).")
                else:
                    print(f"'{info['title']}' is NOT available. "
                          f"First copy expected back on {info['next_due_date']}.")
            elif choice == "13":
                print_table(currently_issued(conn), ISSUED_COLS,
                            "No books currently issued.")
            elif choice == "14":
                print_table(overdue_books(conn), ISSUED_COLS, "No overdue books.")
            elif choice == "0":
                break
            else:
                print("Invalid choice.")
        except ValueError as e:
            print(f"Error: {e}")
    conn.close()


if __name__ == "__main__":
    main()
