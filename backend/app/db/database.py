import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backend.app.auth.security import generate_access_token, generate_salt, hash_password, verify_password

DB_PATH = Path("backend/data/app.db")
SESSION_TTL_DAYS = 7


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
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


def create_user(username: str, password: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    salt = generate_salt()
    password_hash = hash_password(password, salt)

    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username.strip(), password_hash, salt, now),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("Username already exists") from exc

        user_id = int(cur.lastrowid)
        return {"id": user_id, "username": username.strip(), "created_at": now}


def create_session(username: str, password: str) -> dict[str, Any]:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash, salt FROM users WHERE username = ?", (username.strip(),))
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
            "user": {"id": int(user_row["id"]), "username": user_row["username"]},
        }


def get_user_by_token(token: str) -> dict[str, Any] | None:
    with closing(_get_conn()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.id, u.username, s.expires_at
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

        return {"id": int(row["id"]), "username": row["username"]}


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
