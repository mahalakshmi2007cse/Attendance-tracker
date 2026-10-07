"""Run once: python setup_db.py  -> creates tables and demo data."""
import random
from datetime import date, timedelta
import mysql.connector
from werkzeug.security import generate_password_hash
from app import DB

cfg = {k: v for k, v in DB.items() if k != "database"}
con = mysql.connector.connect(**cfg); cur = con.cursor()
for stmt in open("schema.sql").read().split(";"):
    if stmt.strip(): cur.execute(stmt)
cur.execute("USE " + DB["database"])

students = [("CS001","Arun Kumar","CSE"),("CS002","Divya S","CSE"),("EC001","Karthik R","ECE"),
            ("EC002","Meena P","ECE"),("ME001","Suresh V","MECH")]
for i, (roll, name, dept) in enumerate(students, 1):
    cur.execute("INSERT IGNORE INTO students(roll_no,name,email,department,fingerprint_id) VALUES(%s,%s,%s,%s,%s)",
                (roll, name, f"{roll.lower()}@college.edu", dept, f"FP{i:03d}"))
con.commit()

users = [("admin","admin@college.edu","admin123","admin",None),
         ("faculty","faculty@college.edu","faculty123","faculty",None),
         ("student","student@college.edu","student123","student",1)]
for u, e, p, r, sid in users:
    cur.execute("INSERT IGNORE INTO users(username,email,password_hash,role,student_id) VALUES(%s,%s,%s,%s,%s)",
                (u, e, generate_password_hash(p), r, sid))

# 20 days of sample attendance (last student ends up below 75%)
random.seed(1); cur.execute("SELECT id FROM students")
ids = [r[0] for r in cur.fetchall()]
for d in range(1, 21):
    day = date.today() - timedelta(days=d)
    if day.weekday() > 4: continue
    for sid in ids:
        chance = 0.6 if sid == ids[-1] else 0.9
        st = "Present" if random.random() < chance else random.choice(["Absent", "Leave"])
        cur.execute("INSERT IGNORE INTO attendance(student_id,date,status,method) VALUES(%s,%s,%s,'Manual')", (sid, day, st))
con.commit(); con.close()
print("Done. Logins: admin/admin123, faculty/faculty123, student/student123")
