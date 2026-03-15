from __future__ import annotations

import time
from typing import Dict, List

from kiteconnect import KiteConnect

from .config import settings
from .db import get_conn, get_state, set_state
from .kite_client import get_access_token, kite_ready


def sync_instruments(exchanges: List[str]) -> Dict:
    if not kite_ready():
        return {"error": "Kite not connected."}
    token = get_access_token()
    kite = KiteConnect(api_key=settings.api_key)
    kite.set_access_token(token)

    rows = []
    for ex in exchanges:
        try:
            rows.extend(kite.instruments(ex))
        except Exception as exc:
            return {"error": f"Failed to fetch instruments for {ex}: {exc}"}

    with get_conn() as conn:
        conn.execute("DELETE FROM instruments")
        conn.executemany(
            """
            INSERT INTO instruments
            (instrument_token, tradingsymbol, name, exchange, segment, instrument_type,
             expiry, strike, tick_size, lot_size)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    r.get("instrument_token"),
                    r.get("tradingsymbol"),
                    r.get("name"),
                    r.get("exchange"),
                    r.get("segment"),
                    r.get("instrument_type"),
                    _to_date_str(r.get("expiry")),
                    r.get("strike"),
                    r.get("tick_size"),
                    r.get("lot_size"),
                )
                for r in rows
            ],
        )
        set_state(conn, "last_instruments_sync", int(time.time()))
        conn.commit()
    return {"count": len(rows)}


def list_instruments(
    q: str | None,
    exchanges: List[str],
    segments: List[str],
    limit: int,
    offset: int,
) -> Dict:
    with get_conn() as conn:
        clauses = []
        params: List = []
        if q:
            clauses.append("(tradingsymbol LIKE ? OR name LIKE ?)")
            like = f"%{q}%"
            params.extend([like, like])
        if exchanges:
            placeholders = ",".join(["?"] * len(exchanges))
            clauses.append(f"exchange IN ({placeholders})")
            params.extend(exchanges)
        if segments:
            placeholders = ",".join(["?"] * len(segments))
            clauses.append(f"segment IN ({placeholders})")
            params.extend(segments)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = conn.execute(
            f"SELECT COUNT(*) AS c FROM instruments {where}", params
        ).fetchone()["c"]
        rows = conn.execute(
            f"""
            SELECT instrument_token, tradingsymbol, name, exchange, segment,
                   instrument_type, expiry, strike, tick_size, lot_size
            FROM instruments
            {where}
            ORDER BY exchange, tradingsymbol
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()
        last_sync = get_state(conn, "last_instruments_sync") or 0
        return {
            "total": total,
            "last_sync": last_sync,
            "data": [dict(r) for r in rows],
        }


def get_instrument_token(tradingsymbol: str, exchange: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT instrument_token
            FROM instruments
            WHERE tradingsymbol = ? AND exchange = ?
            """,
            (tradingsymbol, exchange),
        ).fetchone()
        return row["instrument_token"] if row else None


def _to_date_str(value) -> str | None:
    if value is None:
        return None
    return str(value)
