from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from kiteconnect import KiteConnect

from .config import settings
from .instruments import get_instrument_token
from .kite_client import get_access_token, kite_ready


def fetch_candles(
    tradingsymbol: str,
    exchange: str,
    interval: str,
    days: int,
) -> Dict:
    if not kite_ready():
        return {"error": "Kite not connected."}
    token = get_access_token()
    if not token:
        return {"error": "Missing access token."}
    instrument_token = get_instrument_token(tradingsymbol, exchange)
    if not instrument_token:
        return {"error": "Instrument not found. Sync instruments first."}

    to_dt = datetime.now()
    from_dt = to_dt - timedelta(days=days)
    kite = KiteConnect(api_key=settings.api_key)
    kite.set_access_token(token)
    try:
        data = kite.historical_data(
            instrument_token,
            from_dt,
            to_dt,
            interval,
            continuous=False,
            oi=False,
        )
    except Exception as exc:
        return {"error": f"Failed to fetch candles: {exc}"}

    candles: List[Dict] = []
    for row in data:
        candles.append(
            {
                "ts": int(row["date"].timestamp()),
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row.get("volume"),
            }
        )
    return {"data": candles}
