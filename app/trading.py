from __future__ import annotations

import time
import uuid
from typing import Dict, List

from .db import get_conn, get_state, set_state
from .kite_client import kite_ready, get_access_token
from .config import settings
from kiteconnect import KiteConnect

DELAY_MINUTES = 15
TICK_INTERVAL_SECONDS = 5
KITE_SYNC_SECONDS = 2


def list_market(filter_text: str | None = None) -> List[Dict]:
    if kite_ready():
        _maybe_kite_sync()
    else:
        _maybe_tick()
    with get_conn() as conn:
        query = "SELECT * FROM prices"
        params = ()
        if filter_text:
            query += " WHERE symbol LIKE ?"
            params = (f"%{filter_text}%",)
        query += " ORDER BY symbol"
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def simulate_tick() -> List[Dict]:
    return _tick_prices(force=True)


def place_order(order: Dict) -> Dict:
    symbol = order["symbol"]
    exchange = order["exchange"]
    side = order["side"]
    qty = int(order["qty"])
    order_type = order["type"]
    limit_price = order.get("limit_price")

    if order_type == "LIMIT" and not limit_price:
        return {"error": "Limit orders require limit_price."}

    with get_conn() as conn:
        market = _get_market(conn, symbol, exchange)
        if not market and kite_ready():
            market = _ensure_price(conn, symbol, exchange)
        if not market:
            return {"error": "Unknown symbol/exchange."}

        if side == "SELL" and not _has_position(conn, symbol, exchange, qty):
            return {"error": "Insufficient position to sell."}

        if order_type == "MARKET":
            price = market["price"]
            if side == "BUY" and not _has_cash(conn, price * qty):
                return {"error": "Insufficient cash."}
            order_id = _create_order(conn, order, "FILLED", price)
            _apply_trade(conn, order, price)
            return {"id": order_id, "status": "FILLED"}

        if side == "BUY" and not _has_cash(conn, limit_price * qty):
            return {"error": "Insufficient cash for limit order."}

        order_id = _create_order(conn, order, "OPEN", None)
        _fill_open_orders(conn)
        return {"id": order_id, "status": "OPEN"}


def list_orders() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY time DESC LIMIT 200"
        ).fetchall()
        return [dict(row) for row in rows]


def cancel_order(order_id: str) -> Dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        if not row:
            return {"error": "Order not found."}
        if row["status"] != "OPEN":
            return {"error": "Only OPEN orders can be cancelled."}
        conn.execute(
            "UPDATE orders SET status = 'CANCELLED' WHERE id = ?", (order_id,)
        )
        conn.commit()
        return {"id": order_id, "status": "CANCELLED"}


def list_positions() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM positions WHERE qty != 0 ORDER BY symbol"
        ).fetchall()
        return [dict(row) for row in rows]


def list_trades() -> List[Dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY time DESC LIMIT 200"
        ).fetchall()
        return [dict(row) for row in rows]


def get_cash() -> float:
    with get_conn() as conn:
        return float(get_state(conn, "cash") or 0)


def reset_all() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM trades")
        conn.execute("DELETE FROM positions")
        conn.execute(
            "UPDATE prices SET price = prev_price, updated_at = 0"
        )
        set_state(conn, "cash", 1_000_000)
        set_state(conn, "last_tick", 0)
        set_state(conn, "last_kite_sync", 0)
        conn.commit()


def _get_market(conn, symbol: str, exchange: str):
    row = conn.execute(
        "SELECT * FROM prices WHERE symbol = ? AND exchange = ?",
        (symbol, exchange),
    ).fetchone()
    return dict(row) if row else None


def _ensure_price(conn, symbol: str, exchange: str):
    token = get_access_token()
    if not token:
        return None
    kite = KiteConnect(api_key=settings.api_key)
    kite.set_access_token(token)
    key = f"{exchange}:{symbol}"
    try:
        ltp = kite.ltp([key])
    except Exception:
        return None
    if key not in ltp or ltp[key].get("last_price") is None:
        return None
    price = round(float(ltp[key]["last_price"]), 2)
    now = int(time.time())
    conn.execute(
        """
        INSERT INTO prices (symbol, exchange, price, prev_price, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(symbol, exchange) DO UPDATE SET
          prev_price = excluded.prev_price,
          price = excluded.price,
          updated_at = excluded.updated_at
        """,
        (symbol, exchange, price, price, now),
    )
    conn.commit()
    return _get_market(conn, symbol, exchange)


def _has_position(conn, symbol: str, exchange: str, qty: int) -> bool:
    row = conn.execute(
        "SELECT qty FROM positions WHERE symbol = ? AND exchange = ?",
        (symbol, exchange),
    ).fetchone()
    return row is not None and row["qty"] >= qty


def _has_cash(conn, amount: float) -> bool:
    cash = float(get_state(conn, "cash") or 0)
    return cash >= amount


def _create_order(conn, order: Dict, status: str, filled_price: float | None):
    order_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO orders
        (id, time, symbol, exchange, side, qty, type, limit_price, status, filled_price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_id,
            int(time.time()),
            order["symbol"],
            order["exchange"],
            order["side"],
            int(order["qty"]),
            order["type"],
            order.get("limit_price"),
            status,
            filled_price,
        ),
    )
    conn.commit()
    return order_id


def _apply_trade(conn, order: Dict, price: float) -> None:
    qty = int(order["qty"])
    symbol = order["symbol"]
    exchange = order["exchange"]
    side = order["side"]
    cost = price * qty

    cash = float(get_state(conn, "cash") or 0)

    row = conn.execute(
        "SELECT qty, avg_price FROM positions WHERE symbol = ? AND exchange = ?",
        (symbol, exchange),
    ).fetchone()
    pos_qty = row["qty"] if row else 0
    pos_avg = row["avg_price"] if row else 0.0

    if side == "BUY":
        new_qty = pos_qty + qty
        new_avg = ((pos_avg * pos_qty) + (price * qty)) / new_qty
        cash -= cost
    else:
        new_qty = pos_qty - qty
        new_avg = pos_avg if new_qty != 0 else 0.0
        cash += cost

    conn.execute(
        """
        INSERT INTO trades (id, time, symbol, exchange, side, qty, price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (str(uuid.uuid4()), int(time.time()), symbol, exchange, side, qty, price),
    )
    conn.execute(
        """
        INSERT INTO positions (symbol, exchange, qty, avg_price)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(symbol, exchange) DO UPDATE SET
          qty = excluded.qty,
          avg_price = excluded.avg_price
        """,
        (symbol, exchange, new_qty, round(new_avg, 2)),
    )
    set_state(conn, "cash", round(cash, 2))


def _fill_open_orders(conn) -> None:
    orders = conn.execute(
        "SELECT * FROM orders WHERE status = 'OPEN' ORDER BY time ASC"
    ).fetchall()
    for row in orders:
        order = dict(row)
        market = _get_market(conn, order["symbol"], order["exchange"])
        if not market:
            continue
        price = market["price"]
        can_fill = (
            order["type"] == "MARKET"
            or (order["side"] == "BUY" and price <= order["limit_price"])
            or (order["side"] == "SELL" and price >= order["limit_price"])
        )
        if not can_fill:
            continue
        if order["side"] == "BUY" and not _has_cash(conn, price * order["qty"]):
            conn.execute(
                "UPDATE orders SET status = 'REJECTED' WHERE id = ?",
                (order["id"],),
            )
            continue
        if order["side"] == "SELL" and not _has_position(
            conn, order["symbol"], order["exchange"], order["qty"]
        ):
            conn.execute(
                "UPDATE orders SET status = 'REJECTED' WHERE id = ?",
                (order["id"],),
            )
            continue
        _apply_trade(conn, order, price)
        conn.execute(
            "UPDATE orders SET status = 'FILLED', filled_price = ? WHERE id = ?",
            (price, order["id"]),
        )
    conn.commit()


def _tick_prices(force: bool) -> List[Dict]:
    now = int(time.time())
    with get_conn() as conn:
        last_tick = int(get_state(conn, "last_tick") or 0)
        if not force and (now - last_tick) < TICK_INTERVAL_SECONDS:
            rows = conn.execute("SELECT * FROM prices").fetchall()
            return [dict(row) for row in rows]
        rows = conn.execute("SELECT * FROM prices").fetchall()
        for row in rows:
            price = row["price"]
            drift = (time.time() % 1 - 0.5) * (price * 0.003)
            next_price = max(1.0, price + drift)
            conn.execute(
                """
                UPDATE prices
                SET prev_price = ?, price = ?, updated_at = ?
                WHERE symbol = ? AND exchange = ?
                """,
                (
                    price,
                    round(next_price, 2),
                    now - DELAY_MINUTES * 60,
                    row["symbol"],
                    row["exchange"],
                ),
            )
        set_state(conn, "last_tick", now)
        conn.commit()
        _fill_open_orders(conn)
        rows = conn.execute("SELECT * FROM prices").fetchall()
        return [dict(row) for row in rows]


def _maybe_tick() -> None:
    _tick_prices(force=False)


def _maybe_kite_sync() -> None:
    now = int(time.time())
    with get_conn() as conn:
        last_sync = int(get_state(conn, "last_kite_sync") or 0)
        if (now - last_sync) < KITE_SYNC_SECONDS:
            return
        token = get_access_token()
        if not token:
            return
        kite = KiteConnect(api_key=settings.api_key)
        kite.set_access_token(token)
        rows = conn.execute("SELECT symbol, exchange, price FROM prices").fetchall()
        instruments = [f"{row['exchange']}:{row['symbol']}" for row in rows]
        if not instruments:
            return
        try:
            ltp = kite.ltp(instruments)
        except Exception:
            return
        for row in rows:
            key = f"{row['exchange']}:{row['symbol']}"
            if key not in ltp:
                continue
            last_price = ltp[key].get("last_price")
            if last_price is None:
                continue
            conn.execute(
                """
                UPDATE prices
                SET prev_price = price, price = ?, updated_at = ?
                WHERE symbol = ? AND exchange = ?
                """,
                (round(float(last_price), 2), now, row["symbol"], row["exchange"]),
            )
        set_state(conn, "last_kite_sync", now)
        conn.commit()
