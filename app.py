"""Streamlit web app for the Library Management System.

Run:  streamlit run app.py
(All the database logic lives in library.py; this file is only the screens.)
"""
import pandas as pd
import streamlit as st

import library as L

st.set_page_config(page_title="Library Management System", page_icon="📚", layout="wide")

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1400px; }
    h1 { font-weight: 700; letter-spacing: -0.5px; }
    div[data-testid="stMetric"] {
        background: rgba(128,128,128,0.10);
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 14px;
        padding: 16px 20px;
    }
    div[data-testid="stMetricLabel"] p,
    div[data-testid="stMetricValue"] div {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    .stButton > button, .stFormSubmitButton > button {
        border-radius: 10px; font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_conn():
    return L.connect(check_same_thread=False)


conn = get_conn()


# ------------------------------------------------------------ small helpers

def rerun():
    (getattr(st, "rerun", None) or st.experimental_rerun)()


def flash(kind, message):
    """Show a message on the next screen refresh (so tables are up to date)."""
    st.session_state["_flash"] = (kind, message)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        getattr(st, item[0])(item[1])


def col(key, label, width="medium", kind="text"):
    return (key, label, width, kind)


def show_table(rows, cols, empty="Nothing to show."):
    """Full-width table with sensible column widths so nothing is cut off."""
    if not rows:
        st.info(empty)
        return
    df = pd.DataFrame(rows)[[c[0] for c in cols]]
    df.columns = [c[1] for c in cols]
    config = {}
    for _, label, width, kind in cols:
        if kind == "int":
            df[label] = pd.to_numeric(df[label], errors="coerce").astype("Int64")
            config[label] = st.column_config.NumberColumn(label, format="%d", width=width)
        elif kind == "money":
            df[label] = pd.to_numeric(df[label], errors="coerce").fillna(0).astype("Int64")
            config[label] = st.column_config.NumberColumn(label, format="₹%d", width=width)
        elif kind == "rating":
            config[label] = st.column_config.NumberColumn(label, format="%.2f", width=width)
        else:
            df[label] = df[label].fillna("—").astype(str)
            config[label] = st.column_config.TextColumn(label, width=width)
    height = min(42 + 35 * len(df), 620)
    try:
        st.dataframe(df, width="stretch", hide_index=True,
                     column_config=config, height=height)
    except Exception:  # older Streamlit versions
        st.dataframe(df, use_container_width=True, hide_index=True,
                     column_config=config, height=height)


def parse_year(text):
    text = (text or "").strip()
    if not text:
        return None
    if not text.isdigit() or not (0 < int(text) <= 2100):
        raise ValueError("Publication year must be a valid number like 1998.")
    return int(text)


def pick_book(key, label="Search a book by title, author, ISBN or book ID"):
    q = st.text_input(label, key=f"{key}_q", placeholder="e.g. harry potter, rowling, 439023483")
    q = q.strip()
    if not q or (len(q) < 2 and not q.isdigit()):
        st.caption("Type at least 2 characters to search.")
        return None
    results = L.search_books(conn, q, limit=50)
    if not results:
        st.warning("No books found. Try a different spelling.")
        return None
    options = {r["book_id"]: r for r in results}
    if len(results) == 50:
        st.caption("Showing the top 50 matches. Type more of the title to narrow it down.")
    chosen = st.selectbox(
        "Select the book", list(options), key=f"{key}_sel",
        format_func=lambda i: (f"#{i} · {options[i]['title']} — {options[i]['authors']} "
                               f"({options[i]['available_copies']}/{options[i]['total_copies']} available)"))
    return options[chosen]


def pick_member(key, label="Select the member"):
    members = L.list_members(conn)
    if not members:
        st.warning("There are no members yet. Add one on the Members page first.")
        return None
    options = {m["member_id"]: m for m in members}
    chosen = st.selectbox(
        label, list(options), key=key,
        format_func=lambda i: f"#{i} · {options[i]['name']} ({options[i]['email']})")
    return options[chosen]


# ------------------------------------------------------------ table layouts

BOOK_COLS = [
    col("book_id", "ID", "small", "int"),
    col("title", "Title", "large"),
    col("authors", "Author(s)", "large"),
    col("publication_year", "Year", "small", "int"),
    col("average_rating", "Rating", "small", "rating"),
    col("availability", "Availability", "medium"),
]
MEMBER_COLS = [
    col("member_id", "ID", "small", "int"),
    col("name", "Name", "medium"),
    col("email", "Email", "large"),
    col("phone", "Phone", "medium"),
    col("joined_date", "Joined", "medium"),
]
ISSUED_COLS = [
    col("issue_id", "Issue #", "small", "int"),
    col("title", "Book", "large"),
    col("member", "Member", "medium"),
    col("issue_date", "Issued on", "medium"),
    col("due_date", "Due date", "medium"),
    col("days_overdue", "Days late", "small", "int"),
    col("fine_so_far", "Fine", "small", "money"),
]
HISTORY_COLS = [
    col("title", "Book", "large"),
    col("authors", "Author(s)", "large"),
    col("issue_date", "Issued on", "medium"),
    col("due_date", "Due date", "medium"),
    col("return_date", "Returned on", "medium"),
    col("status_label", "Status", "medium"),
    col("fine_amount", "Fine", "small", "money"),
]


# ------------------------------------------------------------------- pages

def page_dashboard():
    st.title("📊 Dashboard")
    show_flash()
    s = L.stats(conn)
    a = st.columns(3)
    a[0].metric("Book titles", f"{s['titles']:,}")
    a[1].metric("Total copies", f"{s['copies']:,}")
    a[2].metric("Members", f"{s['members']:,}")
    b = st.columns(3)
    b[0].metric("Currently issued", f"{s['issued']:,}")
    b[1].metric("Overdue books", f"{s['overdue']:,}")
    b[2].metric("Fines collected", f"₹{s['fines_collected']:,}")

    st.subheader("Overdue books")
    show_table(L.overdue_books(conn)[:10], ISSUED_COLS, "🎉 No overdue books right now.")
    st.subheader("Currently issued (earliest due date first)")
    show_table(L.currently_issued(conn)[:10], ISSUED_COLS, "No books are issued right now.")


def page_search():
    st.title("🔎 Search & Availability")
    show_flash()
    q = st.text_input("Search by title, author, ISBN or book ID", key="search_q",
                      placeholder="e.g. hunger games, rowling, 439023483")
    q = q.strip()
    if not q or (len(q) < 2 and not q.isdigit()):
        st.info(f"Type at least 2 characters to search all {L.stats(conn)['titles']:,} books.")
        return
    rows = L.search_books(conn, q, limit=100)
    if not rows:
        st.warning("No books found. Try a different spelling.")
        return
    for r in rows:
        r["availability"] = (f"🟢 {r['available_copies']} of {r['total_copies']} available"
                             if r["available_copies"] > 0 else "🔴 All copies issued")
    st.caption(f"{len(rows)} result(s){' (top 100 shown)' if len(rows) == 100 else ''}, best rated first.")
    show_table(rows, BOOK_COLS)

    st.subheader("Check availability")
    options = {r["book_id"]: r for r in rows}
    chosen = st.selectbox("Pick a book from the results", list(options), key="avail_sel",
                          format_func=lambda i: f"#{i} · {options[i]['title']}")
    info = L.check_availability(conn, chosen)
    if info["available"]:
        st.success(f"✅ **{info['title']}** is available: "
                   f"{info['available_copies']} of {info['total_copies']} copies on the shelf.")
    else:
        st.warning(f"⏳ **{info['title']}** is not available right now. "
                   f"The first copy is expected back on **{info['next_due_date']}**.")


def page_books():
    st.title("📖 Books")
    show_flash()
    tab_add, tab_update, tab_delete = st.tabs(["➕ Add a book", "✏️ Update a book", "🗑️ Delete a book"])

    with tab_add:
        with st.form("add_book_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            title = c1.text_input("Title *")
            authors = c2.text_input("Author(s) *")
            c3, c4, c5 = st.columns(3)
            isbn = c3.text_input("ISBN (optional)")
            year = c4.text_input("Publication year (optional)")
            copies = c5.number_input("Number of copies", min_value=1, value=3, step=1)
            submitted = st.form_submit_button("Add book", type="primary")
        if submitted:
            try:
                new_id = L.add_book(conn, title, authors, isbn, parse_year(year), int(copies))
                flash("success", f"✅ Book added with ID #{new_id}.")
                rerun()
            except ValueError as e:
                st.error(str(e))

    with tab_update:
        book = pick_book("upd")
        if book:
            full = L.get_book(conn, book["book_id"])
            issued = full["total_copies"] - full["available_copies"]
            lowest = max(issued, 1)
            bid = full["book_id"]
            with st.form(f"update_book_form_{bid}"):
                c1, c2 = st.columns(2)
                title = c1.text_input("Title *", full["title"], key=f"ut_{bid}")
                authors = c2.text_input("Author(s) *", full["authors"], key=f"ua_{bid}")
                c3, c4, c5 = st.columns(3)
                isbn = c3.text_input("ISBN", full["isbn"] or "", key=f"ui_{bid}")
                year = c4.text_input("Publication year", str(full["publication_year"] or ""),
                                     key=f"uy_{bid}")
                copies = c5.number_input("Total copies", min_value=lowest,
                                         value=max(full["total_copies"], lowest), step=1,
                                         key=f"uc_{bid}",
                                         help=f"{issued} copies are issued right now.")
                submitted = st.form_submit_button("Save changes", type="primary")
            if submitted:
                try:
                    L.update_book(conn, bid, title, authors, isbn, parse_year(year), int(copies))
                    flash("success", f"✅ Book #{bid} updated.")
                    rerun()
                except ValueError as e:
                    st.error(str(e))

    with tab_delete:
        book = pick_book("del")
        if book:
            st.warning(f"You are about to delete **#{book['book_id']} · {book['title']}**.")
            sure = st.checkbox("Yes, I want to delete this book", key=f"del_ok_{book['book_id']}")
            if st.button("Delete book", disabled=not sure, key="del_btn"):
                try:
                    L.delete_book(conn, book["book_id"])
                    flash("success", "🗑️ Book deleted.")
                    rerun()
                except ValueError as e:
                    st.error(str(e))


def page_members():
    st.title("👥 Members")
    show_flash()
    tab_all, tab_add, tab_update, tab_delete = st.tabs(
        ["📋 All members", "➕ Add a member", "✏️ Update a member", "🗑️ Delete a member"])

    with tab_all:
        q = st.text_input("Filter by name, email or phone", key="member_filter")
        members = L.list_members(conn, q)
        st.caption(f"{len(members)} member(s)")
        show_table(members, MEMBER_COLS, "No members found.")

    with tab_add:
        with st.form("add_member_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            name = c1.text_input("Full name *")
            email = c2.text_input("Email *")
            phone = c3.text_input("Phone (optional)")
            submitted = st.form_submit_button("Add member", type="primary")
        if submitted:
            try:
                mid = L.add_member(conn, name, email, phone)
                flash("success", f"✅ Member added with ID #{mid}.")
                rerun()
            except ValueError as e:
                st.error(str(e))

    with tab_update:
        member = pick_member("upd_member")
        if member:
            mid = member["member_id"]
            with st.form(f"update_member_form_{mid}"):
                c1, c2, c3 = st.columns(3)
                name = c1.text_input("Full name *", member["name"], key=f"mn_{mid}")
                email = c2.text_input("Email *", member["email"], key=f"me_{mid}")
                phone = c3.text_input("Phone", member["phone"] or "", key=f"mp_{mid}")
                submitted = st.form_submit_button("Save changes", type="primary")
            if submitted:
                try:
                    L.update_member(conn, mid, name, email, phone)
                    flash("success", f"✅ Member #{mid} updated.")
                    rerun()
                except ValueError as e:
                    st.error(str(e))

    with tab_delete:
        member = pick_member("del_member")
        if member:
            st.warning(f"You are about to delete **#{member['member_id']} · {member['name']}**.")
            sure = st.checkbox("Yes, I want to delete this member",
                               key=f"delm_ok_{member['member_id']}")
            if st.button("Delete member", disabled=not sure, key="delm_btn"):
                try:
                    L.delete_member(conn, member["member_id"])
                    flash("success", "🗑️ Member deleted.")
                    rerun()
                except ValueError as e:
                    st.error(str(e))


def page_issue_return():
    st.title("🔁 Issue & Return")
    show_flash()
    tab_issue, tab_return = st.tabs(["📤 Issue a book", "📥 Return a book"])

    with tab_issue:
        st.caption(f"Loan period: {L.LOAN_DAYS} days. Fine: ₹{L.FINE_PER_DAY} per day after the due date.")
        book = pick_book("issue")
        member = pick_member("issue_member", "Issue to which member?")
        if book and member:
            info = L.check_availability(conn, book["book_id"])
            if info["available"]:
                st.success(f"Available: {info['available_copies']} of {info['total_copies']} copies.")
            else:
                st.warning(f"No copy is available. The first one is expected back on "
                           f"{info['next_due_date']}.")
            if st.button("Issue book", type="primary", disabled=not info["available"],
                         key="issue_btn"):
                try:
                    due = L.issue_book(conn, book["book_id"], member["member_id"])
                    flash("success", f"✅ Issued “{book['title']}” to {member['name']}. "
                                     f"Due on {due:%d %b %Y}.")
                    rerun()
                except ValueError as e:
                    st.error(str(e))

    with tab_return:
        member = pick_member("return_member", "Who is returning a book?")
        if member:
            mid = member["member_id"]
            active = [h for h in L.member_history(conn, mid) if h["status"] != "Returned"]
            if not active:
                st.info("This member has no books to return.")
            else:
                options = {h["book_id"]: h for h in active}
                bid = st.selectbox(
                    "Book being returned", list(options), key=f"return_book_{mid}",
                    format_func=lambda i: f"#{i} · {options[i]['title']} (due {options[i]['due_date']})")
                h = options[bid]
                if h["fine_amount"] > 0:
                    st.warning(f"Overdue by {h['fine_amount'] // L.FINE_PER_DAY} day(s). "
                               f"Fine to collect: ₹{h['fine_amount']}")
                else:
                    st.success(f"On time (due {h['due_date']}). No fine.")
                if st.button("Return book", type="primary", key=f"return_btn_{mid}"):
                    try:
                        fine = L.return_book(conn, bid, mid)
                        msg = f"✅ “{h['title']}” returned by {member['name']}."
                        flash("success", msg + (f" Fine collected: ₹{fine}." if fine else " No fine."))
                        rerun()
                    except ValueError as e:
                        st.error(str(e))


def page_issued():
    st.title("📋 Issued & Overdue")
    show_flash()
    tab_issued, tab_overdue = st.tabs(["Currently issued", "⚠️ Overdue"])
    with tab_issued:
        rows = L.currently_issued(conn)
        st.caption(f"{len(rows)} book(s) issued right now, earliest due date first.")
        show_table(rows, ISSUED_COLS, "No books are issued right now.")
    with tab_overdue:
        rows = L.overdue_books(conn)
        st.caption(f"{len(rows)} overdue book(s), longest overdue first. "
                   f"Fine so far = days late × ₹{L.FINE_PER_DAY}.")
        show_table(rows, ISSUED_COLS, "🎉 No overdue books.")


def page_history():
    st.title("🧾 Member History")
    show_flash()
    member = pick_member("hist_member", "Select a member to see their borrowing record")
    if not member:
        return
    rows = L.member_history(conn, member["member_id"])
    icons = {"Returned": "✅ Returned", "Issued": "🟡 Issued", "Overdue": "🔴 Overdue"}
    for r in rows:
        r["status_label"] = icons[r["status"]]
    paid = sum(r["fine_amount"] for r in rows if r["status"] == "Returned")
    pending = sum(r["fine_amount"] for r in rows if r["status"] != "Returned")
    m = st.columns(4)
    m[0].metric("Books borrowed", len(rows))
    m[1].metric("Holding now", sum(1 for r in rows if r["status"] != "Returned"))
    m[2].metric("Fines paid", f"₹{paid:,}")
    m[3].metric("Fines pending", f"₹{pending:,}")
    show_table(rows, HISTORY_COLS, "This member has not borrowed any book yet.")


PAGES = {
    "📊 Dashboard": page_dashboard,
    "🔎 Search & Availability": page_search,
    "📖 Books": page_books,
    "👥 Members": page_members,
    "🔁 Issue & Return": page_issue_return,
    "📋 Issued & Overdue": page_issued,
    "🧾 Member History": page_history,
}

st.sidebar.title("📚 Library")
choice = st.sidebar.radio("Go to", list(PAGES), label_visibility="collapsed")
st.sidebar.caption(f"Loan: {L.LOAN_DAYS} days · Fine: ₹{L.FINE_PER_DAY}/day")
PAGES[choice]()
