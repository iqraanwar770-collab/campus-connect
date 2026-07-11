"""
EduVerse (Campus Connect) - Student Community Platform
Flask + SQLite backend. Run: python app.py
"""
import os
import sqlite3
import threading
import webbrowser
from datetime import datetime
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, send_from_directory, g, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {"pdf", "doc", "docx", "ppt", "pptx", "png", "jpg", "jpeg", "gif", "txt"}

app = Flask(__name__)
app.config["SECRET_KEY"] = "eduverse-secret-key-change-me"
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB


# ---------- DB helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        subject TEXT,
        description TEXT,
        filename TEXT,
        file_type TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS blood_donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        blood_group TEXT NOT NULL,
        phone TEXT,
        city TEXT,
        email TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS lost_found (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        item_type TEXT,
        title TEXT NOT NULL,
        category TEXT,
        description TEXT,
        location TEXT,
        contact TEXT,
        status TEXT DEFAULT 'open',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    # Safe ALTERs for existing DBs
    for stmt in ("ALTER TABLE lost_found ADD COLUMN category TEXT",
                 "ALTER TABLE lost_found ADD COLUMN status TEXT DEFAULT 'open'"):
        try: c.execute(stmt)
        except sqlite3.OperationalError: pass
    conn.commit()
    conn.close()


def allowed_file(fn):
    return "." in fn and fn.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


@app.context_processor
def inject_user():
    return {"current_user": session.get("user_name"), "current_year": datetime.now().year}


# ---------- Routes ----------
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not (name and email and password):
            flash("All fields are required.", "danger")
            return render_template("register.html")
        db = get_db()
        try:
            db.execute("INSERT INTO users(name,email,password) VALUES(?,?,?)",
                       (name, email, generate_password_hash(password)))
            db.commit()
        except sqlite3.IntegrityError:
            flash("Email already registered.", "danger")
            return render_template("register.html")
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        flash("Welcome to EduVerse!", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    stats = {
        "notes": db.execute("SELECT COUNT(*) c FROM notes").fetchone()["c"],
        "donors": db.execute("SELECT COUNT(*) c FROM blood_donors").fetchone()["c"],
        "lost_found": db.execute("SELECT COUNT(*) c FROM lost_found").fetchone()["c"],
    }
    recent_notes = db.execute("SELECT * FROM notes ORDER BY id DESC LIMIT 5").fetchall()
    return render_template("dashboard.html", stats=stats, recent_notes=recent_notes)


# ---------- Notes ----------
@app.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    db = get_db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        file = request.files.get("file")
        filename = None
        file_type = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash("Unsupported file type.", "danger")
                return redirect(url_for("notes"))
            safe = secure_filename(file.filename)
            filename = f"{int(datetime.now().timestamp())}_{safe}"
            file.save(os.path.join(UPLOAD_DIR, filename))
            file_type = safe.rsplit(".", 1)[1].lower()
        if not title:
            flash("Title is required.", "danger")
            return redirect(url_for("notes"))
        db.execute("""INSERT INTO notes(user_id,title,subject,description,filename,file_type)
                      VALUES(?,?,?,?,?,?)""",
                   (session["user_id"], title, subject, description, filename, file_type))
        db.commit()
        flash("Note uploaded.", "success")
        return redirect(url_for("notes"))

    q = request.args.get("q", "").strip()
    if q:
        rows = db.execute("""SELECT * FROM notes WHERE title LIKE ? OR subject LIKE ?
                              OR description LIKE ? ORDER BY id DESC""",
                          (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM notes ORDER BY id DESC").fetchall()
    return render_template("notes.html", notes=rows, q=q)


@app.route("/notes/delete/<int:nid>", methods=["POST"])
@login_required
def delete_note(nid):
    db = get_db()
    row = db.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    if row and row["filename"]:
        try:
            os.remove(os.path.join(UPLOAD_DIR, row["filename"]))
        except OSError:
            pass
    db.execute("DELETE FROM notes WHERE id=?", (nid,))
    db.commit()
    flash("Note deleted.", "info")
    return redirect(url_for("notes"))


@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename, as_attachment=True)


# ---------- Blood Donors ----------
@app.route("/donors", methods=["GET", "POST"])
@login_required
def donors():
    db = get_db()
    if request.method == "POST":
        db.execute("""INSERT INTO blood_donors(name,blood_group,phone,city,email)
                      VALUES(?,?,?,?,?)""",
                   (request.form.get("name", "").strip(),
                    request.form.get("blood_group", "").strip(),
                    request.form.get("phone", "").strip(),
                    request.form.get("city", "").strip(),
                    request.form.get("email", "").strip()))
        db.commit()
        flash("Donor registered.", "success")
        return redirect(url_for("donors"))

    q = request.args.get("q", "").strip()
    bg = request.args.get("bg", "").strip()
    sql = "SELECT * FROM blood_donors WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR city LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if bg:
        sql += " AND blood_group=?"
        params.append(bg)
    sql += " ORDER BY id DESC"
    rows = db.execute(sql, params).fetchall()
    return render_template("donors.html", donors=rows, q=q, bg=bg)


@app.route("/donors/delete/<int:did>", methods=["POST"])
@login_required
def delete_donor(did):
    db = get_db()
    db.execute("DELETE FROM blood_donors WHERE id=?", (did,))
    db.commit()
    flash("Donor removed.", "info")
    return redirect(url_for("donors"))


# ---------- Lost & Found ----------
@app.route("/lostfound", methods=["GET", "POST"])
@login_required
def lostfound():
    db = get_db()
    if request.method == "POST":
        db.execute("""INSERT INTO lost_found(user_id,item_type,title,category,description,location,contact,status)
                      VALUES(?,?,?,?,?,?,?,?)""",
                   (session["user_id"],
                    request.form.get("item_type", "lost"),
                    request.form.get("title", "").strip(),
                    request.form.get("category", "").strip(),
                    request.form.get("description", "").strip(),
                    request.form.get("location", "").strip(),
                    request.form.get("contact", "").strip(),
                    request.form.get("status", "open")))
        db.commit()
        flash("Post added.", "success")
        return redirect(url_for("lostfound"))

    q = request.args.get("q", "").strip()
    t = request.args.get("t", "").strip()
    sql = "SELECT * FROM lost_found WHERE 1=1"
    params = []
    if q:
        sql += " AND (title LIKE ? OR description LIKE ? OR location LIKE ? OR category LIKE ?)"
        params += [f"%{q}%"]*4
    if t:
        sql += " AND item_type=?"
        params.append(t)
    sql += " ORDER BY id DESC"
    rows = db.execute(sql, params).fetchall()
    return render_template("lostfound.html", posts=rows, q=q, t=t)


@app.route("/lostfound/delete/<int:pid>", methods=["POST"])
@login_required
def delete_lostfound(pid):
    db = get_db()
    db.execute("DELETE FROM lost_found WHERE id=?", (pid,))
    db.commit()
    flash("Post deleted.", "info")
    return redirect(url_for("lostfound"))


# ---------- Static pages ----------
@app.route("/profile")
@login_required
def profile():
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    counts = {
        "notes": db.execute("SELECT COUNT(*) c FROM notes WHERE user_id=?", (session["user_id"],)).fetchone()["c"],
        "lost_found": db.execute("SELECT COUNT(*) c FROM lost_found WHERE user_id=?", (session["user_id"],)).fetchone()["c"],
    }
    return render_template("profile.html", user=user, counts=counts)


@app.route("/about")
def about():
    return render_template("info.html", title="About EduVerse",
                           body="EduVerse is a modern student community platform for sharing notes, connecting blood donors, and helping students recover lost items.")


@app.route("/contact")
def contact():
    return render_template("info.html", title="Contact",
                           body="Email: support@eduverse.local  •  Phone: +00 000 0000")


@app.route("/privacy")
def privacy():
    return render_template("info.html", title="Privacy Policy",
                           body="We only store the data you submit. Passwords are hashed. Files are stored locally.")


@app.route("/terms")
def terms():
    return render_template("info.html", title="Terms of Use",
                           body="Use EduVerse responsibly. Do not upload copyrighted material without permission.")


# ---------- Entrypoint ----------
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000/")


if __name__ == "__main__":
    init_db()
    if not os.environ.get("WERKZEUG_RUN_MAIN"):
        threading.Timer(1.2, open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=True)
