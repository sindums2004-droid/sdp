import os
import sqlite3
import re
from datetime import date
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, jsonify, g
)

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "mevi-workshop-development-key"
)

# Database configuration
os.makedirs(app.instance_path, exist_ok=True)

DATABASE = os.environ.get(
    "DATABASE_PATH",
    os.path.join(app.instance_path, "management.db")
)


# Database connection
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row

    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()
        if exception is not None:
            app.logger.error("Database connection closed after an exception")


# Create database table
def init_db():
    with sqlite3.connect(DATABASE) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                course TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


init_db()


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def find_student(student_id):
    return get_db().execute(
        "SELECT * FROM students WHERE id = ?",
        (student_id,)
    ).fetchone()


def get_request_data():
    if request.is_json:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    return request.form


def validate_student_data(data, required=True):
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    course = str(data.get("course", "")).strip()

    if required and (not name or not email or not course):
        return None, "Name, email, and course are required."
    if email and not EMAIL_PATTERN.match(email):
        return None, "Please enter a valid email address."

    return {
        "name": name,
        "email": email,
        "course": course,
    }, None


# Dashboard
@app.route("/")
def dashboard():
    db = get_db()

    total_students = db.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    total_courses = db.execute(
        "SELECT COUNT(DISTINCT course) FROM students"
    ).fetchone()[0]

    today = date.today()
    current_month = date(today.year, today.month, 1)
    month_index = today.year * 12 + today.month - 1
    first_month_index = month_index - 5
    first_month_year, first_month_number = divmod(first_month_index, 12)
    first_month = date(first_month_year, first_month_number + 1, 1)
    if today.month == 12:
        next_month = date(today.year + 1, 1, 1)
    else:
        next_month = date(today.year, today.month + 1, 1)

    month_counts = {
        row["month"]: row["total"]
        for row in db.execute(
            """
            SELECT strftime('%Y-%m', created_at) AS month, COUNT(*) AS total
            FROM students
            WHERE created_at >= ? AND created_at < ?
            GROUP BY month
            """,
            (first_month.isoformat(), next_month.isoformat())
        ).fetchall()
    }

    chart_months = []
    for offset in range(6):
        index = first_month_index + offset
        year, month_number = divmod(index, 12)
        month_date = date(year, month_number + 1, 1)
        month_key = month_date.strftime("%Y-%m")
        chart_months.append({
            "label": month_date.strftime("%b"),
            "count": month_counts.get(month_key, 0),
        })

    peak_enrollments = max((month["count"] for month in chart_months), default=0)
    for month in chart_months:
        month["height"] = (
            round(month["count"] / peak_enrollments * 100)
            if peak_enrollments
            else 0
        )

    recent_students = db.execute(
        "SELECT * FROM students ORDER BY id DESC LIMIT 5"
    ).fetchall()

    return render_template(
        "index.html",
        total_students=total_students,
        total_courses=total_courses,
        new_this_month=month_counts.get(current_month.strftime("%Y-%m"), 0),
        chart_months=chart_months,
        recent_students=recent_students
    )


# Student management page
@app.route("/students")
def students():
    db = get_db()

    all_students = db.execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()

    return render_template(
        "students.html",
        students=all_students
    )


# Add student
@app.route("/students/add", methods=["POST"])
def add_student():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    course = request.form.get("course", "").strip()

    if not name or not email or not course:
        flash("Please fill in all fields.", "error")
        return redirect(url_for("students"))

    if not EMAIL_PATTERN.match(email):
        flash("Please enter a valid email address.", "error")
        return redirect(url_for("students"))

    db = get_db()

    try:
        db.execute(
            """
            INSERT INTO students (name, email, course)
            VALUES (?, ?, ?)
            """,
            (name, email, course)
        )
        db.commit()

        flash("Student added successfully!", "success")

    except sqlite3.IntegrityError:
        flash("This email address is already registered.", "error")

    return redirect(url_for("students"))


# Edit student
@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
def edit_student(student_id):
    student = find_student(student_id)
    if student is None:
        return render_template("404.html"), 404

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        course = request.form.get("course", "").strip()

        if not name or not email or not course:
            flash("Please fill in all fields.", "error")
        elif not EMAIL_PATTERN.match(email):
            flash("Please enter a valid email address.", "error")
        else:
            try:
                get_db().execute(
                    """
                    UPDATE students
                    SET name = ?, email = ?, course = ?
                    WHERE id = ?
                    """,
                    (name, email, course, student_id)
                )
                get_db().commit()
                flash("Student record updated.", "success")
                return redirect(url_for("students"))
            except sqlite3.IntegrityError:
                flash("This email address is already registered.", "error")

    return render_template("edit.html", student=student)


# Delete student
@app.route("/students/<int:student_id>/delete", methods=["POST"])
def delete_student(student_id):
    db = get_db()
    student = find_student(student_id)
    if student is None:
        return jsonify({"error": "Student not found"}), 404

    db.execute(
        "DELETE FROM students WHERE id = ?",
        (student_id,)
    )
    db.commit()

    flash("Student record deleted.", "success")

    return redirect(url_for("students"))


# JSON CRUD API
@app.route("/api/students", methods=["GET", "POST"])
def students_api():
    if request.method == "POST":
        values, error = validate_student_data(get_request_data())
        if error:
            return jsonify({"error": error}), 400

        try:
            cursor = get_db().execute(
                """
                INSERT INTO students (name, email, course)
                VALUES (?, ?, ?)
                """,
                (values["name"], values["email"], values["course"])
            )
            get_db().commit()
            student = find_student(cursor.lastrowid)
            return jsonify(dict(student)), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "This email address is already registered."}), 409

    records = get_db().execute(
        "SELECT * FROM students ORDER BY id DESC"
    ).fetchall()
    return jsonify([dict(record) for record in records])


@app.route(
    "/api/students/<int:student_id>",
    methods=["GET", "PUT", "PATCH", "DELETE"]
)
def student_api(student_id):
    student = find_student(student_id)
    if student is None:
        return jsonify({"error": "Student not found"}), 404

    if request.method == "GET":
        return jsonify(dict(student))

    if request.method == "DELETE":
        get_db().execute(
            "DELETE FROM students WHERE id = ?",
            (student_id,)
        )
        get_db().commit()
        return "", 204

    data = get_request_data()
    required = request.method == "PUT"
    values, error = validate_student_data(data, required=required)
    if error:
        return jsonify({"error": error}), 400

    if request.method == "PATCH":
        updated = dict(student)
        for field in ("name", "email", "course"):
            if field in data:
                updated[field] = values[field]
        values = {
            "name": updated["name"],
            "email": updated["email"],
            "course": updated["course"],
        }

    try:
        get_db().execute(
            """
            UPDATE students
            SET name = ?, email = ?, course = ?
            WHERE id = ?
            """,
            (values["name"], values["email"], values["course"], student_id)
        )
        get_db().commit()
        updated_student = find_student(student_id)
        return jsonify(dict(updated_student))
    except sqlite3.IntegrityError:
        return jsonify({"error": "This email address is already registered."}), 409


# Health check
@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "application": "MEVI Management Portal"
    })


@app.errorhandler(404)
def page_not_found(error):
    app.logger.debug("Page not found: %s", error)
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("404.html"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5001"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )