from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .db import get_conn, get_state, set_state


def load_csv(symbol: str, csv_text: str) -> Dict:
    rows = _parse_csv(csv_text)
    if not rows:
        return {"error": "No valid rows found. Expected: date,price per line."}
    with get_conn() as conn:
        conn.execute("DELETE FROM backtest_prices")
        conn.execute("DELETE FROM backtest_trades")
        conn.executemany(
            "INSERT INTO backtest_prices (ts, price) VALUES (?, ?)",
            rows,
        )
        set_state(conn, "bt_symbol", symbol or "BACKTEST")
        set_state(conn, "bt_index", 0)
        set_state(conn, "bt_cash", 1_000_000)
        set_state(conn, "bt_pos_qty", 0)
        set_state(conn, "bt_pos_avg", 0.0)
        conn.commit()
    return {"count": len(rows)}


def reset() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM backtest_prices")
        conn.execute("DELETE FROM backtest_trades")
        set_state(conn, "bt_symbol", "BACKTEST")
        set_state(conn, "bt_index", 0)
        set_state(conn, "bt_cash", 1_000_000)
        set_state(conn, "bt_pos_qty", 0)
        set_state(conn, "bt_pos_avg", 0.0)
        conn.commit()


def get_state_snapshot() -> Dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM backtest_prices").fetchone()["c"]
        index = int(get_state(conn, "bt_index") or 0)
        index = max(0, min(index, max(total - 1, 0))) if total else 0
        symbol = get_state(conn, "bt_symbol") or "BACKTEST"
        cash = float(get_state(conn, "bt_cash") or 0)
        pos_qty = int(get_state(conn, "bt_pos_qty") or 0)
        pos_avg = float(get_state(conn, "bt_pos_avg") or 0)
        current = _get_bar(conn, index) if total else None
        return {
            "symbol": symbol,
            "cash": cash,
            "pos_qty": pos_qty,
            "pos_avg": pos_avg,
            "index": index,
            "total": total,
            "current": current,
        }


def step(delta: int = 0, index: Optional[int] = None) -> Dict:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM backtest_prices").fetchone()["c"]
        if total == 0:
            return get_state_snapshot()
        cur = int(get_state(conn, "bt_index") or 0)
        if index is not None:
            cur = index
        else:
            cur += delta
        cur = max(0, min(cur, total - 1))
        set_state(conn, "bt_index", cur)
        conn.commit()
    return get_state_snapshot()


def trade(side: str, qty: int) -> Dict:
    side = side.upper()
    if side not in ("BUY", "SELL"):
        return {"error": "Side must be BUY or SELL."}
    if qty <= 0:
        return {"error": "Quantity must be > 0."}
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM backtest_prices").fetchone()["c"]
        if total == 0:
            return {"error": "No backtest data loaded."}
        index = int(get_state(conn, "bt_index") or 0)
        bar = _get_bar(conn, index)
        if not bar:
            return {"error": "Invalid backtest index."}
        price = float(bar["price"])
        cash = float(get_state(conn, "bt_cash") or 0)
        pos_qty = int(get_state(conn, "bt_pos_qty") or 0)
        pos_avg = float(get_state(conn, "bt_pos_avg") or 0)

        if side == "BUY":
            cost = price * qty
            if cash < cost:
                return {"error": "Insufficient backtest cash."}
            new_qty = pos_qty + qty
            new_avg = ((pos_avg * pos_qty) + (price * qty)) / new_qty
            cash -= cost
            pos_qty = new_qty
            pos_avg = round(new_avg, 2)
        else:
            if pos_qty < qty:
                return {"error": "Insufficient position to sell."}
            pos_qty -= qty
            cash += price * qty
            if pos_qty == 0:
                pos_avg = 0.0

        conn.execute(
            """
            INSERT INTO backtest_trades (id, time, ts, side, qty, price)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), int(time.time()), bar["ts"], side, qty, price),
        )
        set_state(conn, "bt_cash", round(cash, 2))
        set_state(conn, "bt_pos_qty", pos_qty)
        set_state(conn, "bt_pos_avg", pos_avg)
        conn.commit()
    return get_state_snapshot()


def list_trades(limit: int = 200) -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT ts, side, qty, price
            FROM backtest_trades
            ORDER BY time DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def _get_bar(conn, index: int) -> Optional[Dict]:
    row = conn.execute(
        "SELECT ts, price FROM backtest_prices ORDER BY ts ASC LIMIT 1 OFFSET ?",
        (index,),
    ).fetchone()
    return dict(row) if row else None


def _parse_csv(text: str) -> List[Tuple[int, float]]:
    rows: List[Tuple[int, float]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        ts = _parse_date(parts[0].strip())
        try:
            price = float(parts[1].strip())
        except ValueError:
            continue
        if ts is None:
            continue
        rows.append((ts, price))
    rows.sort(key=lambda r: r[0])
    return rows


def _parse_date(raw: str) -> Optional[int]:
    try:
        num = float(raw)
        if num > 10_000_000_000:
            return int(num / 1000)
        return int(num)
    except ValueError:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except ValueError:
        return None
