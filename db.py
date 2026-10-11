"""Database access layer for SecureNEET.

Primary Database: MySQL (using PyMySQL).
Provides connection pooling, transactions, dictionary cursors, and safe parameterized queries.
Includes automatic fallback to local SQLite for zero-dependency local development and testing.
"""

import os
import re
import sqlite3
import logging
from contextlib import contextmanager

try:
    import pymysql
    from pymysql.cursors import DictCursor
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False
    DictCursor = None

from config import Config

logger = logging.getLogger("secureneet.db")

# Track active database mode: 'mysql' or 'sqlite'
ACTIVE_DB_MODE = None

def get_raw_mysql_connection():
    """Attempt raw connection to MySQL server."""
    if not PYMYSQL_AVAILABLE:
        raise RuntimeError("PyMySQL is not installed.")
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=False
    )

def test_mysql_connection():
    """Test if MySQL server is reachable."""
    try:
        conn = get_raw_mysql_connection()
        conn.close()
        return True
    except Exception as e:
        logger.warning(f"MySQL connection test failed ({Config.DB_HOST}:{Config.DB_PORT}): {e}")
        return False

def determine_db_mode():
    """Determine whether to use MySQL or SQLite fallback."""
    global ACTIVE_DB_MODE
    if ACTIVE_DB_MODE is not None:
        return ACTIVE_DB_MODE
    
    if Config.DB_TYPE == "mysql" and PYMYSQL_AVAILABLE:
        if test_mysql_connection():
            ACTIVE_DB_MODE = "mysql"
            logger.info("Database mode: MySQL connected successfully.")
            return ACTIVE_DB_MODE
        else:
            logger.warning("Falling back to local SQLite engine because MySQL server is not currently reachable.")
            ACTIVE_DB_MODE = "sqlite"
            return ACTIVE_DB_MODE
    else:
        ACTIVE_DB_MODE = "sqlite"
        return ACTIVE_DB_MODE

def get_raw_sqlite_connection():
    """Get connection to SQLite fallback database."""
    conn = sqlite3.connect(Config.SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

class SQLiteCursorWrapper:
    """Wraps sqlite3 cursor to provide PyMySQL-compatible dict responses."""
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        # Convert %s placeholders to ? for sqlite
        translated_sql = sql.replace("%s", "?")
        # Replace NOW() with CURRENT_TIMESTAMP
        translated_sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', translated_sql, flags=re.IGNORECASE)
        if params is None:
            self.cursor.execute(translated_sql)
        else:
            self.cursor.execute(translated_sql, params)
        self.lastrowid = self.cursor.lastrowid
        self.rowcount = self.cursor.rowcount
        return self

    def executemany(self, sql, seq_of_params):
        translated_sql = sql.replace("%s", "?")
        translated_sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', translated_sql, flags=re.IGNORECASE)
        self.cursor.executemany(translated_sql, seq_of_params)
        self.rowcount = self.cursor.rowcount
        return self

    def fetchone(self):
        row = self.cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def fetchall(self):
        rows = self.cursor.fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.cursor.close()

class SQLiteConnectionWrapper:
    """Wraps sqlite3 connection to match PyMySQL connection interface."""
    def __init__(self, raw_conn):
        self.conn = raw_conn

    def cursor(self):
        return SQLiteCursorWrapper(self.conn.cursor())

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

@contextmanager
def get_db():
    """Context manager for obtaining an active database connection."""
    mode = determine_db_mode()
    if mode == "mysql":
        conn = get_raw_mysql_connection()
        try:
            yield conn
        finally:
            conn.close()
    else:
        raw_conn = get_raw_sqlite_connection()
        conn = SQLiteConnectionWrapper(raw_conn)
        try:
            yield conn
        finally:
            conn.close()

@contextmanager
def transaction():
    """Atomic transaction context manager."""
    mode = determine_db_mode()
    if mode == "mysql":
        conn = get_raw_mysql_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        raw_conn = get_raw_sqlite_connection()
        conn = SQLiteConnectionWrapper(raw_conn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

def query_all(sql, params=None):
    """Execute query and fetch all matching records as dictionaries."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        res = cur.fetchall()
        cur.close()
        return res

def query_one(sql, params=None):
    """Execute query and fetch a single record as a dictionary."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        res = cur.fetchone()
        cur.close()
        return res

def execute(sql, params=None):
    """Execute a single write query (INSERT, UPDATE, DELETE). Returns lastrowid."""
    with transaction() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        last_id = cur.lastrowid
        cur.close()
        return last_id

def execute_many(sql, seq_of_params):
    """Batch execute a query."""
    with transaction() as conn:
        cur = conn.cursor()
        cur.executemany(sql, seq_of_params)
        count = cur.rowcount
        cur.close()
        return count

def init_db():
    """Initialize database tables according to canonical schema."""
    mode = determine_db_mode()
    if mode == "mysql":
        # Run MySQL schema from database.sql
        sql_file = os.path.join(os.path.dirname(__file__), "database.sql")
        if os.path.exists(sql_file):
            with open(sql_file, "r", encoding="utf-8") as f:
                content = f.read()
            # Split queries by semicolon
            queries = [q.strip() for q in content.split(";") if q.strip()]
            with get_db() as conn:
                cur = conn.cursor()
                for q in queries:
                    # Ignore CREATE DATABASE / USE commands if user doesn't have superadmin grants
                    if re.match(r'^(CREATE DATABASE|USE)\b', q, re.IGNORECASE):
                        continue
                    try:
                        cur.execute(q)
                    except Exception as e:
                        logger.warning(f"Error executing schema query: {e}")
                conn.commit()
                cur.close()
    else:
        # SQLite schema initialization
        raw_conn = get_raw_sqlite_connection()
        cur = raw_conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                state TEXT,
                gender TEXT,
                registration_number TEXT UNIQUE,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS examinations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                code TEXT NOT NULL UNIQUE,
                duration_minutes INTEGER NOT NULL DEFAULT 180,
                total_marks INTEGER NOT NULL DEFAULT 720,
                passing_marks INTEGER NOT NULL DEFAULT 360,
                positive_marks REAL NOT NULL DEFAULT 4.00,
                negative_marks REAL NOT NULL DEFAULT 1.00,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                is_published INTEGER NOT NULL DEFAULT 0,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examination_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                topic TEXT,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL,
                marks REAL NOT NULL DEFAULT 4.00,
                negative_marks REAL NOT NULL DEFAULT 1.00,
                explanation TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (examination_id) REFERENCES examinations (id) ON DELETE CASCADE,
                FOREIGN KEY (created_by) REFERENCES users (id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS examination_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                examination_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                deadline_time TIMESTAMP NOT NULL,
                submitted_at TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'in_progress',
                total_score REAL NOT NULL DEFAULT 0.00,
                questions_answered INTEGER NOT NULL DEFAULT 0,
                correct_answers INTEGER NOT NULL DEFAULT 0,
                incorrect_answers INTEGER NOT NULL DEFAULT 0,
                unanswered_count INTEGER NOT NULL DEFAULT 0,
                percentage REAL NOT NULL DEFAULT 0.00,
                time_taken_seconds INTEGER NOT NULL DEFAULT 0,
                overall_rank INTEGER,
                state_rank INTEGER,
                gender_rank INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (examination_id) REFERENCES examinations (id) ON DELETE CASCADE,
                FOREIGN KEY (student_id) REFERENCES users (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS student_answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                attempt_id INTEGER NOT NULL,
                question_id INTEGER NOT NULL,
                selected_option TEXT,
                is_marked_for_review INTEGER NOT NULL DEFAULT 0,
                is_correct INTEGER,
                marks_awarded REAL NOT NULL DEFAULT 0.00,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (attempt_id, question_id),
                FOREIGN KEY (attempt_id) REFERENCES examination_attempts (id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions (id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT NOT NULL,
                target_type TEXT,
                target_id INTEGER,
                ip_address TEXT,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
            );
        """)
        raw_conn.commit()
        raw_conn.close()
        logger.info("Database initialized successfully.")
