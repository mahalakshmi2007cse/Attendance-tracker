# Attendance Tracker
Frontend: HTML/CSS/JS (static/) | Backend: Python Flask (app.py) | Database: SQLite (attendance.db, created automatically)

## Run
1. Install Python 3.9 or newer.
2. `pip install -r requirements.txt`
3. `python app.py`
4. Open http://localhost:5000

The database file and demo data are created on the first run. Delete attendance.db to reset everything.

## Demo logins
| Role | Username | Password |
|---|---|---|
| Admin | admin | admin123 |
| Faculty | faculty | faculty123 |
| Student | student | student123 |

## Notes
- Low attendance threshold: change `THRESHOLD` in app.py (default 75).
- Percentage = Present days / total working days x 100 (a working day is any date with attendance recorded). Leave counts as not present.
- Biometric: /api/biometric receives a fingerprint ID (demo IDs FP001 to FP005). Connect a real scanner by posting its matched ID there.
- Change SECRET_KEY and the demo passwords before real use.
