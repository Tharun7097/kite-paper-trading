from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .backtest import get_state_snapshot, list_trades as bt_list_trades, load_csv, reset as bt_reset, step as bt_step, trade as bt_trade
from .db import init_db
from .instruments import list_instruments, sync_instruments
from .kite_history import fetch_candles
from .kite_client import exchange_request_token, kite_configured, kite_ready, login_url
from .trading import (
    get_cash,
    list_market,
    list_orders,
    list_positions,
    list_trades,
    place_order,
    reset_all,
    simulate_tick,
)

app = FastAPI(title="Kite Paper Trading (Local)")

init_db()

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("app/static/index.html")


@app.get("/api/market")
def api_market(q: str | None = None):
    return {"data": list_market(q)}


@app.post("/api/tick")
def api_tick():
    return {"data": simulate_tick()}


@app.get("/api/orders")
def api_orders():
    return {"data": list_orders()}


@app.post("/api/orders")
async def api_place_order(request: Request):
    payload = await request.json()
    result = place_order(payload)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/orders/{order_id}/cancel")
def api_cancel(order_id: str):
    from .trading import cancel_order

    result = cancel_order(order_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/positions")
def api_positions():
    return {"data": list_positions()}


@app.get("/api/trades")
def api_trades():
    return {"data": list_trades()}


@app.get("/api/state")
def api_state():
    return {"cash": get_cash()}


@app.post("/api/reset")
def api_reset():
    reset_all()
    return {"ok": True}


@app.get("/api/kite/status")
def kite_status():
    return {
        "configured": kite_configured(),
        "connected": kite_ready(),
    }


@app.get("/api/kite/login-url")
def kite_login():
    if not kite_configured():
        raise HTTPException(status_code=400, detail="Kite API key/secret not configured.")
    return {"login_url": login_url()}


@app.post("/api/kite/exchange-token")
async def kite_exchange(request: Request):
    if not kite_configured():
        raise HTTPException(status_code=400, detail="Kite API key/secret not configured.")
    payload = await request.json()
    token = payload.get("request_token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing request_token.")
    data = exchange_request_token(token)
    return {"ok": True, "data": data}


@app.post("/api/kite/instruments/sync")
async def kite_sync_instruments(request: Request):
    if not kite_ready():
        raise HTTPException(status_code=400, detail="Kite not connected.")
    payload = await request.json()
    exchanges = payload.get("exchanges") or ["NSE", "BSE", "NFO"]
    result = sync_instruments(exchanges)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/instruments")
def api_instruments(
    q: str | None = None,
    exchange: str | None = None,
    segment: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    exchanges = [e.strip() for e in exchange.split(",")] if exchange else []
    segments = [s.strip() for s in segment.split(",")] if segment else []
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    return list_instruments(q, exchanges, segments, limit, offset)


@app.get("/api/kite/candles")
def api_kite_candles(
    symbol: str,
    exchange: str,
    interval: str = "day",
    days: int = 180,
):
    days = max(1, min(days, 365))
    result = fetch_candles(symbol, exchange, interval, days)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/backtest/state")
def api_backtest_state():
    return get_state_snapshot()


@app.post("/api/backtest/load")
async def api_backtest_load(request: Request):
    payload = await request.json()
    symbol = payload.get("symbol") or "BACKTEST"
    csv_text = payload.get("csv_text") or ""
    result = load_csv(symbol, csv_text)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/backtest/step")
async def api_backtest_step(request: Request):
    payload = await request.json()
    delta = int(payload.get("delta") or 0)
    index = payload.get("index")
    index_val = int(index) if index is not None else None
    return bt_step(delta=delta, index=index_val)


@app.post("/api/backtest/trade")
async def api_backtest_trade(request: Request):
    payload = await request.json()
    side = payload.get("side") or ""
    qty = int(payload.get("qty") or 0)
    result = bt_trade(side, qty)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/backtest/reset")
def api_backtest_reset():
    bt_reset()
    return {"ok": True}


@app.get("/api/backtest/trades")
def api_backtest_trades():
    return {"data": bt_list_trades(200)}


@app.get("/callback")
def kite_callback(request: Request):
    token = request.query_params.get("request_token")
    if not token:
        return JSONResponse({"error": "Missing request_token"}, status_code=400)
    return JSONResponse({"request_token": token})
