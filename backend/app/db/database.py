import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.auth.security import generate_access_token, generate_salt, hash_password, verify_password

DB_PATH = Path("backend/data/app.db")
SESSION_TTL_DAYS = 7
VERIFICATION_TTL_MINUTES = 10


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(cur: sqlite3.Cursor, table: str, column: str, definition: str) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    columns = {row["name"] for row in cur.fetchall()}
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db() -> None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                default_language TEXT,
                avg_temperature REAL,
                avg_humidity REAL,
                avg_rainfall REAL,
                weather_city TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(cur, "users", "email", "TEXT UNIQUE")
        _ensure_column(cur, "users", "default_language", "TEXT")
        _ensure_column(cur, "users", "avg_temperature", "REAL")
        _ensure_column(cur, "users", "avg_humidity", "REAL")
        _ensure_column(cur, "users", "avg_rainfall", "REAL")
        _ensure_column(cur, "users", "weather_city", "TEXT")

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                endpoint TEXT NOT NULL,
                input_payload TEXT NOT NULL,
                weather_used TEXT NOT NULL,
                top_predictions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.commit()


def start_email_registration(email: str, username: str, password: str) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=VERIFICATION_TTL_MINUTES)
    salt = generate_salt()
    password_hash = hash_password(password, salt)
    code = f"{secrets.randbelow(1_000_000):06d}"

    normalized_email = email.strip().lower()
    normalized_username = username.strip().lower()

    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = ?", (normalized_username,))
        if cur.fetchone():
            raise ValueError("Username already exists")

        cur.execute("SELECT id FROM users WHERE email = ?", (normalized_email,))
        if cur.fetchone():
            raise ValueError("Email already exists")

        cur.execute("DELETE FROM email_verifications WHERE email = ?", (normalized_email,))
        cur.execute(
            """
            INSERT INTO email_verifications(email, username, password_hash, salt, code, expires_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_email,
                normalized_username,
                password_hash,
                salt,
                code,
                expires.isoformat(),
                now.isoformat(),
            ),
        )
        conn.commit()

    return code, expires.isoformat()


def verify_email_and_create_user(email: str, code: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    now = datetime.now(timezone.utc)

    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT email, username, password_hash, salt, code, expires_at
            FROM email_verifications
            WHERE email = ?
            ORDER BY datetime(created_at) DESC
            LIMIT 1
            """,
            (normalized_email,),
        )
        row = cur.fetchone()
        if not row:
            raise ValueError("No pending verification found for this email")

        if row["code"] != code.strip():
            raise ValueError("Invalid verification code")

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < now:
            raise ValueError("Verification code has expired")

        try:
            cur.execute(
                """
                INSERT INTO users(username, email, password_hash, salt, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["username"],
                    row["email"],
                    row["password_hash"],
                    row["salt"],
                    now.isoformat(),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("User already exists") from exc

        user_id = int(cur.lastrowid)
        cur.execute("DELETE FROM email_verifications WHERE email = ?", (normalized_email,))
        conn.commit()

    return {
        "id": user_id,
        "username": row["username"],
        "email": row["email"],
        "created_at": now.isoformat(),
    }


def create_user(username: str, password: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    salt = generate_salt()
    password_hash = hash_password(password, salt)

    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username.strip().lower(), password_hash, salt, now),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists") from exc

        user_id = int(cur.lastrowid)
        return {"id": user_id, "username": username.strip().lower(), "created_at": now}


def create_session(username: str, password: str) -> dict[str, Any]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, username, email, default_language, password_hash, salt FROM users WHERE username = ?",
            (username.strip().lower(),),
        )
        user_row = cur.fetchone()
        if not user_row:
            raise ValueError("Invalid username or password")

        if not verify_password(password, user_row["salt"], user_row["password_hash"]):
            raise ValueError("Invalid username or password")

        token = generate_access_token()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=SESSION_TTL_DAYS)
        cur.execute(
            "INSERT INTO sessions(token, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
            (token, int(user_row["id"]), now.isoformat(), expires.isoformat()),
        )
        conn.commit()

        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_at": expires.isoformat(),
            "user": {
                "id": int(user_row["id"]),
                "username": user_row["username"],
                "email": user_row["email"],
                "default_language": user_row["default_language"],
            },
        }


def update_user_language(user_id: int, language: str) -> None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET default_language = ? WHERE id = ?", (language, user_id))
        conn.commit()


def update_user_weather_profile(
    user_id: int,
    city: str | None,
    avg_temperature: float,
    avg_humidity: float,
    avg_rainfall: float,
) -> None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE users
            SET weather_city = ?, avg_temperature = ?, avg_humidity = ?, avg_rainfall = ?
            WHERE id = ?
            """,
            (city, avg_temperature, avg_humidity, avg_rainfall, user_id),
        )
        conn.commit()


def get_user_weather_profile(user_id: int) -> dict[str, Any] | None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT avg_temperature, avg_humidity, avg_rainfall, weather_city FROM users WHERE id = ?",
            (user_id,),
        )
        row = cur.fetchone()
        if not row or row["avg_temperature"] is None:
            return None
        return {
            "avg_temperature": float(row["avg_temperature"]),
            "avg_humidity": float(row["avg_humidity"] or 65.0),
            "total_rainfall": float(row["avg_rainfall"] or 80.0),
            "cached_city": row["weather_city"],
        }


def get_user_by_token(token: str) -> dict[str, Any] | None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.username, u.email, u.default_language, s.expires_at
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        )
        row = cur.fetchone()
        if not row:
            return None

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < datetime.now(timezone.utc):
            cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
            return None

        return {
            "id": int(row["id"]),
            "username": row["username"],
            "email": row["email"],
            "default_language": row["default_language"],
        }


def save_recommendation(
    user_id: int,
    endpoint: str,
    input_payload: dict[str, Any],
    weather_used: dict[str, Any],
    top_predictions: list[dict[str, Any]],
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO recommendations(user_id, endpoint, input_payload, weather_used, top_predictions, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                endpoint,
                json.dumps(input_payload),
                json.dumps(weather_used),
                json.dumps(top_predictions),
                now,
            ),
        )
        conn.commit()


def get_recent_recommendations(user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, endpoint, input_payload, weather_used, top_predictions, created_at
            FROM recommendations
            WHERE user_id = ?
            ORDER BY datetime(created_at) DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = cur.fetchall()

    return [
        {
            "id": int(row["id"]),
            "endpoint": row["endpoint"],
            "input_payload": json.loads(row["input_payload"]),
            "weather_used": json.loads(row["weather_used"]),
            "top_predictions": json.loads(row["top_predictions"]),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
