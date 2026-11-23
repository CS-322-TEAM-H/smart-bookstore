"""Local SQLite storage for the Lumina desktop GUI prototype.

This module is intentionally self-contained so the team can later replace its
functions with calls to the main smart-bookstore backend.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "lumina_demo.sqlite3"


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db():
    with connection() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                role TEXT NOT NULL CHECK(role IN ('RC','VC','SU')),
                balance_cents INTEGER NOT NULL DEFAULT 2000,
                suspended INTEGER NOT NULL DEFAULT 0,
                warning_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS face_profiles (
                user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                profile_path TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, author TEXT NOT NULL,
                category TEXT NOT NULL, year INTEGER NOT NULL,
                price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
                stock INTEGER NOT NULL CHECK(stock >= 0),
                description TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id),
                user_id INTEGER REFERENCES users(id),
                viewed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id),
                user_id INTEGER NOT NULL REFERENCES users(id),
                paid_cents INTEGER NOT NULL,
                fine_cents INTEGER NOT NULL,
                purchased_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL REFERENCES books(id),
                user_id INTEGER REFERENCES users(id),
                guest_name TEXT,
                stars INTEGER NOT NULL CHECK(stars BETWEEN 1 AND 5),
                body TEXT NOT NULL,
                verified INTEGER NOT NULL,
                blocked INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        count = con.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        if not count:
            con.executemany(
                "INSERT INTO books(title, author, category, year, price_cents, stock, description) "
                "VALUES(?,?,?,?,?,?,?)",
                SAMPLE_BOOKS,
            )


SAMPLE_BOOKS = [
    ("Pride and Prejudice", "Jane Austen", "Literature", 1813, 950, 8, "A classic novel about family, pride, and first impressions."),
    ("Frankenstein", "Mary Shelley", "Science Fiction", 1818, 1100, 7, "A scientist creates life and confronts the consequences."),
    ("Alice's Adventures in Wonderland", "Lewis Carroll", "Fantasy", 1865, 800, 10, "Alice discovers a curious world of unusual characters."),
    ("The Adventures of Sherlock Holmes", "Arthur Conan Doyle", "Mystery", 1892, 1250, 6, "Short detective stories starring Sherlock Holmes."),
    ("A Tale of Two Cities", "Charles Dickens", "Literature", 1859, 1050, 9, "A historical novel set in London and Paris."),
    ("The Time Machine", "H. G. Wells", "Science Fiction", 1895, 900, 6, "An inventor travels into a distant future."),
    ("Little Women", "Louisa May Alcott", "Literature", 1868, 900, 6, "Four sisters come of age during the American Civil War."),
    ("The Wonderful Wizard of Oz", "L. Frank Baum", "Fantasy", 1900, 850, 8, "Dorothy journeys through the magical Land of Oz."),
]


def create_user(username, role="RC"):
    username = username.strip()
    if not 3 <= len(username) <= 32:
        raise ValueError("Username must be 3–32 characters.")
    if role not in ("RC", "SU"):
        raise ValueError("Invalid registration role.")
    try:
        with connection() as con:
            cur = con.execute(
                "INSERT INTO users(username,role,created_at) VALUES(?,?,?)",
                (username, role, timestamp()),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as exc:
        raise ValueError("Username already exists.") from exc


def delete_pending_user(user_id):
    with connection() as con:
        if not con.execute("SELECT 1 FROM face_profiles WHERE user_id=?", (user_id,)).fetchone():
            con.execute("DELETE FROM users WHERE id=?", (user_id,))


def set_face_profile(user_id, profile_path):
    with connection() as con:
        con.execute(
            "INSERT INTO face_profiles(user_id,profile_path) VALUES(?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET profile_path=excluded.profile_path",
            (user_id, str(profile_path)),
        )


def get_user(username=None, user_id=None):
    if username is None and user_id is None:
        return None
    sql = "SELECT * FROM users WHERE username=?" if username is not None else "SELECT * FROM users WHERE id=?"
    value = username if username is not None else user_id
    with connection() as con:
        return con.execute(sql, (value,)).fetchone()


def get_face_profile(user_id):
    with connection() as con:
        row = con.execute("SELECT profile_path FROM face_profiles WHERE user_id=?", (user_id,)).fetchone()
        return row["profile_path"] if row else None


def admin_exists():
    with connection() as con:
        return bool(con.execute("SELECT 1 FROM users WHERE role='SU' LIMIT 1").fetchone())


def books(search="", category="All"):
    with connection() as con:
        return con.execute(
            "SELECT * FROM books WHERE (title LIKE ? OR author LIKE ?) "
            "AND (?='All' OR category=?) ORDER BY title",
            (f"%{search}%", f"%{search}%", category, category),
        ).fetchall()


def categories():
    with connection() as con:
        return ["All"] + [r[0] for r in con.execute("SELECT DISTINCT category FROM books ORDER BY category")]


def get_book(book_id):
    with connection() as con:
        return con.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()


def record_view(book_id, user_id=None):
    with connection() as con:
        con.execute("INSERT INTO views(book_id,user_id,viewed_at) VALUES(?,?,?)", (book_id, user_id, timestamp()))


def avg_rating(book_id):
    with connection() as con:
        row = con.execute(
            "SELECT COALESCE(SUM(stars * CASE WHEN verified=1 THEN 2 ELSE 1 END)*1.0 / "
            "NULLIF(SUM(CASE WHEN verified=1 THEN 2 ELSE 1 END),0),0) avg, COUNT(*) n "
            "FROM reviews WHERE book_id=? AND blocked=0", (book_id,),
        ).fetchone()
        return float(row["avg"]), int(row["n"])


def top_books(user_id=None, count=3):
    with connection() as con:
        user = con.execute("SELECT role FROM users WHERE id=?", (user_id,)).fetchone() if user_id else None
        preference = None
        if user and user["role"] in ("RC", "VC"):
            preference = con.execute(
                "SELECT b.category, COUNT(*) n FROM books b "
                "JOIN views v ON v.book_id=b.id WHERE v.user_id=? "
                "GROUP BY b.category ORDER BY n DESC LIMIT 1", (user_id,),
            ).fetchone()
        return con.execute(
            "SELECT b.*, (SELECT COUNT(*) FROM views v WHERE v.book_id=b.id) AS views_count, "
            "(SELECT COUNT(*) FROM purchases p WHERE p.book_id=b.id) AS sales_count "
            "FROM books b ORDER BY "
            "CASE WHEN ? IS NOT NULL AND b.category=? THEN 1 ELSE 0 END DESC, "
            "(views_count + sales_count * 3) DESC, b.id ASC LIMIT ?",
            (preference["category"] if preference else None, preference["category"] if preference else None, count),
        ).fetchall()


def purchase(user_id, book_id):
    """Demo interpretation: insufficient funds completes sale, adds $1 fine, and may suspend."""
    with connection() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        book = con.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if not user or user["role"] not in ("RC", "VC") or user["suspended"] or user["balance_cents"] < 0:
            raise ValueError("An active customer account is required.")
        if not book or book["stock"] < 1:
            raise ValueError("This book is out of stock.")
        price = (book["price_cents"] * 90 + 50) // 100 if user["role"] == "VC" else book["price_cents"]
        fine = 100 if user["balance_cents"] < price else 0
        new_balance = user["balance_cents"] - price - fine
        con.execute("UPDATE books SET stock=stock-1 WHERE id=? AND stock>0", (book_id,))
        con.execute("UPDATE users SET balance_cents=?, suspended=? WHERE id=?", (new_balance, int(new_balance < 0), user_id))
        con.execute(
            "INSERT INTO purchases(user_id,book_id,paid_cents,fine_cents,purchased_at) VALUES(?,?,?,?,?)",
            (user_id, book_id, price, fine, timestamp()),
        )
        counts = con.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(paid_cents),0) AS total FROM purchases WHERE user_id=?", (user_id,),
        ).fetchone()
        if user["role"] == "RC" and (counts["n"] > 3 or counts["total"] > 20000):
            con.execute("UPDATE users SET role='VC' WHERE id=?", (user_id,))
        return {"price_cents": price, "fine_cents": fine, "balance_cents": new_balance, "suspended": new_balance < 0}


def deposit(user_id, amount_cents):
    if amount_cents <= 0:
        raise ValueError("Deposit must be positive.")
    with connection() as con:
        user = con.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
        if not user or user["role"] not in ("RC", "VC") or user["suspended"]:
            raise ValueError("This account requires super-user assistance.")
        con.execute("UPDATE users SET balance_cents=balance_cents+? WHERE id=?", (amount_cents, user_id))


def purchase_history(user_id):
    with connection() as con:
        return con.execute(
            "SELECT p.purchased_at, b.title, p.paid_cents, p.fine_cents FROM purchases p "
            "JOIN books b ON p.book_id=b.id WHERE p.user_id=? ORDER BY p.id DESC",
            (user_id,),
        ).fetchall()


def add_review(book_id, user_id, guest_name, stars, text):
    stars = int(stars)
    if stars not in range(1, 6):
        raise ValueError("Please choose 1–5 stars.")
    if not text.strip():
        raise ValueError("Please enter a short comment.")
    if not user_id and not guest_name.strip():
        raise ValueError("Visitors must enter a nickname.")
    taboo = {"spam", "scam", "idiot"}  # Demo starter list; team will make this SU-editable.
    words = text.split()
    hits = sum(word.strip(".,!?;:\"'()[]").lower() in taboo for word in words)
    masked = " ".join("*" * len(w) if w.strip(".,!?;:\"'()[]").lower() in taboo else w for w in words)
    blocked = hits > 3
    with connection() as con:
        verified = bool(user_id and con.execute(
            "SELECT 1 FROM purchases WHERE user_id=? AND book_id=? LIMIT 1", (user_id, book_id)
        ).fetchone())
        con.execute(
            "INSERT INTO reviews(book_id,user_id,guest_name,stars,body,verified,blocked,created_at) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (book_id, user_id, guest_name or None, stars, masked, int(verified), int(blocked), timestamp()),
        )
        if blocked and user_id:
            user = con.execute("SELECT role,warning_count FROM users WHERE id=?", (user_id,)).fetchone()
            warnings = user["warning_count"] + 1
            new_role = "RC" if user["role"] == "VC" else user["role"]
            suspend = int(user["role"] == "RC" and warnings > 2)
            con.execute(
                "UPDATE users SET warning_count=?, role=?, suspended=MAX(suspended,?) WHERE id=?",
                (warnings, new_role, suspend, user_id),
            )
    return blocked


def reviews_for_book(book_id):
    with connection() as con:
        return con.execute(
            "SELECT COALESCE(u.username, r.guest_name, 'Visitor') reviewer, stars, body "
            "FROM reviews r LEFT JOIN users u ON u.id=r.user_id "
            "WHERE book_id=? AND blocked=0 ORDER BY r.id DESC LIMIT 12",
            (book_id,),
        ).fetchall()


def list_users():
    with connection() as con:
        return con.execute("SELECT id,username,role,balance_cents,suspended FROM users WHERE role!='SU' ORDER BY username").fetchall()


def admin_reopen(user_id, amount_cents):
    with connection() as con:
        user = con.execute("SELECT * FROM users WHERE id=? AND role!='SU'", (user_id,)).fetchone()
        if not user or not user["suspended"]:
            raise ValueError("Select a suspended customer.")
        if amount_cents <= 0 or user["balance_cents"] + amount_cents <= 0:
            raise ValueError("Deposit must make the new balance positive.")
        con.execute("UPDATE users SET balance_cents=balance_cents+?, suspended=0 WHERE id=?", (amount_cents,user_id))


def add_book(title, author, category, year, price_cents, stock):
    if not all([title.strip(), author.strip(), category.strip()]) or not (0 < year <= 2100) or price_cents < 0 or stock < 0:
        raise ValueError("Please enter valid book details.")
    with connection() as con:
        con.execute("INSERT INTO books(title,author,category,year,price_cents,stock) VALUES(?,?,?,?,?,?)",
                    (title.strip(),author.strip(),category.strip(),year,price_cents,stock))


def money(cents):
    return f"${cents / 100:,.2f}"
