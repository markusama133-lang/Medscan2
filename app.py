import os
import math
import sqlite3
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)
app.secret_key = "medscan_production_secret_key"
DB_PATH = os.path.join(os.path.dirname(__file__), "medscan_attendance.db")
SQL_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "medscan_database.sql")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    exists = cur.fetchone()
    if not exists and os.path.exists(SQL_SCHEMA_PATH):
        with open(SQL_SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql_script = f.read().replace("LONGTEXT", "TEXT").replace("DOUBLE", "REAL")
            cur.executescript(sql_script)
        conn.commit()
    conn.close()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state", methods=["GET"])
def api_get_state():
    conn = get_db()
    s_row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    u_rows = conn.execute("SELECT * FROM users ORDER BY created_at ASC").fetchall()
    e_rows = conn.execute("SELECT * FROM early_departure_requests ORDER BY created_at DESC").fetchall()
    l_rows = conn.execute("SELECT * FROM attendance_logs ORDER BY created_at DESC").fetchall()
    conn.close()

    return jsonify({
        "settings": {
            "branchName": s_row["branch_name"],
            "lat": s_row["lat"],
            "lng": s_row["lng"],
            "allowedRadiusMeters": s_row["allowed_radius_meters"],
            "graceMinutes": s_row["grace_minutes"],
            "roundingMode": s_row["rounding_mode"],
        },
        "users": [
            {
                "id": u["id"],
                "name": u["name"],
                "email": u["email"],
                "password": u["password"],
                "role": u["role"],
                "activated": bool(u["activated"]),
                "title": u["title"],
                "baseSalary": u["base_salary"],
                "workDays": u["work_days"],
                "shiftStart": u["shift_start"],
                "shiftEnd": u["shift_end"],
                "customHourRate": u["custom_hour_rate"],
            }
            for u in u_rows
        ],
        "earlyRequests": [
            {
                "id": r["id"],
                "userId": r["user_id"],
                "userName": r["user_name"],
                "requestTime": r["request_time"],
                "shiftEnd": r["shift_end"],
                "reason": r["reason"],
                "status": r["status"],
            }
            for r in e_rows
        ],
        "logs": [
            {
                "id": l["id"],
                "userId": l["user_id"],
                "userName": l["user_name"],
                "type": l["action_type"],
                "dateStr": l["date_str"],
                "timeStr": l["time_str"],
                "shiftStart": l["shift_start"],
                "shiftEnd": l["shift_end"],
                "lat": l["lat"],
                "lng": l["lng"],
                "distanceMeters": l["distance_meters"],
                "lateMinutes": l["late_minutes"],
                "withinGrace": bool(l["within_grace"]),
                "deductedHours": l["deducted_hours"],
                "deductionAmount": l["deduction_amount"],
                "earlyReason": l["early_reason"],
                "photoDataUrl": l["photo_data_url"],
            }
            for l in l_rows
        ],
    })


@app.route("/api/sync", methods=["POST"])
def api_sync_state():
    data = request.get_json(force=True)
    conn = get_db()
    cur = conn.cursor()

    if "settings" in data:
        s = data["settings"]
        cur.execute(
            """UPDATE settings SET branch_name=?, lat=?, lng=?, allowed_radius_meters=?, grace_minutes=?, rounding_mode=? WHERE id=1""",
            (s["branchName"], s["lat"], s["lng"], s["allowedRadiusMeters"], s["graceMinutes"], s["roundingMode"]),
        )

    if "users" in data:
        cur.execute("DELETE FROM users")
        for u in data["users"]:
            cur.execute(
                """INSERT INTO users (id, name, email, password, role, activated, title, base_salary, work_days, shift_start, shift_end, custom_hour_rate)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    u["id"], u["name"], u["email"], u.get("password", ""), u["role"],
                    1 if u.get("activated") else 0, u.get("title", ""), u.get("baseSalary", 0),
                    u.get("workDays", 26), u.get("shiftStart", "09:00"), u.get("shiftEnd", "17:00"),
                    u.get("customHourRate", 0),
                ),
            )

    if "earlyRequests" in data:
        cur.execute("DELETE FROM early_departure_requests")
        for r in data["earlyRequests"]:
            cur.execute(
                """INSERT INTO early_departure_requests (id, user_id, user_name, request_time, shift_end, reason, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (r["id"], r["userId"], r["userName"], r["requestTime"], r["shiftEnd"], r["reason"], r["status"]),
            )

    if "logs" in data:
        cur.execute("DELETE FROM attendance_logs")
        for l in data["logs"]:
            cur.execute(
                """INSERT INTO attendance_logs (id, user_id, user_name, action_type, date_str, time_str, shift_start, shift_end, lat, lng, distance_meters, late_minutes, within_grace, deducted_hours, deduction_amount, early_reason, photo_data_url)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    l["id"], l["userId"], l["userName"], l["type"], l["dateStr"], l["timeStr"],
                    l["shiftStart"], l["shiftEnd"], l["lat"], l["lng"], l["distanceMeters"],
                    l["lateMinutes"], 1 if l.get("withinGrace") else 0, l["deductedHours"],
                    l["deductionAmount"], l.get("earlyReason", ""), l["photoDataUrl"],
                ),
            )

    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
