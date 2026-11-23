"""Lumina Smart Bookstore - clean Tkinter GUI prototype for Group H.

Run: python app.py
To enroll a local super-user: python app.py --create-admin
Registration/login: username + actual camera face scan (no passwords).
This is a prototype, not a production biometric authentication system.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

import database as db
from face_auth import FaceAuthError, enroll, verify

BASE_DIR = Path(__file__).resolve().parent
FACE_DIR = BASE_DIR / "data" / "faces"
BG = "#f2f2f2"
WHITE = "#ffffff"
TEXT = "#202124"
MUTED = "#667078"
BLUE = "#087ccc"
GREEN = "#20a64b"
TEAL = "#00a5b5"
DARK = "#555d64"


def to_cents(value):
    try:
        amount = Decimal(str(value).replace("$", "").strip())
        if not amount.is_finite() or amount <= 0:
            raise ValueError
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Enter a valid positive amount, such as 10.00.") from exc


class LuminaApp(tk.Tk):
    def __init__(self):
        super().__init__()
        db.init_db()
        self.user_id = None
        self.title("Lumina Smart Bookstore - Group H")
        self.geometry("970x675")
        self.minsize(825, 585)
        self.configure(bg=BG)
        self.font = ("Segoe UI", 11)
        self.heading = ("Segoe UI", 23, "bold")
        self.section_font = ("Segoe UI", 13, "bold")
        self._configure_tree()
        self.show_home()

    def _configure_tree(self):
        s = ttk.Style(self)
        s.configure("Lumina.Treeview", font=("Segoe UI", 10), rowheight=29)
        s.configure("Lumina.Treeview.Heading", font=("Segoe UI", 10, "bold"))

    def user(self):
        return db.get_user(user_id=self.user_id) if self.user_id else None

    def role(self):
        user = self.user()
        return user["role"] if user else "VS"

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._header()
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=30, pady=18)

    def _header(self):
        bar = tk.Frame(self, bg=WHITE, height=54, highlightbackground="#e2e2e2", highlightthickness=1)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(bar, text="Lumina  |  Smart Bookstore", font=("Segoe UI", 13, "bold"), bg=WHITE, fg=TEXT).pack(side="left", padx=20)
        right = tk.Frame(bar, bg=WHITE)
        right.pack(side="right", padx=14)
        self._nav_button(right, "Home", self.show_home)
        self._nav_button(right, "Browse Books", self.show_catalog)
        user = self.user()
        if user:
            self._nav_button(right, "My Account" if user["role"] != "SU" else "Admin", self.show_account)
            self._nav_button(right, "Logout", self.logout)
        else:
            self._nav_button(right, "Login", self.show_login)

    def _nav_button(self, parent, label, action):
        tk.Button(parent, text=label, command=action, relief="flat", bg=WHITE, fg=DARK,
                  activebackground="#edf3f8", activeforeground=TEXT,
                  font=("Segoe UI", 9), padx=10, pady=9, cursor="hand2", bd=0).pack(side="left", padx=1)

    def button(self, parent, label, action, color=BLUE, width=18, **pack):
        b = tk.Button(parent, text=label, command=action, bg=color, fg=WHITE,
                      activebackground=color, activeforeground=WHITE,
                      font=("Segoe UI", 10, "bold"), bd=0, relief="flat",
                      padx=14, pady=10, width=width, cursor="hand2")
        if pack:
            b.pack(**pack)
        return b

    def label(self, parent, text, size=11, bold=False, fg=TEXT, bg=BG, **pack):
        widget = tk.Label(parent, text=text, font=("Segoe UI", size, "bold" if bold else "normal"),
                          fg=fg, bg=bg, justify="center", **pack)
        return widget

    def title_label(self, parent, heading, subtext=""):
        self.label(parent, heading, 23, True).pack(pady=(11, 9))
        if subtext:
            self.label(parent, subtext, 10, fg=MUTED).pack(pady=(0, 22))

    def show_home(self):
        self.clear()
        user = self.user()
        welcome = f"Welcome back, {user['username']}" if user else "Welcome to Lumina"
        self.title_label(self.body, welcome, "A simple AI-enabled bookstore for exploring, purchasing and reviewing books.")
        panels = tk.Frame(self.body, bg=BG)
        panels.pack(fill="x", padx=25, pady=(20, 28))
        picks = db.top_books(self.user_id, 3)
        names = ("Recommended Book 1", "Recommended Book 2", "Recommended Book 3")
        for i, book in enumerate(picks):
            card = tk.Frame(panels, bg=BG, width=245, height=146)
            card.pack(side="left", expand=True, fill="x", padx=8)
            card.pack_propagate(False)
            self.label(card, names[i], 12, True, fg=DARK).pack(pady=(7, 20))
            self.label(card, book["title"], 11, True, wraplength=220).pack()
            self.label(card, f"{book['author']}  |  {db.money(book['price_cents'])}", 9, fg=MUTED).pack(pady=4)

        actions = tk.Frame(self.body, bg=BG)
        actions.pack(pady=(6, 6))
        self.button(actions, "Browse Books", self.show_catalog, BLUE, width=19).pack(pady=10)
        if user:
            self.button(actions, "My Account" if user["role"] != "SU" else "Admin Panel",
                        self.show_account, GREEN, width=19).pack(pady=10)
            self.button(actions, "Logout", self.logout, TEAL, width=19).pack(pady=10)
        else:
            self.button(actions, "Login", self.show_login, GREEN, width=19).pack(pady=10)
            self.button(actions, "Register", self.show_register, TEAL, width=19).pack(pady=10)

    def _auth_form(self, heading, subtitle, button_text, submit):
        self.clear()
        self.title_label(self.body, heading, subtitle)
        form = tk.Frame(self.body, bg=BG)
        form.pack(pady=(65, 4))
        self.label(form, "Username", 11, True).pack(pady=(0, 10))
        entry = tk.Entry(form, font=("Segoe UI", 12), width=39, relief="solid", bd=1,
                         highlightbackground="#c8ccd0", highlightthickness=1)
        entry.pack(ipady=8, pady=(0, 13))
        entry.focus_set()
        entry.bind("<Return>", lambda e: submit(entry.get()))
        self.label(form, "A webcam scan is required. No password or PIN.", 9, fg=MUTED).pack(pady=(0, 18))
        self.button(form, button_text, lambda: submit(entry.get()), GREEN, width=22).pack(pady=7)
        self.button(form, "Back", self.show_home, DARK, width=16).pack(pady=10)
        return form

    def show_login(self):
        self._auth_form("Login to Lumina", "Sign in using your username and registered face.",
                        "Scan Face & Login", self._login)
        self.label(self.body, "New here? Choose Register from the Home page.", 10, fg=MUTED).pack(pady=12)

    def show_register(self):
        self._auth_form("Register for Lumina", "Create a customer account with a face scan.",
                        "Capture Face & Register", self._register_user)
        self.label(self.body, "Please allow camera access and press Q to cancel the camera scan.", 9, fg=MUTED).pack(pady=12)

    def _register_user(self, username):
        username = username.strip()
        if len(username) < 3:
            messagebox.showerror("Username", "Enter a username of at least 3 characters.", parent=self)
            return
        if not messagebox.askokcancel("Face enrollment", "The camera will capture 12 face samples.\nContinue?", parent=self):
            return
        user_id = None
        try:
            user_id = db.create_user(username, "RC")
            profile = enroll(user_id, FACE_DIR)
            db.set_face_profile(user_id, profile)
        except (ValueError, FaceAuthError) as exc:
            if user_id:
                db.delete_pending_user(user_id)
            messagebox.showerror("Registration failed", str(exc), parent=self)
            return
        except Exception as exc:
            if user_id:
                db.delete_pending_user(user_id)
            messagebox.showerror("Registration failed", f"Unexpected error: {exc}", parent=self)
            return
        self.user_id = user_id
        messagebox.showinfo("Registered", "Your customer account and face profile were saved.", parent=self)
        self.show_home()

    def _login(self, username):
        user = db.get_user(username=username.strip())
        if not user:
            messagebox.showerror("Login failed", "Username not found.", parent=self)
            return
        if user["suspended"] or user["balance_cents"] < 0:
            messagebox.showerror("Account suspended", "Ask the super-user to deposit funds and reopen your account.", parent=self)
            return
        profile = db.get_face_profile(user["id"])
        if not profile:
            messagebox.showerror("Login failed", "No face profile is enrolled for this account.", parent=self)
            return
        try:
            match, score = verify(profile)
        except FaceAuthError as exc:
            messagebox.showerror("Camera error", str(exc), parent=self)
            return
        if not match:
            messagebox.showerror("Face not recognized", "Face did not match the enrolled profile. Please try again.", parent=self)
            return
        self.user_id = user["id"]
        messagebox.showinfo("Signed in", f"Welcome, {user['username']}!", parent=self)
        self.show_home()

    def logout(self):
        self.user_id = None
        self.show_home()

    def show_catalog(self):
        self.clear()
        self.title_label(self.body, "Browse Books", "Search titles or authors, and select a book to view its details.")
        filters = tk.Frame(self.body, bg=BG)
        filters.pack(fill="x", padx=22, pady=(0, 14))
        self.query_var = tk.StringVar()
        self.category_var = tk.StringVar(value="All")
        tk.Entry(filters, textvariable=self.query_var, font=self.font, width=34, bd=1, relief="solid").pack(side="left", padx=(0, 12), ipady=6)
        category = ttk.Combobox(filters, textvariable=self.category_var, state="readonly", values=db.categories(), width=20)
        category.pack(side="left", padx=(0, 12))
        category.bind("<<ComboboxSelected>>", lambda e: self._load_catalog())
        self.button(filters, "Search", self._load_catalog, BLUE, width=9).pack(side="left")
        self.query_var.trace_add("write", lambda *_: None)

        tableframe = tk.Frame(self.body, bg=BG)
        tableframe.pack(fill="both", expand=True, padx=22)
        cols = ("title", "author", "category", "year", "price", "stock")
        tree = ttk.Treeview(tableframe, columns=cols, show="headings", height=9, style="Lumina.Treeview", selectmode="browse")
        for key, text, width in [
            ("title", "Title", 250), ("author", "Author", 180), ("category", "Category", 145),
            ("year", "Year", 65), ("price", "Price", 80), ("stock", "Stock", 65)
        ]:
            tree.heading(key, text=text)
            tree.column(key, width=width, anchor="center" if key in ("year", "price", "stock") else "w")
        scroll = ttk.Scrollbar(tableframe, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        tree.bind("<Double-1>", lambda e: self._open_selected_book())
        self.catalog_tree = tree
        controls = tk.Frame(self.body, bg=BG)
        controls.pack(pady=18)
        self.button(controls, "View Book Details", self._open_selected_book, GREEN, width=17).pack(side="left", padx=8)
        self.button(controls, "Back", self.show_home, DARK, width=12).pack(side="left", padx=8)
        self._load_catalog()

    def _load_catalog(self):
        for item in self.catalog_tree.get_children():
            self.catalog_tree.delete(item)
        for book in db.books(self.query_var.get().strip(), self.category_var.get()):
            self.catalog_tree.insert("", "end", iid=str(book["id"]),
                                     values=(book["title"], book["author"], book["category"],
                                             book["year"], db.money(book["price_cents"]), book["stock"]))

    def _open_selected_book(self):
        selected = self.catalog_tree.selection()
        if not selected:
            messagebox.showinfo("Choose a book", "Select a book in the list first.", parent=self)
            return
        self.show_book(int(selected[0]))

    def show_book(self, book_id):
        book = db.get_book(book_id)
        if not book:
            messagebox.showerror("Not found", "Book no longer exists.", parent=self)
            self.show_catalog()
            return
        db.record_view(book_id, self.user_id)
        rating, count = db.avg_rating(book_id)
        self.clear()
        panel = tk.Frame(self.body, bg=BG)
        panel.pack(expand=True, pady=15)
        self.label(panel, book["title"], 21, True, wraplength=760).pack(pady=(0, 12))
        self.label(panel, f"By {book['author']}  •  {book['category']}  •  {book['year']}", 11, fg=MUTED).pack(pady=4)
        self.label(panel, f"Price: {db.money(book['price_cents'])}       In stock: {book['stock']}", 12, True).pack(pady=15)
        self.label(panel, book["description"] or "No description available.", 10, wraplength=720).pack(pady=8)
        self.label(panel, f"Weighted rating: {rating:.1f}/5  ({count} reviews)", 10, fg=DARK).pack(pady=8)
        actions = tk.Frame(panel, bg=BG)
        actions.pack(pady=16)
        self.button(actions, "Buy Book", lambda: self._buy(book_id), GREEN, width=14).pack(side="left", padx=8)
        self.button(actions, "Rate / Comment", lambda: self._review(book_id), TEAL, width=14).pack(side="left", padx=8)
        self.button(actions, "Back to Catalog", self.show_catalog, DARK, width=16).pack(side="left", padx=8)
        tk.Label(panel, text="Recent reviews", bg=BG, fg=DARK, font=self.section_font).pack(pady=(22, 5))
        items = db.reviews_for_book(book_id)
        if not items:
            self.label(panel, "No reviews yet.", 10, fg=MUTED).pack()
        for r in items[:3]:
            self.label(panel, f"{r['reviewer']}  •  {r['stars']} stars  —  {r['body'][:110]}", 9, wraplength=780).pack(pady=3)

    def _buy(self, book_id):
        user = self.user()
        if not user or user["role"] not in ("RC", "VC"):
            messagebox.showinfo("Login required", "Please log in as a customer to purchase books.", parent=self)
            return
        book = db.get_book(book_id)
        price = (book["price_cents"]*90+50)//100 if user["role"] == "VC" else book["price_cents"]
        fine_note = "\nYour balance is insufficient. A $1 fine applies and your account may be suspended." if user["balance_cents"] < price else ""
        if not messagebox.askyesno("Confirm purchase", f"Buy {book['title']} for {db.money(price)}?{fine_note}", parent=self):
            return
        try:
            result = db.purchase(user["id"], book_id)
        except ValueError as exc:
            messagebox.showerror("Purchase error", str(exc), parent=self)
            return
        text = f"Purchase recorded.\nPrice: {db.money(result['price_cents'])}\nFine: {db.money(result['fine_cents'])}\nBalance: {db.money(result['balance_cents'])}"
        if result["suspended"]:
            text += "\n\nAccount suspended. Contact your super-user."
            self.user_id = None
        messagebox.showinfo("Purchase result", text, parent=self)
        self.show_home() if result["suspended"] else self.show_book(book_id)

    def _review(self, book_id):
        star = simpledialog.askinteger("Rate book", "Stars (1 to 5):", minvalue=1, maxvalue=5, parent=self)
        if star is None:
            return
        comment = simpledialog.askstring("Comment", "Write a short review:", parent=self)
        if comment is None:
            return
        guest_name = ""
        if not self.user_id:
            guest_name = simpledialog.askstring("Visitor name", "Enter a nickname:", parent=self) or ""
        try:
            blocked = db.add_review(book_id, self.user_id, guest_name, star, comment)
        except ValueError as exc:
            messagebox.showerror("Review error", str(exc), parent=self)
            return
        messagebox.showinfo("Review status", "Review blocked: too many taboo words." if blocked else "Review posted.", parent=self)
        user = self.user()
        if user and user["suspended"]:
            self.user_id = None
        self.show_book(book_id)

    def show_account(self):
        user = self.user()
        if not user:
            self.show_login()
            return
        if user["role"] == "SU":
            self.show_admin()
            return
        self.clear()
        self.title_label(self.body, "My Account", f"{user['username']}  •  {'VIP Customer' if user['role']=='VC' else 'Registered Customer'}")
        self.label(self.body, f"Wallet Balance: {db.money(user['balance_cents'])}", 17, True).pack(pady=(10, 12))
        self.button(self.body, "Deposit Demo Money", self._deposit, GREEN, width=20).pack(pady=7)
        self.label(self.body, "Purchase History", 13, True, fg=DARK).pack(pady=(26, 10))
        rows = db.purchase_history(user["id"])
        history = ttk.Treeview(self.body, columns=("date", "title", "price", "fine"), show="headings", height=8, style="Lumina.Treeview")
        for col, display, wid in [("date","Date",190),("title","Book",310),("price","Paid",90),("fine","Fine",90)]:
            history.heading(col, text=display)
            history.column(col, width=wid)
        for item in rows:
            history.insert("", "end", values=(item["purchased_at"][:16].replace("T", " "),
                                                       item["title"],db.money(item["paid_cents"]),db.money(item["fine_cents"])))
        history.pack(fill="x", padx=35, pady=5)
        self.button(self.body, "Back", self.show_home, DARK, width=14).pack(pady=16)

    def _deposit(self):
        user = self.user()
        amount = simpledialog.askstring("Demo Wallet", "Deposit amount ($):", parent=self)
        if amount is None:
            return
        try:
            db.deposit(user["id"], to_cents(amount))
        except ValueError as exc:
            messagebox.showerror("Deposit error", str(exc), parent=self)
            return
        messagebox.showinfo("Deposit", "Demo money added successfully.", parent=self)
        self.show_account()

    def show_admin(self):
        if self.role() != "SU":
            messagebox.showerror("Access denied", "Super-user access required.", parent=self)
            self.show_home()
            return
        self.clear()
        self.title_label(self.body, "Super-user Panel", "Basic catalog and suspended-account management for the prototype.")
        controls = tk.Frame(self.body, bg=BG)
        controls.pack(pady=(8, 23))
        self.button(controls, "Add Book", self._admin_add_book, BLUE, width=15).pack(side="left", padx=9)
        self.button(controls, "Reopen Account", self._admin_reopen, GREEN, width=16).pack(side="left", padx=9)
        self.button(controls, "Back", self.show_home, DARK, width=12).pack(side="left", padx=9)
        self.label(self.body, "Customer Accounts", 12, True).pack(pady=(10, 10))
        table = ttk.Treeview(self.body, columns=("id","name","role","balance","status"), show="headings", style="Lumina.Treeview", height=12)
        for col, heading, width in [("id","ID",65),("name","Username",210),("role","Role",85),("balance","Balance",130),("status","Status",150)]:
            table.heading(col, text=heading)
            table.column(col, width=width, anchor="center" if col!="name" else "w")
        for user in db.list_users():
            table.insert("", "end", values=(user["id"],user["username"],user["role"],
                                            db.money(user["balance_cents"]),"Suspended" if user["suspended"] else "Active"))
        table.pack(fill="x", padx=35)

    def _admin_add_book(self):
        if self.role() != "SU":
            return
        fields = ["Title", "Author", "Category", "Publication year", "Price ($)", "Stock"]
        values = []
        for field in fields:
            value = simpledialog.askstring("Add Book", field + ":", parent=self)
            if value is None:
                return
            values.append(value)
        try:
            db.add_book(values[0], values[1], values[2], int(values[3]), to_cents(values[4]), int(values[5]))
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid book", str(exc), parent=self)
            return
        messagebox.showinfo("Book added", "The catalog has been updated.", parent=self)
        self.show_admin()

    def _admin_reopen(self):
        if self.role() != "SU":
            return
        identifier = simpledialog.askinteger("Reopen Account", "Customer ID (see account table):", parent=self)
        if identifier is None:
            return
        amount = simpledialog.askstring("Reopen Account", "Deposit amount ($):", parent=self)
        if amount is None:
            return
        try:
            db.admin_reopen(identifier, to_cents(amount))
        except ValueError as exc:
            messagebox.showerror("Could not reopen", str(exc), parent=self)
            return
        messagebox.showinfo("Reopened", "Account balance is positive and suspension cleared.", parent=self)
        self.show_admin()


def create_admin():
    db.init_db()
    if db.admin_exists():
        print("An SU account already exists. Do not enroll a second one with this prototype.")
        return
    username = input("Choose super-user username (no password): ").strip()
    user_id = None
    try:
        user_id = db.create_user(username, "SU")
        print("Opening camera. Look at the camera; press Q to cancel.")
        profile = enroll(user_id, FACE_DIR)
        db.set_face_profile(user_id, profile)
        print(f"Super-user '{username}' enrolled. Run: python app.py")
    except (ValueError, FaceAuthError) as exc:
        if user_id:
            db.delete_pending_user(user_id)
        print(f"Setup failed: {exc}")


def main():
    parser = argparse.ArgumentParser(description="Lumina Smart Bookstore GUI prototype")
    parser.add_argument("--create-admin", action="store_true", help="Enroll the first SU using the webcam")
    args = parser.parse_args()
    if args.create_admin:
        create_admin()
    else:
        app = LuminaApp()
        app.mainloop()


if __name__ == "__main__":
    main()
