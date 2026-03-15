from __future__ import annotations

import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prices (
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                price REAL NOT NULL,
                prev_price REAL NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (symbol, exchange)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                time INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                side TEXT NOT NULL,
                qty INTEGER NOT NULL,
                type TEXT NOT NULL,
                limit_price REAL,
                status TEXT NOT NULL,
                filled_price REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                time INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                side TEXT NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT NOT NULL,
                exchange TEXT NOT NULL,
                qty INTEGER NOT NULL,
                avg_price REAL NOT NULL,
                PRIMARY KEY (symbol, exchange)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS instruments (
                instrument_token INTEGER PRIMARY KEY,
                tradingsymbol TEXT NOT NULL,
                name TEXT,
                exchange TEXT NOT NULL,
                segment TEXT NOT NULL,
                instrument_type TEXT,
                expiry TEXT,
                strike REAL,
                tick_size REAL,
                lot_size INTEGER
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts INTEGER NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS backtest_trades (
                id TEXT PRIMARY KEY,
                time INTEGER NOT NULL,
                ts INTEGER NOT NULL,
                side TEXT NOT NULL,
                qty INTEGER NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS app_state (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.commit()

        cur = conn.execute("SELECT COUNT(*) AS c FROM prices")
        if cur.fetchone()["c"] == 0:
            seed_prices(conn)

        if get_state(conn, "cash") is None:
            set_state(conn, "cash", 1_000_000)

        if get_state(conn, "last_tick") is None:
            set_state(conn, "last_tick", 0)

        if get_state(conn, "last_kite_sync") is None:
            set_state(conn, "last_kite_sync", 0)

        if get_state(conn, "last_instruments_sync") is None:
            set_state(conn, "last_instruments_sync", 0)

        if get_state(conn, "bt_symbol") is None:
            set_state(conn, "bt_symbol", "BACKTEST")
        if get_state(conn, "bt_index") is None:
            set_state(conn, "bt_index", 0)
        if get_state(conn, "bt_cash") is None:
            set_state(conn, "bt_cash", 1_000_000)
        if get_state(conn, "bt_pos_qty") is None:
            set_state(conn, "bt_pos_qty", 0)
        if get_state(conn, "bt_pos_avg") is None:
            set_state(conn, "bt_pos_avg", 0.0)


def seed_prices(conn: sqlite3.Connection) -> None:
    symbols = [
        ("RELIANCE", "NSE", 2875.5),
        ("TCS", "NSE", 3892.3),
        ("INFY", "NSE", 1625.15),
        ("HDFCBANK", "NSE", 1498.4),
        ("ICICIBANK", "NSE", 1102.25),
        ("SBIN", "NSE", 785.1),
        ("ITC", "BSE", 446.75),
        ("HINDUNILVR", "BSE", 2448.2),
        ("ONGC", "BSE", 262.8),
        ("TATASTEEL", "BSE", 154.6),
    ]
    for symbol, exchange, price in symbols:
        conn.execute(
            """
            INSERT INTO prices (symbol, exchange, price, prev_price, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (symbol, exchange, price, price, 0),
        )
    conn.commit()


def get_state(conn: sqlite3.Connection, key: str):
    cur = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,))
    row = cur.fetchone()
    if not row:
        return None
    try:
        return json.loads(row["value"])
    except json.JSONDecodeError:
        return row["value"]


def set_state(conn: sqlite3.Connection, key: str, value) -> None:
    payload = json.dumps(value)
    conn.execute(
        """
        INSERT INTO app_state (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
        (key, payload),
    )
    conn.commit()
