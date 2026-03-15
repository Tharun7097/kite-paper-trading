# Kite Paper Trading (Local)

Local-only paper trading app with delayed simulated prices. It is structured so a real broker
integration (Kite Connect) can be added later.

## Quick Start

1. Create a virtual environment:
   `C:\Users\tharu\AppData\Local\Programs\Python\Python314\python.exe -m venv .venv`
2. Activate:
   `.venv\Scripts\Activate.ps1`
3. Install dependencies:
   `python -m pip install -r requirements.txt`
4. Run:
   `python -m uvicorn app.main:app --reload --port 8000`

Open `http://127.0.0.1:8000/`.

## Kite Connect Setup (Later)

- Redirect URL: `http://127.0.0.1:8000/callback`
- Postback URL: leave blank for now unless you host a public HTTPS webhook.

Copy `.env.example` to `.env` and fill in your Kite credentials when ready.

## Live Data (Kite LTP)

1. Copy `.env.example` to `.env` and set `KITE_API_KEY` and `KITE_API_SECRET`.
2. Run the app and open `http://127.0.0.1:8000/`.
3. Click "Get Login URL", sign in, and paste the `request_token` from the callback URL.
4. Live LTP will be used for the Market table once connected.

## Full Instruments (NSE/BSE/NFO)

1. Connect Kite.
2. Click "Sync Instruments" in the UI. This downloads the full instrument list into local SQLite.
3. Use the Instrument Search panel to query NSE/BSE/NFO (showing up to 200 at a time).

## Backtest Tab

Use the Backtest tab to load a CSV (date,price) and step through time.
Backtest data, trades, and positions are stored in SQLite.
