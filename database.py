import sqlite3
import hashlib
import os


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DATABASE_NAME = "students.db"


# =========================================================
# CONNECT TO DATABASE
# =========================================================

def connect_db():
    return sqlite3.connect(DATABASE_NAME)


# =========================================================
# CREATE TABLES
# =========================================================

def create_tables():

    connection = connect_db()
    cursor = connection.cursor()

    # -----------------------------------------------------
    # STUDENTS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # ATTEMPTS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            student_id INTEGER NOT NULL,

            game_type TEXT NOT NULL,

            question TEXT NOT NULL,

            student_answer INTEGER,

            correct_answer INTEGER NOT NULL,

            is_correct INTEGER NOT NULL,

            response_time REAL NOT NULL,

            difficulty_before INTEGER NOT NULL,

            difficulty_after INTEGER NOT NULL,

            decision TEXT NOT NULL,

            decision_reason TEXT,

            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (student_id)
                REFERENCES students(id)
                ON DELETE CASCADE
        )
    """)

    # -----------------------------------------------------
    # SESSION ID COLUMN (added for teacher dashboard grouping)
    # Added safely with ALTER TABLE so existing attempt rows
    # and the existing schema are never destroyed.
    # -----------------------------------------------------

    cursor.execute("PRAGMA table_info(attempts)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    if "session_id" not in existing_columns:
        cursor.execute("ALTER TABLE attempts ADD COLUMN session_id TEXT")

    # -----------------------------------------------------
    # TEACHERS TABLE (new - required for Teacher Dashboard)
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    """)

    connection.commit()

    # Create a default teacher account if none exist yet, so the
    # dashboard is reachable on a fresh install without breaking
    # anything that already exists.
    cursor.execute("SELECT COUNT(*) FROM teachers")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO teachers (username, password_hash) VALUES (?, ?)",
            ("teacher", _hash_password("teacher123"))
        )
        connection.commit()

    connection.close()


# =========================================================
# TEACHER AUTH HELPERS
# =========================================================

def _hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_teacher(username, password):
    """Returns True if the username/password combo matches a teacher row."""
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT password_hash FROM teachers WHERE username = ?",
        (username.strip(),)
    )
    row = cursor.fetchone()
    connection.close()

    if row is None:
        return False

    return row[0] == _hash_password(password)


# =========================================================
# ADD STUDENT
# =========================================================

def add_student(first_name):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO students (first_name)
        VALUES (?)
        """,
        (first_name,)
    )

    connection.commit()
    connection.close()


# =========================================================
# GET ALL STUDENTS
# =========================================================

def get_students():

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, first_name
        FROM students
        ORDER BY first_name
        """
    )

    students = cursor.fetchall()

    connection.close()

    return students


# =========================================================
# DELETE STUDENT
# =========================================================

def delete_student(student_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM students
        WHERE id = ?
        """,
        (student_id,)
    )

    connection.commit()

    deleted = cursor.rowcount

    connection.close()

    return deleted


# =========================================================
# SAVE GAME ATTEMPT
# =========================================================

def save_attempt(
    student_id,
    game_type,
    question,
    student_answer,
    correct_answer,
    is_correct,
    response_time,
    difficulty_before,
    difficulty_after,
    decision,
    decision_reason,
    session_id=None
):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO attempts (
            student_id,
            game_type,
            question,
            student_answer,
            correct_answer,
            is_correct,
            response_time,
            difficulty_before,
            difficulty_after,
            decision,
            decision_reason,
            session_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            student_id,
            game_type,
            question,
            student_answer,
            correct_answer,
            int(is_correct),
            response_time,
            difficulty_before,
            difficulty_after,
            decision,
            decision_reason,
            session_id
        )
    )

    connection.commit()
    connection.close()


# =========================================================
# GET STUDENT ATTEMPTS
# =========================================================

def get_student_attempts(student_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            game_type,
            question,
            student_answer,
            correct_answer,
            is_correct,
            response_time,
            difficulty_before,
            difficulty_after,
            decision,
            decision_reason,
            timestamp
        FROM attempts
        WHERE student_id = ?
        ORDER BY timestamp ASC
        """,
        (student_id,)
    )

    attempts = cursor.fetchall()

    connection.close()

    return attempts


# =========================================================
# GET STUDENT PERFORMANCE SUMMARY
# =========================================================

def get_student_performance(student_id):

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_attempts,

            SUM(
                CASE
                    WHEN is_correct = 1 THEN 1
                    ELSE 0
                END
            ) AS correct_answers,

            AVG(response_time) AS average_response_time,

            MAX(difficulty_after) AS highest_difficulty

        FROM attempts

        WHERE student_id = ?
        """,
        (student_id,)
    )

    performance = cursor.fetchone()

    connection.close()

    return performance


# =========================================================
# CENTRALIZED PERFORMANCE STATUS
# (kept identical to the original inline logic used
# throughout main.py: score > 7 -> MASTERED,
# score > 3 -> DEVELOPING, else -> NEEDS SUPPORT)
# =========================================================

def get_performance_status(score, total_questions):
    if score > 7:
        return "MASTERED"
    elif score > 3:
        return "DEVELOPING"
    else:
        return "NEEDS SUPPORT"


# =========================================================
# TEACHER DASHBOARD DATA
# =========================================================
#
# Individual question attempts are stored one row per
# question (as before). To show the teacher per-activity
# "attempts / best score / average time" the rows are
# grouped back into play sessions using session_id (each
# full 10-question playthrough shares one session_id).
# Rows saved before session_id existed (session_id IS NULL)
# are grouped one-row-per-session so no old data is lost.

def get_student_dashboard_summary(student_id):
    """
    Returns a dict:
    {
        "GAME_TYPE": [
            {
                "session_id": ...,
                "attempts": <question count in that session>,
                "score": <correct answers in that session>,
                "total_questions": <question count in that session>,
                "average_time": <avg response_time in that session>,
                "status": "MASTERED" / "DEVELOPING" / "NEEDS SUPPORT",
                "last_timestamp": <timestamp of last question>
            },
            ...
        ],
        ...
    }
    Sessions are ordered oldest -> newest per game type.
    """

    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            game_type,
            session_id,
            id,
            is_correct,
            response_time,
            timestamp
        FROM attempts
        WHERE student_id = ?
        ORDER BY game_type ASC, timestamp ASC, id ASC
        """,
        (student_id,)
    )

    rows = cursor.fetchall()
    connection.close()

    summary = {}

    # Group rows into sessions. A NULL session_id (legacy rows
    # saved before this feature existed) is treated as its own
    # one-row session so nothing is dropped or merged incorrectly.
    sessions = {}
    order = []

    for game_type, session_id, attempt_id, is_correct, response_time, timestamp in rows:
        key = (game_type, session_id if session_id else f"legacy-{attempt_id}")
        if key not in sessions:
            sessions[key] = {
                "game_type": game_type,
                "session_id": session_id,
                "attempts": 0,
                "score": 0,
                "time_sum": 0.0,
                "last_timestamp": timestamp
            }
            order.append(key)

        entry = sessions[key]
        entry["attempts"] += 1
        entry["score"] += int(is_correct)
        entry["time_sum"] += response_time or 0.0
        entry["last_timestamp"] = timestamp

    for key in order:
        entry = sessions[key]
        game_type = entry["game_type"]
        total_questions = entry["attempts"]
        average_time = entry["time_sum"] / entry["attempts"] if entry["attempts"] else 0.0

        summary.setdefault(game_type, []).append({
            "session_id": entry["session_id"],
            "attempts": entry["attempts"],
            "score": entry["score"],
            "total_questions": total_questions,
            "average_time": average_time,
            "status": get_performance_status(entry["score"], total_questions),
            "last_timestamp": entry["last_timestamp"]
        })

    return summary


def get_all_students_dashboard_summary():
    """Returns {student_id: {"name": ..., "summary": get_student_dashboard_summary(...)}}"""
    result = {}
    for student_id, name in get_students():
        result[student_id] = {
            "name": name,
            "summary": get_student_dashboard_summary(student_id)
        }
    return result
