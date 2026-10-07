import os
import random
import sqlite3
from datetime import date, timedelta
from functools import wraps
from flask import Flask, request, jsonify, session
from werkzeug.security import check_password_hash, generate_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE, "attendance.db")
THRESHOLD = 75  # minimum attendance %

app = Flask(__name__, static_folder=os.path.join(BASE, "static"), static_url_path="")
app.secret_key = os.getenv("SECRET_KEY", "change-this-secret")

SCHEMA = """
CREATE TABLE IF NOT EXISTS students (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  roll_no TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  email TEXT,
  department TEXT,
  fingerprint_id TEXT UNIQUE,
  active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  email TEXT UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('admin','faculty','student')),
  student_id INTEGER REFERENCES students(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS attendance (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
  date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('Present','Absent','Leave')),
  method TEXT NOT NULL DEFAULT 'Manual' CHECK (method IN ('Manual','Biometric')),
  marked_at TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (student_id, date)
);
"""


def connect():
    con = sqlite3.connect(DB_FILE)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def q(sql, args=(), one=False, commit=False):
    con = connect()
    try:
        cur = con.execute(sql, args)
        if commit:
            con.commit()
            return cur.lastrowid
        rows = [dict(r) for r in cur.fetchall()]
        return (rows[0] if rows else None) if one else rows
    finally:
        con.close()


def init_db():
    """Creates tables and demo data the first time the app starts."""
    con = connect()
    con.executescript(SCHEMA)
    if con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        demo = [("CS001", "Arun Kumar", "CSE"), ("CS002", "Divya S", "CSE"), ("EC001", "Karthik R", "ECE"),
                ("EC002", "Meena P", "ECE"), ("ME001", "Suresh V", "MECH")]
        for i, (roll, name, dept) in enumerate(demo, 1):
            con.execute("INSERT INTO students(roll_no,name,email,department,fingerprint_id) VALUES(?,?,?,?,?)",
                        (roll, name, f"{roll.lower()}@college.edu", dept, f"FP{i:03d}"))
        for u, e, p, r, sid in [("admin", "admin@college.edu", "admin123", "admin", None),
                                ("faculty", "faculty@college.edu", "faculty123", "faculty", None),
                                ("student", "student@college.edu", "student123", "student", 1)]:
            con.execute("INSERT INTO users(username,email,password_hash,role,student_id) VALUES(?,?,?,?,?)",
                        (u, e, generate_password_hash(p), r, sid))
        # 4 weeks of sample attendance; the last student is meant to fall below 75%
        rng = random.Random(7)
        for d in range(1, 29):
            day = date.today() - timedelta(days=d)
            if day.weekday() > 4:
                continue
            for sid in range(1, 6):
                if sid == 5:
                    st = "Present" if rng.random() < 0.55 else rng.choice(["Absent", "Leave"])
                else:
                    st = "Present" if rng.random() < 0.92 else rng.choice(["Absent", "Leave"])
                con.execute("INSERT INTO attendance(student_id,date,status,method) VALUES(?,?,?,'Manual')",
                            (sid, day.isoformat(), st))
        con.commit()
    con.close()


def auth(*roles):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = session.get("user")
            if not u:
                return jsonify(error="Please log in."), 401
            if roles and u["role"] not in roles:
                return jsonify(error="You don't have access to this."), 403
            return f(*a, **k)
        return w
    return deco


def stats(student_id=None, search=None, active_only=False):
    """Attendance % = present days / total working days x 100."""
    total = q("SELECT COUNT(DISTINCT date) AS n FROM attendance", one=True)["n"]
    sql = """SELECT s.id, s.roll_no, s.name, s.email, s.department, s.fingerprint_id, s.active,
             COALESCE(SUM(a.status='Present'),0) AS present,
             COALESCE(SUM(a.status='Absent'),0) AS absent,
             COALESCE(SUM(a.status='Leave'),0) AS on_leave
             FROM students s LEFT JOIN attendance a ON a.student_id = s.id WHERE 1=1"""
    args = []
    if student_id:
        sql += " AND s.id=?"; args.append(student_id)
    if search:
        sql += " AND (s.name LIKE ? OR s.roll_no LIKE ?)"; args += [f"%{search}%"] * 2
    if active_only:
        sql += " AND s.active=1"
    rows = q(sql + " GROUP BY s.id ORDER BY s.roll_no", args)
    for r in rows:
        r["total_days"] = total
        r["percentage"] = round(r["present"] / total * 100, 1) if total else 0.0
        r["low"] = total > 0 and r["percentage"] < THRESHOLD
    return rows


def today():
    return date.today().isoformat()


# ---------- Login ----------
@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    name = (d.get("username") or "").strip()
    u = q("SELECT * FROM users WHERE username=? OR email=?", (name, name), one=True)
    if not u or not check_password_hash(u["password_hash"], d.get("password", "")):
        return jsonify(error="Wrong username or password."), 401
    if u["role"] != d.get("role"):
        return jsonify(error=f"This account is not a {d.get('role')} account."), 403
    session["user"] = dict(id=u["id"], username=u["username"], role=u["role"], student_id=u["student_id"])
    return jsonify(session["user"])


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
@auth()
def me():
    return jsonify(session["user"])


# ---------- Dashboard ----------
@app.get("/api/dashboard")
@auth("admin", "faculty")
def dashboard():
    rows = stats(active_only=True)
    t = {r["status"]: r["n"] for r in q(
        "SELECT status, COUNT(*) AS n FROM attendance WHERE date=? GROUP BY status", (today(),))}
    return jsonify(total=len(rows), present=t.get("Present", 0), absent=t.get("Absent", 0),
                   on_leave=t.get("Leave", 0),
                   average=round(sum(r["percentage"] for r in rows) / len(rows), 1) if rows else 0,
                   low=[r for r in rows if r["low"]], threshold=THRESHOLD)


# ---------- Student management ----------
@app.get("/api/students")
@auth("admin", "faculty")
def students():
    return jsonify(stats(search=request.args.get("q")))


@app.post("/api/students")
@auth("admin")
def add_student():
    d = request.get_json(silent=True) or {}
    if not d.get("roll_no") or not d.get("name"):
        return jsonify(error="Roll no and name are required."), 400
    try:
        q("INSERT INTO students(roll_no,name,email,department,fingerprint_id) VALUES(?,?,?,?,?)",
          (d["roll_no"], d["name"], d.get("email"), d.get("department"), d.get("fingerprint_id") or None), commit=True)
    except sqlite3.IntegrityError:
        return jsonify(error="Roll no or fingerprint ID already exists."), 409
    return jsonify(ok=True)


@app.put("/api/students/<int:sid>")
@auth("admin")
def update_student(sid):
    d = request.get_json(silent=True) or {}
    try:
        q("UPDATE students SET name=?,email=?,department=?,fingerprint_id=?,active=? WHERE id=?",
          (d.get("name"), d.get("email"), d.get("department"), d.get("fingerprint_id") or None,
           int(d.get("active", 1)), sid), commit=True)
    except sqlite3.IntegrityError:
        return jsonify(error="That fingerprint ID is already used by another student."), 409
    return jsonify(ok=True)


@app.delete("/api/students/<int:sid>")
@auth("admin")
def deactivate(sid):
    q("UPDATE students SET active=0 WHERE id=?", (sid,), commit=True)  # soft delete keeps history
    return jsonify(ok=True)


@app.get("/api/students/<int:sid>/attendance")
@auth()
def student_attendance(sid):
    u = session["user"]
    if u["role"] == "student" and u["student_id"] != sid:
        return jsonify(error="Not allowed."), 403
    s = stats(student_id=sid)
    if not s:
        return jsonify(error="Student not found."), 404
    recs = q("SELECT date, status, method FROM attendance WHERE student_id=? ORDER BY date DESC", (sid,))
    return jsonify(student=s[0], records=recs)


# ---------- Manual attendance ----------
UPSERT = """INSERT INTO attendance(student_id,date,status,method) VALUES(?,?,?,?)
            ON CONFLICT(student_id,date) DO UPDATE SET status=excluded.status, method=excluded.method"""


@app.post("/api/attendance")
@auth("admin", "faculty")
def mark_manual():
    d = request.get_json(silent=True) or {}
    if d.get("status") not in ("Present", "Absent", "Leave"):
        return jsonify(error="Invalid status."), 400
    if not d.get("student_id"):
        return jsonify(error="Select a student."), 400
    q(UPSERT, (d["student_id"], d.get("date") or today(), d["status"], "Manual"), commit=True)
    return jsonify(ok=True)


# ---------- Biometric attendance ----------
@app.post("/api/biometric")
@auth("admin", "faculty")
def biometric():
    fid = ((request.get_json(silent=True) or {}).get("fingerprint_id") or "").strip()
    s = q("SELECT * FROM students WHERE fingerprint_id=? AND active=1", (fid,), one=True)  # identify
    if not s:
        return jsonify(error="Fingerprint not recognised."), 404
    ex = q("SELECT status FROM attendance WHERE student_id=? AND date=?", (s["id"], today()), one=True)  # check
    if ex and ex["status"] == "Present":
        return jsonify(message=f"{s['name']} is already marked present today.", student=s["name"])
    q(UPSERT, (s["id"], today(), "Present", "Biometric"), commit=True)  # mark + save
    return jsonify(message=f"{s['name']} marked present.", student=s["name"])


# ---------- Low attendance ----------
@app.get("/api/low-attendance")
@auth("admin", "faculty")
def low():
    return jsonify(threshold=THRESHOLD, students=[r for r in stats(active_only=True) if r["low"]])


@app.get("/")
def index():
    return app.send_static_file("index.html")


init_db()

if __name__ == "__main__":
    print("Open http://localhost:5000  (admin / admin123)")
    app.run(debug=False, port=5000)
