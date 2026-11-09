import os
from dotenv import load_dotenv
load_dotenv()
"""
Online Student Attendance Management System
-------------------------------------------
Software Engineering Project  |  Python (Tkinter) + MySQL

Roles:
  * Admin   -> students, teachers, courses, enrollments, reports
  * Teacher -> mark attendance, approve/reject leave requests, course reports
  * Student -> own attendance %, history, leave requests

Run:
    pip install mysql-connector-python
    python attendance_system.py

Demo logins (from the SQL script):
    admin    / admin123
    teacher1 / teacher123
    student1 / student123
"""

import csv
import datetime as dt
import functools
import hashlib
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import mysql.connector

# ============================================================
#  CONFIG  -> sirf yahan apna MySQL password likho
# ============================================================
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password":  os.getenv("DB_PASSWORD"),   # <-- apna MySQL root password yahan likho
    "database": "attendance_db",
}
MIN_ATTENDANCE = 75.0   # is se kam percentage = LOW attendance

# ---------- colors (colourful theme) ----------
PRIMARY = "#4F46E5"        # indigo
ACCENT = "#10B981"         # green
DANGER = "#EF4444"         # red
BG = "#EEF1FB"             # soft lavender background
TEXT = "#1F2937"
MUTED = "#6B7280"
SIDEBAR = "#1E1B4B"        # dark indigo sidebar
SIDEBAR_HOVER = "#312E81"
SIDEBAR_ACTIVE = "#4F46E5"
FONT = "Segoe UI"


# ============================================================
#  DATABASE HELPERS
# ============================================================
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def query(sql, params=()):
    """SELECT chalao aur saari rows wapas lo."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()


def execute(sql, params=()):
    """INSERT / UPDATE / DELETE chalao."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        conn.commit()
        last_id = cur.lastrowid
        cur.close()
        return last_id
    finally:
        conn.close()


def run_transaction(steps):
    """steps = [(sql, params), ...] -> sab ek saath chalte hain, ya koi nahi."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        for sql, params in steps:
            cur.execute(sql, params)
        conn.commit()
        cur.close()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def hash_password(password):
    # MySQL ke SHA2(password, 256) jaisa hi hash
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def safe(fn):
    """Database errors par app crash hone ki jagah message box dikhao."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except mysql.connector.IntegrityError as e:
            messagebox.showerror(
                "Error",
                "Ye data pehle se maujood hai ya kisi aur record se juda hua hai.\n\n" + str(e.msg),
            )
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", str(e))
    return wrapper


# ============================================================
#  SMALL UTILITIES
# ============================================================
def parse_date(text):
    try:
        return dt.datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def combo_id(text):
    """'3 - Something' -> 3"""
    return int(text.split(" - ")[0])


def set_combo(cb, values, default_index=0):
    """Combobox ki list update karo, purani selection bachao agar maujood ho."""
    current = cb.get()
    cb["values"] = values
    if current in values:
        cb.set(current)
    elif values:
        cb.current(default_index)
    else:
        cb.set("")


def make_form(parent, fields, per_row=3, width=22):
    """fields = [(label, key, is_secret)] -> {key: Entry}"""
    entries = {}
    for i, (label, key, secret) in enumerate(fields):
        r, c = divmod(i, per_row)
        ttk.Label(parent, text=label).grid(row=r * 2, column=c, sticky="w", padx=6)
        e = ttk.Entry(parent, width=width, show="*" if secret else "")
        e.grid(row=r * 2 + 1, column=c, padx=6, pady=(0, 8), sticky="w")
        entries[key] = e
    return entries


def form_values(entries):
    out = {}
    for key, e in entries.items():
        val = e.get()
        out[key] = val if "password" in key else val.strip()
    return out


def clear_form(entries):
    for e in entries.values():
        e.delete(0, "end")


# ---------- attendance summary (percentage) ----------
SUMMARY_SQL = """
SELECT s.roll_no, s.full_name, c.course_code, c.course_name,
       COUNT(a.attendance_id) AS total,
       COALESCE(SUM(a.status IN ('Present','Late')), 0) AS attended
FROM enrollments e
JOIN students s ON s.student_id = e.student_id
JOIN courses  c ON c.course_id  = e.course_id
LEFT JOIN attendance a ON a.student_id = e.student_id AND a.course_id = e.course_id
{where}
GROUP BY s.student_id, c.course_id
ORDER BY c.course_code, s.roll_no
"""

SUMMARY_COLS = ("Roll No", "Student", "Code", "Course", "Total", "Attended", "Percentage", "Status")
SUMMARY_WIDTHS = (90, 170, 80, 200, 70, 80, 100, 100)


def summary_rows(where="", params=(), low_only=False):
    rows = query(SUMMARY_SQL.format(where=where), params)
    out = []
    for roll, name, code, cname, total, attended in rows:
        total, attended = int(total), int(attended)
        pct = round(attended * 100 / total, 2) if total else 0.0
        if total == 0:
            status = "No classes"
        elif pct < MIN_ATTENDANCE:
            status = "LOW"
        else:
            status = "OK"
        if low_only and status != "LOW":
            continue
        out.append((roll, name, code, cname, total, attended, f"{pct:.2f}%", status))
    return out


def low_tag(row):
    return ("low",) if row[-1] == "LOW" else ()


# ============================================================
#  STYLE + GRADIENT HELPERS
# ============================================================
def setup_style(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(FONT, 10), background=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("TLabelframe", background=BG)
    style.configure("TLabelframe.Label", background=BG, foreground=PRIMARY, font=(FONT, 10, "bold"))
    style.configure("TCheckbutton", background=BG)
    # tabs are hidden: the left sidebar is used for navigation instead
    style.layout("Hidden.TNotebook.Tab", [])
    style.configure("Hidden.TNotebook", background=BG, borderwidth=0, tabmargins=0)
    style.configure("Treeview", rowheight=28, font=(FONT, 10), fieldbackground="white")
    style.configure("Treeview.Heading", font=(FONT, 10, "bold"), background=PRIMARY, foreground="white")
    style.map("Treeview.Heading", background=[("active", "#4338CA")])
    style.map("Treeview", background=[("selected", "#C7D2FE")], foreground=[("selected", "black")])
    style.configure("TButton", padding=6)
    style.configure("Accent.TButton", background=ACCENT, foreground="white", font=(FONT, 10, "bold"))
    style.map("Accent.TButton", background=[("active", "#059669")])
    style.configure("Danger.TButton", background=DANGER, foreground="white", font=(FONT, 10, "bold"))
    style.map("Danger.TButton", background=[("active", "#DC2626")])


def _hex_to_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def gradient_colors(stops, n):
    """n colours spread evenly across the given hex colour stops."""
    rgbs = [_hex_to_rgb(s) for s in stops]
    segs = len(rgbs) - 1
    out = []
    for i in range(n):
        t = i / max(1, n - 1) * segs
        k = min(int(t), segs - 1)
        f = t - k
        a_, b_ = rgbs[k], rgbs[k + 1]
        out.append("#%02x%02x%02x" % tuple(int(a_[j] + (b_[j] - a_[j]) * f) for j in range(3)))
    return out


class GradientCanvas(tk.Canvas):
    """Canvas with a colourful gradient background that redraws on resize."""

    def __init__(self, master, stops, vertical=False, **kwargs):
        super().__init__(master, highlightthickness=0, bd=0, **kwargs)
        self.stops = stops
        self.vertical = vertical
        self.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        w, h = event.width, event.height
        self.delete("grad")
        step = 3
        n = (h if self.vertical else w) // step + 1
        for i, col in enumerate(gradient_colors(self.stops, n)):
            pos = i * step
            if self.vertical:
                self.create_rectangle(0, pos, w, pos + step, fill=col, outline=col, tags="grad")
            else:
                self.create_rectangle(pos, 0, pos + step, h, fill=col, outline=col, tags="grad")
        self.tag_lower("grad")
        self.after_resize(w, h)

    def after_resize(self, w, h):
        pass


# ============================================================
#  TABLE WIDGET (Treeview + scrollbar + CSV export)
# ============================================================
class Table(ttk.Frame):
    def __init__(self, parent, columns, widths, height=12):
        super().__init__(parent)
        self.columns = list(columns)
        self.rows = []
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings",
                                 height=min(height, 6), selectmode="extended")
        for col, w in zip(self.columns, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, minwidth=60, anchor="center")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        colors = {"low": "#fde2e2", "Present": "#e6f7ea", "Absent": "#fde2e2",
                  "Late": "#fff3d6", "Approved": "#e6f7ea", "Rejected": "#fde2e2"}
        for tag, color in colors.items():
            self.tree.tag_configure(tag, background=color)

    def fill(self, rows, iids=None, tag_fn=None):
        self.tree.delete(*self.tree.get_children())
        self.rows = [tuple("" if v is None else v for v in r) for r in rows]
        for i, row in enumerate(self.rows):
            kwargs = {}
            if iids is not None:
                kwargs["iid"] = str(iids[i])
            tags = tag_fn(row) if tag_fn else ()
            self.tree.insert("", "end", values=row, tags=tags, **kwargs)

    def selected(self):
        return self.tree.selection()

    def export_csv(self, default_name="report.csv"):
        if not self.rows:
            messagebox.showinfo("Export", "Export karne ke liye koi data nahi hai. Pehle Load dabao.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", initialfile=default_name,
            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(self.columns)
            writer.writerows(self.rows)
        messagebox.showinfo("Export", f"Report save ho gayi:\n{path}")


# ============================================================
#  LOGIN SCREEN  (colourful gradient background)
# ============================================================
class LoginFrame(GradientCanvas):
    def __init__(self, master, on_success):
        super().__init__(master, ("#7C3AED", "#2563EB", "#06B6D4"))
        self.on_success = on_success

        card = tk.Frame(self, bg="white")
        tk.Frame(card, bg="#F59E0B", height=6).pack(fill="x")
        body = tk.Frame(card, bg="white", padx=40, pady=24)
        body.pack()

        logo = tk.Canvas(body, width=64, height=64, bg="white", highlightthickness=0)
        logo.create_oval(4, 4, 60, 60, fill="#7C3AED", outline="")
        logo.create_text(32, 32, text="\u2714", font=(FONT, 24, "bold"), fill="white")
        logo.pack()
        tk.Label(body, text="Welcome Back!", bg="white", fg="#312E81",
                 font=(FONT, 20, "bold")).pack(pady=(8, 0))
        tk.Label(body, text="Login to your account", bg="white", fg=MUTED).pack(pady=(0, 16))

        tk.Label(body, text="Username", bg="white", fg=TEXT, anchor="w").pack(fill="x")
        self.user_e = ttk.Entry(body, width=32)
        self.user_e.pack(pady=(2, 12), ipady=4)
        tk.Label(body, text="Password", bg="white", fg=TEXT, anchor="w").pack(fill="x")
        self.pass_e = ttk.Entry(body, width=32, show="*")
        self.pass_e.pack(pady=(2, 18), ipady=4)

        tk.Button(body, text="LOGIN", bg="#7C3AED", fg="white", activebackground="#6D28D9",
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=(FONT, 11, "bold"), command=self.login).pack(fill="x", ipady=7)
        tk.Label(body, text="Demo:  admin / admin123    teacher1 / teacher123", bg="white",
                 fg=MUTED, font=(FONT, 8)).pack(pady=(14, 0))
        tk.Label(body, text="student1 / student123", bg="white", fg=MUTED,
                 font=(FONT, 8)).pack()

        self.card_win = self.create_window(0, 0, window=card, anchor="center")
        self.user_e.focus()
        self.bind_all("<Return>", self.login)

    def after_resize(self, w, h):
        self.coords(self.card_win, w - 280, h / 2)
        self.delete("deco")
        self.delete("txt")
        # translucent bubbles
        for cx, cy, r in ((0.08, 0.92, 0.30), (0.42, -0.04, 0.22), (0.95, 0.98, 0.30),
                          (0.28, 0.58, 0.06), (0.60, 0.90, 0.05)):
            R = r * h
            self.create_oval(cx * w - R, cy * h - R, cx * w + R, cy * h + R,
                             fill="white", stipple="gray12", outline="", tags="deco")
        self.tag_lower("deco")
        self.tag_lower("grad")
        # welcome text on the left
        x, y = max(50, w * 0.06), h * 0.24
        self.create_text(x, y, text="Attendance", anchor="w", font=(FONT, 38, "bold"),
                         fill="white", tags="txt")
        self.create_text(x, y + 56, text="Management System", anchor="w", font=(FONT, 30, "bold"),
                         fill="#FDE68A", tags="txt")
        self.create_text(x, y + 104, text="Smart  \u2022  Simple  \u2022  Online", anchor="w",
                         font=(FONT, 13), fill="#E0F2FE", tags="txt")
        features = ["Mark attendance in seconds", "Automatic attendance percentage",
                    "Low-attendance warnings", "Online leave requests"]
        for i, text in enumerate(features):
            yy = y + 170 + i * 38
            self.create_text(x, yy, text="\u2714", anchor="w", font=(FONT, 14, "bold"),
                             fill="#FDE68A", tags="txt")
            self.create_text(x + 32, yy, text=text, anchor="w", font=(FONT, 14),
                             fill="white", tags="txt")

    @safe
    def login(self, event=None):
        if not self.winfo_exists():
            return
        username = self.user_e.get().strip()
        password = self.pass_e.get()
        if not username or not password:
            messagebox.showwarning("Login", "Username aur password dono likho.")
            return

        rows = query("SELECT user_id, username, role FROM users "
                     "WHERE username=%s AND password_hash=%s",
                     (username, hash_password(password)))
        if not rows:
            messagebox.showerror("Login Failed", "Username ya password galat hai.")
            return

        user_id, uname, role = rows[0]
        user = {"user_id": user_id, "username": uname, "role": role, "full_name": "Administrator"}

        if role == "teacher":
            t = query("SELECT teacher_id, full_name FROM teachers WHERE user_id=%s", (user_id,))
            if not t:
                messagebox.showerror("Login", "Is account ka teacher profile nahi mila.")
                return
            user["teacher_id"], user["full_name"] = t[0]
        elif role == "student":
            s = query("SELECT student_id, full_name, roll_no FROM students WHERE user_id=%s", (user_id,))
            if not s:
                messagebox.showerror("Login", "Is account ka student profile nahi mila.")
                return
            user["student_id"], user["full_name"], user["roll_no"] = s[0]

        self.unbind_all("<Return>")
        self.on_success(user)


# ============================================================
#  DASHBOARD BASE  (colourful sidebar + gradient top bar)
# ============================================================
class TopBar(GradientCanvas):
    def __init__(self, master, user):
        super().__init__(master, ("#EC4899", "#8B5CF6", "#3B82F6", "#06B6D4"), height=78)
        self.user = user
        self.page_title = "Dashboard"
        self._size = (0, 78)

    def set_title(self, text):
        self.page_title = text
        self.draw_texts()

    def after_resize(self, w, h):
        self._size = (w, h)
        self.draw_texts()

    def draw_texts(self):
        w, h = self._size
        self.delete("txt")
        self.create_text(24, h * 0.38, text=self.page_title, anchor="w",
                         font=(FONT, 19, "bold"), fill="white", tags="txt")
        self.create_text(24, h * 0.74, text=dt.date.today().strftime("%A, %d %B %Y"), anchor="w",
                         font=(FONT, 10), fill="#F5F3FF", tags="txt")
        self.create_text(w - 24, h * 0.38, text=self.user["full_name"], anchor="e",
                         font=(FONT, 12, "bold"), fill="white", tags="txt")
        self.create_text(w - 24, h * 0.74, text=self.user["role"].title(), anchor="e",
                         font=(FONT, 10, "bold"), fill="#FEF3C7", tags="txt")


class DashboardBase(ttk.Frame):
    DOTS = ["#F472B6", "#FBBF24", "#34D399", "#60A5FA", "#A78BFA", "#FB923C"]

    def __init__(self, master, user, on_logout):
        super().__init__(master)
        self.user = user
        self.on_logout = on_logout

        self.sidebar = tk.Frame(self, bg=SIDEBAR, width=235)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        right = ttk.Frame(self)
        right.pack(side="left", fill="both", expand=True)
        self.topbar = TopBar(right, user)
        self.topbar.pack(fill="x")
        self.nb = ttk.Notebook(right, style="Hidden.TNotebook")
        self.nb.pack(fill="both", expand=True, padx=16, pady=14)

        self.build()
        self.build_sidebar()
        self.nb.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.on_tab_changed()

    def build(self):
        raise NotImplementedError

    def refresh_all(self):
        pass

    # ---------------- sidebar ----------------
    def build_sidebar(self):
        sb = self.sidebar
        logo = tk.Canvas(sb, width=235, height=104, bg=SIDEBAR, highlightthickness=0)
        logo.create_oval(20, 26, 72, 78, fill="#F59E0B", outline="")
        logo.create_text(46, 52, text="\u2714", font=(FONT, 22, "bold"), fill="white")
        logo.create_text(84, 42, text="Attendance", anchor="w", font=(FONT, 15, "bold"), fill="white")
        logo.create_text(84, 64, text="Management", anchor="w", font=(FONT, 10), fill="#C7D2FE")
        logo.pack()
        tk.Frame(sb, bg="#4338CA", height=1).pack(fill="x", padx=16, pady=(0, 14))

        self.nav_rows = []
        for i, tab_id in enumerate(self.nb.tabs()):
            text = self.nb.tab(tab_id, "text")
            row = tk.Frame(sb, bg=SIDEBAR, cursor="hand2")
            row.pack(fill="x", padx=12, pady=3)
            dot = tk.Label(row, text="\u25CF", fg=self.DOTS[i % len(self.DOTS)], bg=SIDEBAR,
                           font=(FONT, 12))
            dot.pack(side="left", padx=(12, 8), pady=9)
            lbl = tk.Label(row, text=text, fg="white", bg=SIDEBAR, font=(FONT, 11, "bold"), anchor="w")
            lbl.pack(side="left", fill="x", expand=True)
            for widget in (row, dot, lbl):
                widget.bind("<Button-1>", lambda e, i=i: self.nb.select(i))
                widget.bind("<Enter>", lambda e, i=i: self.paint_nav(hover=i))
                widget.bind("<Leave>", lambda e: self.paint_nav())
            self.nav_rows.append((row, dot, lbl))

        tk.Button(sb, text="Logout", bg=DANGER, fg="white", activebackground="#DC2626",
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=(FONT, 10, "bold"), command=self.on_logout).pack(
            side="bottom", fill="x", padx=16, pady=(6, 16), ipady=6)
        tk.Button(sb, text="Change Password", bg="#6366F1", fg="white", activebackground="#4F46E5",
                  activeforeground="white", relief="flat", cursor="hand2",
                  font=(FONT, 10), command=self.change_password).pack(
            side="bottom", fill="x", padx=16, ipady=6)

    def paint_nav(self, hover=None):
        current = self.nb.index(self.nb.select())
        for i, (row, dot, lbl) in enumerate(self.nav_rows):
            color = SIDEBAR_ACTIVE if i == current else (SIDEBAR_HOVER if i == hover else SIDEBAR)
            for widget in (row, dot, lbl):
                widget.config(bg=color)

    def on_tab_changed(self, event=None):
        self.paint_nav()
        tab_id = self.nb.select()
        self.topbar.set_title(self.nb.tab(tab_id, "text"))
        self.refresh_all()

    # ---------------- change password ----------------
    def change_password(self):
        win = tk.Toplevel(self)
        win.title("Change Password")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.winfo_toplevel())
        win.grab_set()

        frm = ttk.Frame(win, padding=20)
        frm.pack()
        entries = make_form(frm, [("Purana Password", "old_password", True),
                                  ("Naya Password", "new_password", True),
                                  ("Naya Password Dobara", "confirm_password", True)], per_row=1, width=30)

        @safe
        def save():
            v = form_values(entries)
            ok = query("SELECT 1 FROM users WHERE user_id=%s AND password_hash=%s",
                       (self.user["user_id"], hash_password(v["old_password"])))
            if not ok:
                messagebox.showerror("Error", "Purana password galat hai.", parent=win)
                return
            if len(v["new_password"]) < 6:
                messagebox.showwarning("Password", "Naya password kam az kam 6 characters ka ho.", parent=win)
                return
            if v["new_password"] != v["confirm_password"]:
                messagebox.showwarning("Password", "Naya password dono jagah same likho.", parent=win)
                return
            execute("UPDATE users SET password_hash=%s WHERE user_id=%s",
                    (hash_password(v["new_password"]), self.user["user_id"]))
            messagebox.showinfo("Done", "Password change ho gaya.", parent=win)
            win.destroy()

        ttk.Button(frm, text="Save", style="Accent.TButton", command=save).grid(
            row=6, column=0, sticky="ew", pady=(6, 0))


# ============================================================
#  ADMIN DASHBOARD
# ============================================================
class AdminFrame(DashboardBase):
    def build(self):
        self.build_overview()
        self.build_students()
        self.build_teachers()
        self.build_courses()
        self.build_enrollments()
        self.build_reports()

    def refresh_all(self):
        self.refresh_overview()
        self.refresh_students()
        self.refresh_teachers()
        self.refresh_courses()
        self.refresh_enrollments()
        self.refresh_report()

    # ---------------- Overview ----------------
    def build_overview(self):
        tab = ttk.Frame(self.nb, padding=12)
        self.nb.add(tab, text="Overview")
        row = ttk.Frame(tab)
        row.pack(fill="x")
        self.cards = {}
        colors = {"students": "#6366F1", "teachers": "#10B981", "courses": "#F59E0B",
                  "today": "#EC4899", "low": "#EF4444"}
        for key, title in (("students", "Students"), ("teachers", "Teachers"),
                           ("courses", "Courses"), ("today", "Today's Records"),
                           ("low", "Low Attendance")):
            card = tk.Frame(row, bg=colors[key], padx=18, pady=16)
            card.pack(side="left", padx=6, fill="x", expand=True)
            val = tk.Label(card, text="0", font=(FONT, 26, "bold"), bg=colors[key], fg="white")
            val.pack()
            tk.Label(card, text=title, bg=colors[key], fg="white", font=(FONT, 10, "bold")).pack()
            self.cards[key] = val

        ttk.Label(tab, text="Low attendance students (75% se kam)",
                  font=(FONT, 11, "bold")).pack(anchor="w", pady=(20, 6))
        self.low_table = Table(tab, SUMMARY_COLS, SUMMARY_WIDTHS, height=10)
        self.low_table.pack(fill="both", expand=True)

    @safe
    def refresh_overview(self):
        s, t, c, today = query(
            "SELECT (SELECT COUNT(*) FROM students), (SELECT COUNT(*) FROM teachers), "
            "(SELECT COUNT(*) FROM courses), "
            "(SELECT COUNT(*) FROM attendance WHERE att_date = CURDATE())")[0]
        low = summary_rows(low_only=True)
        for key, val in (("students", s), ("teachers", t), ("courses", c),
                         ("today", today), ("low", len(low))):
            self.cards[key].config(text=str(val))
        self.low_table.fill(low, tag_fn=low_tag)

    # ---------------- Students ----------------
    def build_students(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Students")
        form = ttk.LabelFrame(tab, text="Naya Student Add Karo", padding=10)
        form.pack(fill="x")
        self.st_form = make_form(form, [
            ("Username", "username", False), ("Password", "password", True),
            ("Roll No", "roll", False), ("Full Name", "name", False),
            ("Program", "program", False), ("Semester", "sem", False)])
        ttk.Button(form, text="Add Student", style="Accent.TButton",
                   command=self.add_student).grid(row=0, column=3, rowspan=2, padx=12)

        self.st_table = Table(tab, ("Roll No", "Name", "Program", "Semester", "Username"),
                              (110, 230, 120, 90, 140))
        self.st_table.pack(fill="both", expand=True, pady=10)
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Delete Selected", style="Danger.TButton",
                   command=self.delete_student).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.refresh_all).pack(side="left", padx=8)

    @safe
    def refresh_students(self):
        rows = query("SELECT s.student_id, s.roll_no, s.full_name, s.program, s.semester, u.username "
                     "FROM students s JOIN users u ON u.user_id = s.user_id ORDER BY s.roll_no")
        self.st_table.fill([r[1:] for r in rows], iids=[r[0] for r in rows])

    @safe
    def add_student(self):
        v = form_values(self.st_form)
        if not all([v["username"], v["password"], v["roll"], v["name"]]):
            messagebox.showwarning("Student", "Username, Password, Roll No aur Name zaroori hain.")
            return
        if not v["sem"].isdigit():
            messagebox.showwarning("Student", "Semester number hona chahiye (jaise 5).")
            return
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,'student')",
                        (v["username"], hash_password(v["password"])))
            uid = cur.lastrowid
            cur.execute("INSERT INTO students (user_id, roll_no, full_name, program, semester) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (uid, v["roll"], v["name"], v["program"], int(v["sem"])))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        clear_form(self.st_form)
        self.refresh_all()
        messagebox.showinfo("Student", "Student add ho gaya.")

    @safe
    def delete_student(self):
        sel = self.st_table.selected()
        if not sel:
            messagebox.showwarning("Delete", "Pehle table mein se student select karo.")
            return
        if not messagebox.askyesno("Confirm", f"{len(sel)} student(s) aur unki attendance delete ho jayegi. Pakka?"):
            return
        for sid in sel:
            sid = int(sid)
            uid = query("SELECT user_id FROM students WHERE student_id=%s", (sid,))[0][0]
            run_transaction([
                ("DELETE FROM attendance WHERE student_id=%s", (sid,)),
                ("DELETE FROM leave_requests WHERE student_id=%s", (sid,)),
                ("DELETE FROM enrollments WHERE student_id=%s", (sid,)),
                ("DELETE FROM students WHERE student_id=%s", (sid,)),
                ("DELETE FROM users WHERE user_id=%s", (uid,)),
            ])
        self.refresh_all()

    # ---------------- Teachers ----------------
    def build_teachers(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Teachers")
        form = ttk.LabelFrame(tab, text="Naya Teacher Add Karo", padding=10)
        form.pack(fill="x")
        self.t_form = make_form(form, [
            ("Username", "username", False), ("Password", "password", True),
            ("Full Name", "name", False), ("Email", "email", False)], per_row=4)
        ttk.Button(form, text="Add Teacher", style="Accent.TButton",
                   command=self.add_teacher).grid(row=0, column=4, rowspan=2, padx=12)

        self.t_table = Table(tab, ("Name", "Email", "Username"), (240, 260, 160))
        self.t_table.pack(fill="both", expand=True, pady=10)
        bar = ttk.Frame(tab)
        bar.pack(fill="x")
        ttk.Button(bar, text="Delete Selected", style="Danger.TButton",
                   command=self.delete_teacher).pack(side="left")

    @safe
    def refresh_teachers(self):
        rows = query("SELECT t.teacher_id, t.full_name, t.email, u.username "
                     "FROM teachers t JOIN users u ON u.user_id = t.user_id ORDER BY t.full_name")
        self.t_table.fill([r[1:] for r in rows], iids=[r[0] for r in rows])

    @safe
    def add_teacher(self):
        v = form_values(self.t_form)
        if not all([v["username"], v["password"], v["name"]]):
            messagebox.showwarning("Teacher", "Username, Password aur Name zaroori hain.")
            return
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,'teacher')",
                        (v["username"], hash_password(v["password"])))
            uid = cur.lastrowid
            cur.execute("INSERT INTO teachers (user_id, full_name, email) VALUES (%s,%s,%s)",
                        (uid, v["name"], v["email"]))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        clear_form(self.t_form)
        self.refresh_all()
        messagebox.showinfo("Teacher", "Teacher add ho gaya.")

    @safe
    def delete_teacher(self):
        sel = self.t_table.selected()
        if not sel:
            messagebox.showwarning("Delete", "Pehle table mein se teacher select karo.")
            return
        if not messagebox.askyesno("Confirm", "Teacher delete hoga aur uske courses 'Not assigned' ho jayenge. Pakka?"):
            return
        for tid in sel:
            tid = int(tid)
            uid = query("SELECT user_id FROM teachers WHERE teacher_id=%s", (tid,))[0][0]
            run_transaction([
                ("UPDATE attendance SET marked_by=NULL WHERE marked_by=%s", (tid,)),
                ("UPDATE courses SET teacher_id=NULL WHERE teacher_id=%s", (tid,)),
                ("DELETE FROM teachers WHERE teacher_id=%s", (tid,)),
                ("DELETE FROM users WHERE user_id=%s", (uid,)),
            ])
        self.refresh_all()

    # ---------------- Courses ----------------
    def build_courses(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Courses")
        form = ttk.LabelFrame(tab, text="Course Add / Teacher Assign", padding=10)
        form.pack(fill="x")
        self.c_form = make_form(form, [("Course Code", "code", False),
                                       ("Course Name", "name", False)], per_row=2)
        ttk.Label(form, text="Teacher").grid(row=0, column=2, sticky="w", padx=6)
        self.c_teacher = ttk.Combobox(form, state="readonly", width=28)
        self.c_teacher.grid(row=1, column=2, padx=6, pady=(0, 8))
        ttk.Button(form, text="Add Course", style="Accent.TButton",
                   command=self.add_course).grid(row=0, column=3, rowspan=2, padx=8)
        ttk.Button(form, text="Update Teacher of Selected",
                   command=self.update_course_teacher).grid(row=0, column=4, rowspan=2, padx=4)

        self.c_table = Table(tab, ("Code", "Course Name", "Teacher"), (120, 300, 220))
        self.c_table.pack(fill="both", expand=True, pady=10)
        ttk.Button(tab, text="Delete Selected", style="Danger.TButton",
                   command=self.delete_course).pack(anchor="w")

    @safe
    def refresh_courses(self):
        teachers = query("SELECT teacher_id, full_name FROM teachers ORDER BY full_name")
        set_combo(self.c_teacher, ["0 - Not assigned"] + [f"{i} - {n}" for i, n in teachers], 1)
        rows = query("SELECT c.course_id, c.course_code, c.course_name, "
                     "COALESCE(t.full_name, '-- Not assigned --') "
                     "FROM courses c LEFT JOIN teachers t ON t.teacher_id = c.teacher_id "
                     "ORDER BY c.course_code")
        self.c_table.fill([r[1:] for r in rows], iids=[r[0] for r in rows])

    @safe
    def add_course(self):
        v = form_values(self.c_form)
        if not v["code"] or not v["name"]:
            messagebox.showwarning("Course", "Course code aur name dono likho.")
            return
        tid = combo_id(self.c_teacher.get()) if self.c_teacher.get() else 0
        execute("INSERT INTO courses (course_code, course_name, teacher_id) VALUES (%s,%s,%s)",
                (v["code"], v["name"], tid or None))
        clear_form(self.c_form)
        self.refresh_all()

    @safe
    def update_course_teacher(self):
        sel = self.c_table.selected()
        if not sel or not self.c_teacher.get():
            messagebox.showwarning("Course", "Table se course select karo aur teacher chuno.")
            return
        tid = combo_id(self.c_teacher.get())
        for cid in sel:
            execute("UPDATE courses SET teacher_id=%s WHERE course_id=%s", (tid or None, int(cid)))
        self.refresh_all()

    @safe
    def delete_course(self):
        sel = self.c_table.selected()
        if not sel:
            messagebox.showwarning("Delete", "Pehle course select karo.")
            return
        if not messagebox.askyesno("Confirm", "Course aur uski attendance/enrollments delete ho jayengi. Pakka?"):
            return
        for cid in sel:
            cid = int(cid)
            run_transaction([
                ("DELETE FROM attendance WHERE course_id=%s", (cid,)),
                ("DELETE FROM leave_requests WHERE course_id=%s", (cid,)),
                ("DELETE FROM enrollments WHERE course_id=%s", (cid,)),
                ("DELETE FROM courses WHERE course_id=%s", (cid,)),
            ])
        self.refresh_all()

    # ---------------- Enrollments ----------------
    def build_enrollments(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Enrollments")
        form = ttk.LabelFrame(tab, text="Student ko Course mein Enroll Karo", padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="Student").grid(row=0, column=0, sticky="w", padx=6)
        self.e_student = ttk.Combobox(form, state="readonly", width=34)
        self.e_student.grid(row=1, column=0, padx=6, pady=(0, 8))
        ttk.Label(form, text="Course").grid(row=0, column=1, sticky="w", padx=6)
        self.e_course = ttk.Combobox(form, state="readonly", width=34)
        self.e_course.grid(row=1, column=1, padx=6, pady=(0, 8))
        ttk.Button(form, text="Enroll", style="Accent.TButton",
                   command=self.enroll).grid(row=0, column=2, rowspan=2, padx=12)

        self.e_table = Table(tab, ("Roll No", "Student", "Code", "Course"), (110, 230, 110, 260))
        self.e_table.pack(fill="both", expand=True, pady=10)
        ttk.Button(tab, text="Remove Selected Enrollment", style="Danger.TButton",
                   command=self.remove_enrollment).pack(anchor="w")

    @safe
    def refresh_enrollments(self):
        students = query("SELECT student_id, roll_no, full_name FROM students ORDER BY roll_no")
        set_combo(self.e_student, [f"{i} - {r} - {n}" for i, r, n in students])
        courses = query("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code")
        set_combo(self.e_course, [f"{i} - {c} - {n}" for i, c, n in courses])
        rows = query("SELECT e.enrollment_id, s.roll_no, s.full_name, c.course_code, c.course_name "
                     "FROM enrollments e JOIN students s ON s.student_id = e.student_id "
                     "JOIN courses c ON c.course_id = e.course_id ORDER BY c.course_code, s.roll_no")
        self.e_table.fill([r[1:] for r in rows], iids=[r[0] for r in rows])

    @safe
    def enroll(self):
        if not self.e_student.get() or not self.e_course.get():
            messagebox.showwarning("Enroll", "Student aur course dono select karo.")
            return
        execute("INSERT INTO enrollments (student_id, course_id) VALUES (%s,%s)",
                (combo_id(self.e_student.get()), combo_id(self.e_course.get())))
        self.refresh_all()

    @safe
    def remove_enrollment(self):
        sel = self.e_table.selected()
        if not sel:
            messagebox.showwarning("Remove", "Pehle enrollment select karo.")
            return
        for eid in sel:
            execute("DELETE FROM enrollments WHERE enrollment_id=%s", (int(eid),))
        self.refresh_all()

    # ---------------- Reports ----------------
    def build_reports(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Reports")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Course:").pack(side="left")
        self.r_course = ttk.Combobox(bar, state="readonly", width=34)
        self.r_course.pack(side="left", padx=6)
        self.r_course.bind("<<ComboboxSelected>>", lambda e: self.refresh_report())
        self.r_low = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Sirf Low Attendance (<75%)", variable=self.r_low,
                        command=self.refresh_report).pack(side="left", padx=10)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: self.r_table.export_csv("attendance_report.csv")).pack(side="right")
        self.r_table = Table(tab, SUMMARY_COLS, SUMMARY_WIDTHS, height=16)
        self.r_table.pack(fill="both", expand=True)

    @safe
    def refresh_report(self):
        courses = query("SELECT course_id, course_code, course_name FROM courses ORDER BY course_code")
        set_combo(self.r_course, ["All Courses"] + [f"{i} - {c} - {n}" for i, c, n in courses])
        where, params = "", ()
        sel = self.r_course.get()
        if sel and not sel.startswith("All"):
            where, params = "WHERE c.course_id=%s", (combo_id(sel),)
        rows = summary_rows(where, params, self.r_low.get())
        self.r_table.fill(rows, tag_fn=low_tag)


# ============================================================
#  TEACHER DASHBOARD
# ============================================================
class TeacherFrame(DashboardBase):
    STATUS_CYCLE = ["Present", "Absent", "Late"]

    def build(self):
        self.tid = self.user["teacher_id"]
        self.loaded = None          # (course_id, date) jo table mein khula hai
        self.build_mark()
        self.build_leaves()
        self.build_reports()

    def refresh_all(self):
        self.refresh_courses()
        self.refresh_leaves()
        self.refresh_report()

    @safe
    def refresh_courses(self):
        courses = query("SELECT course_id, course_code, course_name FROM courses "
                        "WHERE teacher_id=%s ORDER BY course_code", (self.tid,))
        values = [f"{i} - {c} - {n}" for i, c, n in courses]
        set_combo(self.m_course, values)
        set_combo(self.r_course, ["All My Courses"] + values)

    # ---------------- Mark Attendance ----------------
    def build_mark(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Mark Attendance")
        top = ttk.Frame(tab)
        top.pack(fill="x", pady=(0, 8))
        ttk.Label(top, text="Course:").pack(side="left")
        self.m_course = ttk.Combobox(top, state="readonly", width=34)
        self.m_course.pack(side="left", padx=6)
        ttk.Label(top, text="Date (YYYY-MM-DD):").pack(side="left", padx=(12, 0))
        self.m_date = ttk.Entry(top, width=12)
        self.m_date.insert(0, dt.date.today().isoformat())
        self.m_date.pack(side="left", padx=6)
        ttk.Button(top, text="Load Students", style="Accent.TButton",
                   command=self.load_students).pack(side="left", padx=8)

        self.m_info = ttk.Label(tab, text="Course aur date chuno, phir Load Students dabao. "
                                          "Status badalne ke liye row par double-click karo.",
                                foreground=MUTED)
        self.m_info.pack(anchor="w", pady=(0, 6))

        self.m_table = Table(tab, ("Roll No", "Student", "Status", "Leave"), (110, 280, 110, 170), height=14)
        self.m_table.pack(fill="both", expand=True)
        self.m_table.tree.bind("<Double-1>", self.cycle_status)

        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(8, 0))
        for status in self.STATUS_CYCLE:
            ttk.Button(bar, text=f"Selected -> {status}",
                       command=lambda s=status: self.set_status(s)).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Mark All Present",
                   command=lambda: self.set_status("Present", all_rows=True)).pack(side="left", padx=6)
        ttk.Button(bar, text="Save Attendance", style="Accent.TButton",
                   command=self.save_attendance).pack(side="right")

    @safe
    def load_students(self):
        sel = self.m_course.get()
        if not sel:
            messagebox.showwarning("Course", "Pehle course select karo.")
            return
        d = parse_date(self.m_date.get())
        if not d:
            messagebox.showwarning("Date", "Date format YYYY-MM-DD hona chahiye (jaise 2026-10-28).")
            return
        if d > dt.date.today():
            messagebox.showwarning("Date", "Future date ki attendance mark nahi ho sakti.")
            return
        cid = combo_id(sel)
        rows = query("""
            SELECT s.student_id, s.roll_no, s.full_name,
                   COALESCE(a.status, 'Present'),
                   COALESCE((SELECT l.status FROM leave_requests l
                             WHERE l.student_id = s.student_id AND l.course_id = %s AND l.leave_date = %s
                             ORDER BY FIELD(l.status, 'Approved', 'Pending', 'Rejected') LIMIT 1), ''),
                   a.attendance_id
            FROM enrollments e
            JOIN students s ON s.student_id = e.student_id
            LEFT JOIN attendance a ON a.student_id = s.student_id
                                  AND a.course_id = e.course_id AND a.att_date = %s
            WHERE e.course_id = %s
            ORDER BY s.roll_no
        """, (cid, d, d, cid))
        self.loaded = (cid, d)
        table_rows = [(r[1], r[2], r[3], f"Leave {r[4]}" if r[4] else "") for r in rows]
        self.m_table.fill(table_rows, iids=[r[0] for r in rows], tag_fn=lambda row: (row[2],))
        already = any(r[5] is not None for r in rows)
        note = "Is date ki attendance pehle se saved thi (edit kar sakte ho)." if already \
            else "Nayi attendance - default sab Present hain."
        self.m_info.config(text=f"{len(rows)} students loaded. {note}")
        if not rows:
            messagebox.showinfo("Students", "Is course mein koi student enrolled nahi hai.")

    def _paint(self, iid, status):
        self.m_table.tree.set(iid, "Status", status)
        self.m_table.tree.item(iid, tags=(status,))

    def set_status(self, status, all_rows=False):
        tree = self.m_table.tree
        items = tree.get_children() if all_rows else tree.selection()
        if not items:
            messagebox.showwarning("Status", "Pehle Load Students karo aur rows select karo.")
            return
        for iid in items:
            self._paint(iid, status)

    def cycle_status(self, event):
        tree = self.m_table.tree
        iid = tree.identify_row(event.y)
        if not iid:
            return
        current = tree.set(iid, "Status")
        nxt = self.STATUS_CYCLE[(self.STATUS_CYCLE.index(current) + 1) % 3]
        self._paint(iid, nxt)

    @safe
    def save_attendance(self):
        if not self.loaded:
            messagebox.showwarning("Save", "Pehle Load Students dabao.")
            return
        cid, d = self.loaded
        tree = self.m_table.tree
        items = tree.get_children()
        if not items:
            messagebox.showwarning("Save", "Save karne ke liye koi student nahi hai.")
            return
        conn = get_connection()
        try:
            cur = conn.cursor()
            for iid in items:
                cur.execute(
                    "INSERT INTO attendance (student_id, course_id, att_date, status, marked_by) "
                    "VALUES (%s,%s,%s,%s,%s) "
                    "ON DUPLICATE KEY UPDATE status = VALUES(status), marked_by = VALUES(marked_by)",
                    (int(iid), cid, d, tree.set(iid, "Status"), self.tid))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        present = sum(1 for i in items if tree.set(i, "Status") != "Absent")
        messagebox.showinfo("Saved", f"Attendance save ho gayi.\n"
                                     f"Present/Late: {present}   Absent: {len(items) - present}")
        self.refresh_report()

    # ---------------- Leave Requests ----------------
    def build_leaves(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Leave Requests")
        self.l_table = Table(tab, ("Student", "Course", "Leave Date", "Reason", "Status"),
                             (230, 90, 110, 300, 100), height=14)
        self.l_table.pack(fill="both", expand=True)
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Approve", style="Accent.TButton",
                   command=lambda: self.set_leave("Approved")).pack(side="left")
        ttk.Button(bar, text="Reject", style="Danger.TButton",
                   command=lambda: self.set_leave("Rejected")).pack(side="left", padx=8)
        ttk.Button(bar, text="Refresh", command=self.refresh_leaves).pack(side="left")

    @safe
    def refresh_leaves(self):
        rows = query("""
            SELECT l.leave_id, s.roll_no, s.full_name, c.course_code, l.leave_date, l.reason, l.status
            FROM leave_requests l
            JOIN students s ON s.student_id = l.student_id
            JOIN courses  c ON c.course_id  = l.course_id
            WHERE c.teacher_id = %s
            ORDER BY FIELD(l.status, 'Pending', 'Approved', 'Rejected'), l.leave_date DESC
        """, (self.tid,))
        data = [(f"{r[1]} - {r[2]}", r[3], str(r[4]), r[5], r[6]) for r in rows]
        self.l_table.fill(data, iids=[r[0] for r in rows], tag_fn=lambda row: (row[-1],))

    @safe
    def set_leave(self, status):
        sel = self.l_table.selected()
        if not sel:
            messagebox.showwarning("Leave", "Pehle koi request select karo.")
            return
        for lid in sel:
            execute("UPDATE leave_requests SET status=%s WHERE leave_id=%s AND course_id IN "
                    "(SELECT course_id FROM courses WHERE teacher_id=%s)",
                    (status, int(lid), self.tid))
        self.refresh_leaves()

    # ---------------- Reports ----------------
    def build_reports(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Reports")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Course:").pack(side="left")
        self.r_course = ttk.Combobox(bar, state="readonly", width=34)
        self.r_course.pack(side="left", padx=6)
        self.r_course.bind("<<ComboboxSelected>>", lambda e: self.refresh_report())
        self.r_low = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Sirf Low Attendance (<75%)", variable=self.r_low,
                        command=self.refresh_report).pack(side="left", padx=10)
        ttk.Button(bar, text="Export CSV",
                   command=lambda: self.r_table.export_csv("course_report.csv")).pack(side="right")
        self.r_table = Table(tab, SUMMARY_COLS, SUMMARY_WIDTHS, height=16)
        self.r_table.pack(fill="both", expand=True)

    @safe
    def refresh_report(self):
        where, params = "WHERE c.teacher_id=%s", [self.tid]
        sel = self.r_course.get()
        if sel and not sel.startswith("All"):
            where += " AND c.course_id=%s"
            params.append(combo_id(sel))
        rows = summary_rows(where, tuple(params), self.r_low.get())
        self.r_table.fill(rows, tag_fn=low_tag)


# ============================================================
#  STUDENT DASHBOARD
# ============================================================
class StudentFrame(DashboardBase):
    def build(self):
        self.sid = self.user["student_id"]
        self.build_summary()
        self.build_history()
        self.build_leave()

    def refresh_all(self):
        self.refresh_summary()
        self.refresh_courses()
        self.refresh_history()
        self.refresh_leaves()

    @safe
    def refresh_courses(self):
        courses = query("SELECT c.course_id, c.course_code, c.course_name FROM enrollments e "
                        "JOIN courses c ON c.course_id = e.course_id "
                        "WHERE e.student_id=%s ORDER BY c.course_code", (self.sid,))
        values = [f"{i} - {c} - {n}" for i, c, n in courses]
        set_combo(self.h_course, ["All Courses"] + values)
        set_combo(self.l_course, values)

    # ---------------- My Attendance ----------------
    def build_summary(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="My Attendance")
        self.warn = tk.Label(tab, text="", font=(FONT, 11, "bold"), bg=BG, anchor="w")
        self.warn.pack(fill="x", pady=(0, 8))
        self.s_table = Table(tab, ("Code", "Course", "Total", "Attended", "Percentage",
                                   "Status", "Classes Needed"),
                             (90, 250, 80, 90, 110, 100, 130), height=14)
        self.s_table.pack(fill="both", expand=True)
        ttk.Label(tab, text=f"Kam az kam {MIN_ATTENDANCE:.0f}% attendance zaroori hai. "
                            "'Classes Needed' = lagataar kitni classes attend karni hain taake 75% poora ho.",
                  foreground=MUTED).pack(anchor="w", pady=(8, 0))

    @safe
    def refresh_summary(self):
        rows = summary_rows("WHERE s.student_id=%s", (self.sid,))
        data, low_count = [], 0
        for _, _, code, cname, total, attended, pct, status in rows:
            needed = "-"
            if status == "LOW":
                low_count += 1
                needed = str(max(0, 3 * total - 4 * attended))
            data.append((code, cname, total, attended, pct, status, needed))
        self.s_table.fill(data, tag_fn=lambda r: ("low",) if r[5] == "LOW" else ())
        if low_count:
            self.warn.config(text=f"Warning: {low_count} course(s) mein attendance {MIN_ATTENDANCE:.0f}% se kam hai!",
                             fg=DANGER)
        else:
            self.warn.config(text="Aapki attendance theek hai.", fg=ACCENT)

    # ---------------- History ----------------
    def build_history(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Attendance History")
        bar = ttk.Frame(tab)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="Course:").pack(side="left")
        self.h_course = ttk.Combobox(bar, state="readonly", width=34)
        self.h_course.pack(side="left", padx=6)
        self.h_course.bind("<<ComboboxSelected>>", lambda e: self.refresh_history())
        ttk.Button(bar, text="Export CSV",
                   command=lambda: self.h_table.export_csv("my_attendance.csv")).pack(side="right")
        self.h_table = Table(tab, ("Date", "Code", "Course", "Status"), (120, 100, 280, 110), height=16)
        self.h_table.pack(fill="both", expand=True)

    @safe
    def refresh_history(self):
        sql = ("SELECT a.att_date, c.course_code, c.course_name, a.status FROM attendance a "
               "JOIN courses c ON c.course_id = a.course_id WHERE a.student_id=%s")
        params = [self.sid]
        sel = self.h_course.get()
        if sel and not sel.startswith("All"):
            sql += " AND a.course_id=%s"
            params.append(combo_id(sel))
        sql += " ORDER BY a.att_date DESC, c.course_code"
        rows = [(str(d), code, name, status) for d, code, name, status in query(sql, tuple(params))]
        self.h_table.fill(rows, tag_fn=lambda r: (r[3],))

    # ---------------- Leave ----------------
    def build_leave(self):
        tab = ttk.Frame(self.nb, padding=10)
        self.nb.add(tab, text="Leave Request")
        form = ttk.LabelFrame(tab, text="Nayi Leave Request", padding=10)
        form.pack(fill="x")
        ttk.Label(form, text="Course").grid(row=0, column=0, sticky="w", padx=6)
        self.l_course = ttk.Combobox(form, state="readonly", width=32)
        self.l_course.grid(row=1, column=0, padx=6, pady=(0, 8))
        ttk.Label(form, text="Date (YYYY-MM-DD)").grid(row=0, column=1, sticky="w", padx=6)
        self.l_date = ttk.Entry(form, width=14)
        self.l_date.insert(0, dt.date.today().isoformat())
        self.l_date.grid(row=1, column=1, padx=6, pady=(0, 8))
        ttk.Label(form, text="Reason").grid(row=0, column=2, sticky="w", padx=6)
        self.l_reason = ttk.Entry(form, width=36)
        self.l_reason.grid(row=1, column=2, padx=6, pady=(0, 8))
        ttk.Button(form, text="Submit Request", style="Accent.TButton",
                   command=self.submit_leave).grid(row=0, column=3, rowspan=2, padx=10)

        self.l_table = Table(tab, ("Code", "Course", "Leave Date", "Reason", "Status"),
                             (90, 220, 110, 280, 100), height=12)
        self.l_table.pack(fill="both", expand=True, pady=10)

    @safe
    def refresh_leaves(self):
        rows = query("SELECT c.course_code, c.course_name, l.leave_date, l.reason, l.status "
                     "FROM leave_requests l JOIN courses c ON c.course_id = l.course_id "
                     "WHERE l.student_id=%s ORDER BY l.leave_date DESC", (self.sid,))
        data = [(code, name, str(d), reason, status) for code, name, d, reason, status in rows]
        self.l_table.fill(data, tag_fn=lambda r: (r[-1],))

    @safe
    def submit_leave(self):
        sel = self.l_course.get()
        d = parse_date(self.l_date.get())
        reason = self.l_reason.get().strip()
        if not sel:
            messagebox.showwarning("Leave", "Course select karo.")
            return
        if not d:
            messagebox.showwarning("Leave", "Date format YYYY-MM-DD hona chahiye.")
            return
        if d < dt.date.today():
            messagebox.showwarning("Leave", "Purani date ki leave request nahi ho sakti.")
            return
        if not reason:
            messagebox.showwarning("Leave", "Leave ki wajah likho.")
            return
        cid = combo_id(sel)
        dup = query("SELECT 1 FROM leave_requests WHERE student_id=%s AND course_id=%s "
                    "AND leave_date=%s AND status<>'Rejected'", (self.sid, cid, d))
        if dup:
            messagebox.showwarning("Leave", "Is course aur date ki request pehle se maujood hai.")
            return
        execute("INSERT INTO leave_requests (student_id, course_id, leave_date, reason) "
                "VALUES (%s,%s,%s,%s)", (self.sid, cid, d, reason))
        self.l_reason.delete(0, "end")
        self.refresh_leaves()
        messagebox.showinfo("Leave", "Request teacher ko bhej di gayi (status: Pending).")


# ============================================================
#  MAIN APP
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Online Student Attendance Management System")
        w = min(1200, self.winfo_screenwidth() - 40)
        h = min(720, self.winfo_screenheight() - 90)
        self.geometry(f"{w}x{h}+20+10")
        self.minsize(900, 540)
        self.configure(bg=BG)
        setup_style(self)
        self.show_login()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def show_login(self):
        self.clear()
        LoginFrame(self, self.open_dashboard).pack(fill="both", expand=True)

    def open_dashboard(self, user):
        self.clear()
        frames = {"admin": AdminFrame, "teacher": TeacherFrame, "student": StudentFrame}
        frames[user["role"]](self, user, self.show_login).pack(fill="both", expand=True)


def main():
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)   # Windows par saaf text
    except Exception:
        pass

    try:
        get_connection().close()
    except mysql.connector.Error as e:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Database Connection Failed",
            "MySQL se connect nahi ho paya.\n\n"
            "1) File mein DB_CONFIG ke andar password check karo\n"
            "2) MySQL80 service running honi chahiye\n"
            "3) attendance_db Workbench mein bana hona chahiye\n\n"
            f"Error: {e}")
        return

    App().mainloop()


if __name__ == "__main__":
    main()
