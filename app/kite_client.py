from __future__ import annotations

from typing import Optional

from kiteconnect import KiteConnect

from .config import settings
from .db import get_conn, get_state, set_state


def _kite() -> KiteConnect:
    kite = KiteConnect(api_key=settings.api_key)
    token = get_access_token()
    if token:
        kite.set_access_token(token)
    return kite


def kite_ready() -> bool:
    return bool(settings.api_key and settings.api_secret and get_access_token())


def kite_configured() -> bool:
    return bool(settings.api_key and settings.api_secret)


def login_url() -> str:
    kite = _kite()
    return kite.login_url()


def exchange_request_token(request_token: str) -> dict:
    kite = _kite()
    data = kite.generate_session(request_token, api_secret=settings.api_secret)
    access_token = data.get("access_token")
    if access_token:
        _set_access_token(access_token)
    return data


def get_access_token() -> Optional[str]:
    with get_conn() as conn:
        return get_state(conn, "kite_access_token")


def _set_access_token(token: str) -> None:
    with get_conn() as conn:
        set_state(conn, "kite_access_token", token)
