# course_store.py
import sqlite3
import json
from datetime import datetime
from pathlib  import Path

DB_PATH     = "courses.db"
COURSES_DIR = Path("courses")
COURSES_DIR.mkdir(exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS courses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT,
            description TEXT,
            level       TEXT,
            source      TEXT,
            content_json TEXT,
            created_at  TEXT
        );

        CREATE TABLE IF NOT EXISTS quizzes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id   INTEGER,
            module_num  INTEGER,
            module_title TEXT,
            quiz_json   TEXT,
            created_at  TEXT,
            FOREIGN KEY (course_id) REFERENCES courses(id)
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            quiz_id     INTEGER,
            learner     TEXT,
            score       INTEGER,
            total       INTEGER,
            percentage  INTEGER,
            answers_json TEXT,
            created_at  TEXT,
            FOREIGN KEY (quiz_id) REFERENCES quizzes(id)
        );
    """)
    conn.commit()
    conn.close()


def save_course(course: dict, source: str = "") -> int:
    conn = get_conn()
    cur  = conn.execute(
        "INSERT INTO courses (title, description, level, source, content_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            course.get("title", "Untitled"),
            course.get("description", ""),
            course.get("level", "Intermediate"),
            source,
            json.dumps(course),
            datetime.now().isoformat()
        )
    )
    conn.commit()
    course_id = cur.lastrowid
    conn.close()
    return course_id


def save_quiz(course_id: int, module_num: int, module_title: str, quiz: dict) -> int:
    conn = get_conn()
    cur  = conn.execute(
        "INSERT INTO quizzes (course_id, module_num, module_title, quiz_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (course_id, module_num, module_title, json.dumps(quiz), datetime.now().isoformat())
    )
    conn.commit()
    quiz_id = cur.lastrowid
    conn.close()
    return quiz_id


def save_attempt(
    quiz_id:    int,
    learner:    str,
    score:      int,
    total:      int,
    percentage: int,
    answers:    dict
):
    conn = get_conn()
    conn.execute(
        "INSERT INTO quiz_attempts "
        "(quiz_id, learner, score, total, percentage, answers_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (quiz_id, learner, score, total, percentage,
         json.dumps(answers), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_courses() -> list[dict]:
    conn  = get_conn()
    rows  = conn.execute(
        "SELECT id, title, description, level, source, created_at "
        "FROM courses ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_course(course_id: int) -> dict:
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM courses WHERE id = ?", (course_id,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["content"] = json.loads(d["content_json"])
        return d
    return {}


def get_quiz(quiz_id: int) -> dict:
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM quizzes WHERE id = ?", (quiz_id,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["quiz"] = json.loads(d["quiz_json"])
        return d
    return {}


def get_course_quizzes(course_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM quizzes WHERE course_id = ? ORDER BY module_num",
        (course_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_attempts(quiz_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM quiz_attempts WHERE quiz_id = ? ORDER BY created_at DESC",
        (quiz_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]