import hashlib
import hmac
import os
import re
import sqlite3
from pathlib import Path

# Anchor the user database at the project root (two levels above src/auth/) so it
# stays put no matter which working directory the API or a Streamlit app is run from.
# TESSERA_DB_PATH lets a container mount it on a persistent volume instead.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.environ.get("TESSERA_DB_PATH", _PROJECT_ROOT / "tessera_users.db"))
PBKDF2_ITERATIONS = 200000
PBKDF2_ALGO = "pbkdf2_sha256"
ADMIN_EMAIL = os.environ.get("TESSERA_ADMIN_EMAIL", "gantaamith007@gmail.com")


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_token TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );

            CREATE TABLE IF NOT EXISTS user_queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                route TEXT,
                tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"{PBKDF2_ALGO}${PBKDF2_ITERATIONS}${salt.hex()}${hash_bytes.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    if password is None or password_hash is None or "$" not in password_hash:
        return False

    try:
        algo, iterations_str, salt_hex, hash_hex = password_hash.split("$", 3)
        if algo != PBKDF2_ALGO:
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)
        computed_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(computed_hash, expected_hash)
    except (ValueError, TypeError, AttributeError):
        return False


def user_exists(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT 1 FROM users WHERE email = ?", (email,))
        return c.fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def create_user(email: str, password: str) -> tuple[bool, str]:
    if not email or not password:
        return False, "Email and password are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters long."

    email = email.strip().lower()
    if user_exists(email):
        return False, "User already exists."

    password_hash = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        conn.commit()
        return True, "User created."
    except sqlite3.IntegrityError:
        return False, "User already exists."
    except sqlite3.Error:
        return False, "Database error."
    finally:
        conn.close()


def authenticate_user(email: str, password: str) -> tuple[bool, str, int | None]:
    if not email or not password:
        return False, "Email and password are required.", None

    user_id = get_user_id_from_email(email)
    if user_id is None:
        return False, "Invalid email or password.", None

    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        if row is None:
            return False, "Invalid email or password.", None

        if not verify_password(password, row[0]):
            return False, "Invalid email or password.", None

        c.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))
        conn.commit()
        return True, "Login successful.", user_id
    except sqlite3.Error:
        return False, "Database error.", None
    finally:
        conn.close()


def get_user_email(user_id: int) -> str | None:
    if not user_id:
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT email FROM users WHERE id = ?", (user_id,))
        row = c.fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def get_user_id_from_email(email: str) -> int | None:
    if not email:
        return None
    email = email.strip().lower()
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def log_query(
    user_id: int, question: str, answer: str, route: str, tokens: int, cost: float
) -> bool:
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO user_queries (user_id, question, answer, route, tokens, cost) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, question, answer, route, tokens, cost),
        )
        conn.commit()
        return c.rowcount > 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def get_user_stats(user_id: int) -> dict:
    stats = {"total_queries": 0, "total_tokens": 0, "total_cost_usd": 0.0}
    conn = sqlite3.connect(DB_PATH)
    try:
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*), COALESCE(SUM(tokens), 0), COALESCE(SUM(cost), 0) FROM user_queries WHERE user_id = ?",
            (user_id,),
        )
        row = c.fetchone()
        if row:
            stats["total_queries"] = int(row[0] or 0)
            stats["total_tokens"] = int(row[1] or 0)
            stats["total_cost_usd"] = float(row[2] or 0.0)
        return stats
    except sqlite3.Error:
        return stats
    finally:
        conn.close()


def tenant_slug(user_id: int) -> str:
    # Derived multi tenant id, matches the required pattern with a plain hyphen.
    return "user" + chr(45) + str(int(user_id))


def is_admin(email: str | None) -> bool:
    return email is not None and email.strip().lower() == ADMIN_EMAIL.strip().lower()


if not DB_PATH.exists():
    init_db()
