"""
Enrollment : 12402080601078
Assignment : 2          Question : Q5
Title      : Tkinter Contact Manager with MySQL Backend

Required packages : pip install mysql-connector-python      (Tkinter ships with Python;
                    on Linux: sudo apt install python3-tk)
Needs             : a running MySQL server

Run:
    python 12402080601078_2_Q5.py

Database configuration (environment variables, all optional)
    CONTACT_DB_HOST      default localhost
    CONTACT_DB_PORT      default 3306
    CONTACT_DB_USER      default root
    CONTACT_DB_PASSWORD  if not set, a hidden password dialog is shown at start
    CONTACT_DB_NAME      default contact_db
The database and the Contact table are created automatically (see schema.sql).

Table  : Contact(id, name, email, phone, category, notes)

Features
    * Create / Update / Delete, duplicate e-mail rejected (message + UNIQUE index)
    * Search by name / email / phone / all, live while typing (debounced)
    * Sorted display (Radiobuttons: name / email / category)
    * Widgets used: Entry, Text, Combobox, Radiobutton, Checkbutton, Listbox, Menu
    * e-mail validated with the syllabus-style regex before insert/update
    * Tools > "Add 10,000 demo contacts" fills the table to prove 10k+ search speed

Search cost (documented as required)
    "Starts with" search uses LIKE 'text%' -> B-tree index -> O(log n + result)
    "Match anywhere" (Checkbutton) uses LIKE '%text%' -> full scan, O(n)
    The list shows at most 1000 rows, so Python memory is O(result size).
"""

import os
import random
import re
import sys

try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
except ImportError:                                           # pragma: no cover
    print("Missing package. Install it with:  pip install mysql-connector-python")
    sys.exit(1)

# ----------------------------------------------------------------- settings
DB_HOST = os.getenv("CONTACT_DB_HOST", "localhost")
DB_PORT = int(os.getenv("CONTACT_DB_PORT", "3306"))
DB_USER = os.getenv("CONTACT_DB_USER", "root")
DB_NAME = os.getenv("CONTACT_DB_NAME", "contact_db")

CATEGORIES = ["Faculty", "Student", "Family", "Friend", "Work", "Other"]
SEARCH_FIELDS = {"All": ("name", "email", "phone"), "Name": ("name",),
                 "Email": ("email",), "Phone": ("phone",)}
SORT_FIELDS = {"name": "name", "email": "email", "category": "category"}   # whitelist
LIST_LIMIT = 1000

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")


# ------------------------------------------------------------- validation
def validate_contact(name, email, phone, category):
    """Return (clean_dict, None) or (None, error_message)."""
    name = " ".join((name or "").split())
    email = (email or "").strip().lower()
    phone = re.sub(r"[\s\-()]", "", phone or "")
    if not name:
        return None, "Name is required."
    if len(name) > 100:
        return None, "Name must be at most 100 characters."
    if not email:
        return None, "Email is required."
    if len(email) > 150 or not EMAIL_RE.match(email):
        return None, "Email is not valid (example: asha@adit.edu)."
    if phone and not PHONE_RE.match(phone):
        return None, "Phone must be 7-15 digits (optional leading +)."
    if category not in CATEGORIES:
        return None, "Please choose a category."
    return {"name": name, "email": email, "phone": phone, "category": category}, None


def like_prefix(term, anywhere=False):
    """Escape LIKE wildcards in the user's text and add the % wildcard(s)."""
    safe = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{safe}%" if anywhere else f"{safe}%"


class DuplicateEmail(Exception):
    pass


# --------------------------------------------------------------- DB layer
class ContactDB:
    """All SQL lives here (parameterized).  No Tkinter code in this class."""

    def __init__(self, password):
        if not DB_NAME_RE.match(DB_NAME):
            raise ValueError("CONTACT_DB_NAME may contain only letters, digits and _")
        self.conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT,
                                            user=DB_USER, password=password)
        cur = self.conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}`")
        cur.execute(f"USE `{DB_NAME}`")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS Contact (
                id        INT AUTO_INCREMENT PRIMARY KEY,
                name      VARCHAR(100) NOT NULL,
                email     VARCHAR(150) NOT NULL,
                phone     VARCHAR(20)  NOT NULL DEFAULT '',
                category  VARCHAR(30)  NOT NULL DEFAULT 'Other',
                notes     TEXT,
                UNIQUE KEY uq_contact_email (email),
                KEY idx_contact_name (name),
                KEY idx_contact_phone (phone)
            )""")
        self.conn.commit()
        cur.close()

    # -- helpers
    @staticmethod
    def _is_duplicate(exc):
        return getattr(exc, "errno", None) == 1062

    # -- CRUD
    def add(self, c, notes):
        cur = self.conn.cursor()
        try:
            cur.execute("INSERT INTO Contact (name, email, phone, category, notes) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (c["name"], c["email"], c["phone"], c["category"], notes))
            self.conn.commit()
            return cur.lastrowid
        except MySQLError as exc:
            self.conn.rollback()
            if self._is_duplicate(exc):
                raise DuplicateEmail(c["email"])
            raise
        finally:
            cur.close()

    def update(self, contact_id, c, notes):
        cur = self.conn.cursor()
        try:
            cur.execute("UPDATE Contact SET name=%s, email=%s, phone=%s, category=%s, "
                        "notes=%s WHERE id=%s",
                        (c["name"], c["email"], c["phone"], c["category"], notes, contact_id))
            self.conn.commit()
        except MySQLError as exc:
            self.conn.rollback()
            if self._is_duplicate(exc):
                raise DuplicateEmail(c["email"])
            raise
        finally:
            cur.close()

    def delete(self, contact_id):
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM Contact WHERE id = %s", (contact_id,))
            self.conn.commit()
        except MySQLError:
            self.conn.rollback()
            raise
        finally:
            cur.close()

    def get(self, contact_id):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT id, name, email, phone, category, notes "
                        "FROM Contact WHERE id = %s", (contact_id,))
            return cur.fetchone()
        finally:
            cur.close()

    def count(self):
        cur = self.conn.cursor()
        try:
            cur.execute("SELECT COUNT(*) FROM Contact")
            return cur.fetchone()[0]
        finally:
            cur.close()

    def search(self, term="", field="All", sort="name", anywhere=False):
        """Return list of (id, name, email, phone, category) - sorted, max LIST_LIMIT."""
        columns = SEARCH_FIELDS.get(field)
        order = SORT_FIELDS.get(sort)
        if columns is None or order is None:           # whitelist, never user text
            raise ValueError("invalid search field or sort column")
        sql = "SELECT id, name, email, phone, category FROM Contact"
        params = []
        term = (term or "").strip()
        if term:
            pattern = like_prefix(term, anywhere)
            sql += " WHERE " + " OR ".join(f"{col} LIKE %s" for col in columns)
            params = [pattern] * len(columns)
        sql += f" ORDER BY {order} ASC, id ASC LIMIT %s"
        params.append(LIST_LIMIT)
        cur = self.conn.cursor()
        try:
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            cur.close()

    def seed_demo(self, how_many=10000):
        """Insert demo contacts in batches (INSERT IGNORE keeps it repeatable)."""
        first = ["Asha", "Dev", "Meera", "Ravi", "Isha", "Karan", "Neha", "Amit", "Riya", "Vivek"]
        last = ["Patel", "Shah", "Mehta", "Joshi", "Desai", "Trivedi", "Modi", "Rana"]
        start = self.count()
        rows = []
        for i in range(start, start + how_many):
            f, l = random.choice(first), random.choice(last)
            rows.append((f"{f} {l}", f"{f}.{l}.{i}@adit.edu".lower(),
                         f"9{random.randint(100000000, 999999999)}",
                         random.choice(CATEGORIES), "demo contact"))
        cur = self.conn.cursor()
        added = 0
        try:
            for i in range(0, len(rows), 2000):
                cur.executemany("INSERT IGNORE INTO Contact (name, email, phone, category, notes) "
                                "VALUES (%s, %s, %s, %s, %s)", rows[i:i + 2000])
                added += max(cur.rowcount, 0)
            self.conn.commit()
        except MySQLError:
            self.conn.rollback()
            raise
        finally:
            cur.close()
        return added

    def close(self):
        try:
            self.conn.close()
        except MySQLError:
            pass


# ------------------------------------------------------------------- GUI
def run_gui():
    import tkinter as tk
    from tkinter import messagebox, simpledialog, ttk

    class ContactApp:
        def __init__(self, root, db):
            self.root, self.db = root, db
            self.selected_id = None
            self.row_ids = []              # listbox index -> contact id
            self._after_id = None

            self.v_name = tk.StringVar()
            self.v_email = tk.StringVar()
            self.v_phone = tk.StringVar()
            self.v_category = tk.StringVar(value=CATEGORIES[0])
            self.v_search = tk.StringVar()
            self.v_field = tk.StringVar(value="All")
            self.v_sort = tk.StringVar(value="name")
            self.v_anywhere = tk.IntVar(value=0)
            self.v_status = tk.StringVar(value="Ready")

            self._build_menu()
            self._build_widgets()
            self.refresh()

        # ---------------------------------------------------- construction
        def _build_menu(self):
            menubar = tk.Menu(self.root)
            file_menu = tk.Menu(menubar, tearoff=0)
            file_menu.add_command(label="Clear form", command=self.clear_form)
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.root.destroy)
            menubar.add_cascade(label="File", menu=file_menu)
            tools = tk.Menu(menubar, tearoff=0)
            tools.add_command(label="Add 10,000 demo contacts", command=self.seed_demo)
            tools.add_command(label="Show all contacts", command=self.show_all)
            menubar.add_cascade(label="Tools", menu=tools)
            self.root.config(menu=menubar)

            self.popup = tk.Menu(self.root, tearoff=0)         # right-click menu on list
            self.popup.add_command(label="Delete contact", command=self.delete_contact)
            self.popup.add_command(label="Clear form", command=self.clear_form)

        def _build_widgets(self):
            self.root.columnconfigure(1, weight=1)
            self.root.rowconfigure(0, weight=1)

            # ---- left: form
            form = ttk.LabelFrame(self.root, text="Contact details", padding=10)
            form.grid(row=0, column=0, sticky="ns", padx=8, pady=8)
            ttk.Label(form, text="Name *").grid(row=0, column=0, sticky="w")
            ttk.Entry(form, textvariable=self.v_name, width=32).grid(row=0, column=1, pady=2)
            ttk.Label(form, text="Email *").grid(row=1, column=0, sticky="w")
            ttk.Entry(form, textvariable=self.v_email, width=32).grid(row=1, column=1, pady=2)
            ttk.Label(form, text="Phone").grid(row=2, column=0, sticky="w")
            ttk.Entry(form, textvariable=self.v_phone, width=32).grid(row=2, column=1, pady=2)
            ttk.Label(form, text="Category").grid(row=3, column=0, sticky="w")
            ttk.Combobox(form, textvariable=self.v_category, values=CATEGORIES,
                         state="readonly", width=29).grid(row=3, column=1, pady=2)
            ttk.Label(form, text="Notes").grid(row=4, column=0, sticky="nw")
            self.t_notes = tk.Text(form, width=32, height=5, wrap="word")
            self.t_notes.grid(row=4, column=1, pady=2)

            buttons = ttk.Frame(form)
            buttons.grid(row=5, column=0, columnspan=2, pady=(10, 0))
            ttk.Button(buttons, text="Add", command=self.add_contact).grid(row=0, column=0, padx=3)
            ttk.Button(buttons, text="Update", command=self.update_contact).grid(row=0, column=1, padx=3)
            ttk.Button(buttons, text="Delete", command=self.delete_contact).grid(row=0, column=2, padx=3)
            ttk.Button(buttons, text="Clear", command=self.clear_form).grid(row=0, column=3, padx=3)

            # ---- right: search + list
            right = ttk.Frame(self.root)
            right.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)
            right.columnconfigure(0, weight=1)
            right.rowconfigure(2, weight=1)

            search = ttk.LabelFrame(right, text="Search", padding=6)
            search.grid(row=0, column=0, sticky="ew")
            search.columnconfigure(0, weight=1)
            entry = ttk.Entry(search, textvariable=self.v_search)
            entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
            entry.bind("<KeyRelease>", self.on_search_typing)       # live search
            entry.bind("<Return>", lambda _e: self.refresh())
            field_box = ttk.Combobox(search, textvariable=self.v_field,
                                     values=list(SEARCH_FIELDS), state="readonly", width=8)
            field_box.grid(row=0, column=1)
            field_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh())
            ttk.Checkbutton(search, text="Match anywhere (slower)", variable=self.v_anywhere,
                            command=self.refresh).grid(row=0, column=2, padx=6)

            sort = ttk.Frame(right)
            sort.grid(row=1, column=0, sticky="w", pady=4)
            ttk.Label(sort, text="Sort by:").grid(row=0, column=0)
            for i, (label, value) in enumerate((("Name", "name"), ("Email", "email"),
                                                ("Category", "category"))):
                ttk.Radiobutton(sort, text=label, value=value, variable=self.v_sort,
                                command=self.refresh).grid(row=0, column=i + 1, padx=4)

            listframe = ttk.Frame(right)
            listframe.grid(row=2, column=0, sticky="nsew")
            listframe.columnconfigure(0, weight=1)
            listframe.rowconfigure(0, weight=1)
            self.listbox = tk.Listbox(listframe, width=95, height=18, exportselection=False,
                                      font="TkFixedFont", activestyle="dotbox")
            self.listbox.grid(row=0, column=0, sticky="nsew")
            scroll = ttk.Scrollbar(listframe, orient="vertical", command=self.listbox.yview)
            scroll.grid(row=0, column=1, sticky="ns")
            self.listbox.config(yscrollcommand=scroll.set)
            self.listbox.bind("<<ListboxSelect>>", self.on_select)
            self.listbox.bind("<Button-3>", self.on_right_click)
            self.listbox.bind("<Button-2>", self.on_right_click)     # macOS

            ttk.Label(right, textvariable=self.v_status, anchor="w").grid(
                row=3, column=0, sticky="ew", pady=(4, 0))

        # ---------------------------------------------------------- helpers
        def read_form(self):
            notes = self.t_notes.get("1.0", "end-1c").strip()
            data, error = validate_contact(self.v_name.get(), self.v_email.get(),
                                           self.v_phone.get(), self.v_category.get())
            return data, notes, error

        def set_form(self, row):
            _id, name, email, phone, category, notes = row
            self.v_name.set(name)
            self.v_email.set(email)
            self.v_phone.set(phone or "")
            self.v_category.set(category if category in CATEGORIES else "Other")
            self.t_notes.delete("1.0", "end")
            self.t_notes.insert("1.0", notes or "")

        def status(self, text):
            self.v_status.set(text)

        def db_error(self, exc):
            messagebox.showerror("Database error", str(exc), parent=self.root)
            self.status("Database error - see message")

        # ----------------------------------------------------------- actions
        def refresh(self, select_id=None):
            try:
                rows = self.db.search(self.v_search.get(), self.v_field.get(),
                                      self.v_sort.get(), bool(self.v_anywhere.get()))
                total = self.db.count()
            except (MySQLError, ValueError) as exc:
                self.db_error(exc)
                return
            self.listbox.delete(0, "end")
            self.row_ids = []
            for cid, name, email, phone, category in rows:
                self.listbox.insert("end", f"{name[:28]:<28} {email[:36]:<36} "
                                           f"{(phone or '')[:15]:<15} {category}")
                self.row_ids.append(cid)
            if select_id in self.row_ids:
                index = self.row_ids.index(select_id)
                self.listbox.selection_set(index)
                self.listbox.see(index)
            self.status(f"Showing {len(rows)} of {total} contacts"
                        + (f" (list limited to {LIST_LIMIT})" if len(rows) == LIST_LIMIT else ""))

        def show_all(self):
            self.v_search.set("")
            self.refresh()

        def on_search_typing(self, _event=None):
            if self._after_id is not None:
                self.root.after_cancel(self._after_id)
            self._after_id = self.root.after(250, self.refresh)      # debounce

        def on_select(self, _event=None):
            sel = self.listbox.curselection()
            if not sel or sel[0] >= len(self.row_ids):
                return
            self.selected_id = self.row_ids[sel[0]]
            try:
                row = self.db.get(self.selected_id)
            except MySQLError as exc:
                self.db_error(exc)
                return
            if row:
                self.set_form(row)
                self.status(f"Selected contact #{self.selected_id}")

        def on_right_click(self, event):
            index = self.listbox.nearest(event.y)
            if 0 <= index < len(self.row_ids):
                self.listbox.selection_clear(0, "end")
                self.listbox.selection_set(index)
                self.on_select()
                try:
                    self.popup.tk_popup(event.x_root, event.y_root)
                finally:
                    self.popup.grab_release()

        def clear_form(self):
            self.selected_id = None
            self.v_name.set("")
            self.v_email.set("")
            self.v_phone.set("")
            self.v_category.set(CATEGORIES[0])
            self.t_notes.delete("1.0", "end")
            self.listbox.selection_clear(0, "end")
            self.status("Form cleared")

        def add_contact(self):
            data, notes, error = self.read_form()
            if error:
                messagebox.showwarning("Invalid input", error, parent=self.root)
                return
            try:
                new_id = self.db.add(data, notes)
            except DuplicateEmail:
                messagebox.showwarning("Duplicate email",
                                       "A contact with this email already exists.",
                                       parent=self.root)
                return
            except MySQLError as exc:
                self.db_error(exc)
                return
            self.selected_id = new_id
            self.v_search.set("")
            self.refresh(select_id=new_id)
            self.status(f"Record inserted: {data['name']} <{data['email']}>")

        def update_contact(self):
            if self.selected_id is None:
                messagebox.showinfo("Update", "Select a contact from the list first.",
                                    parent=self.root)
                return
            data, notes, error = self.read_form()
            if error:
                messagebox.showwarning("Invalid input", error, parent=self.root)
                return
            try:
                self.db.update(self.selected_id, data, notes)
            except DuplicateEmail:
                messagebox.showwarning("Duplicate email",
                                       "Another contact already uses this email.",
                                       parent=self.root)
                return
            except MySQLError as exc:
                self.db_error(exc)
                return
            self.refresh(select_id=self.selected_id)
            self.status(f"Record updated: {data['name']}")

        def delete_contact(self):
            if self.selected_id is None:
                messagebox.showinfo("Delete", "Select a contact from the list first.",
                                    parent=self.root)
                return
            if not messagebox.askyesno("Delete", "Delete the selected contact?",
                                       parent=self.root):
                return
            try:
                self.db.delete(self.selected_id)
            except MySQLError as exc:
                self.db_error(exc)
                return
            self.clear_form()
            self.refresh()
            self.status("Record deleted")

        def seed_demo(self):
            try:
                added = self.db.seed_demo(10000)
            except MySQLError as exc:
                self.db_error(exc)
                return
            self.refresh()
            self.status(f"{added} demo contacts added")

    # ------------------------------------------------------------ start-up
    root = tk.Tk()
    root.title("Contact Manager - 12402080601078")
    root.withdraw()
    password = os.getenv("CONTACT_DB_PASSWORD")
    if password is None:
        password = simpledialog.askstring("MySQL login", f"Password for {DB_USER}@{DB_HOST}:",
                                          show="*", parent=root)
        if password is None:                 # dialog cancelled
            root.destroy()
            return
    try:
        db = ContactDB(password)
    except (MySQLError, ValueError) as exc:
        messagebox.showerror("Cannot connect to MySQL", str(exc), parent=root)
        root.destroy()
        return
    root.deiconify()
    ContactApp(root, db)
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
    db.close()


if __name__ == "__main__":
    run_gui()
