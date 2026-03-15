from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    api_key: str | None = os.getenv("KITE_API_KEY")
    api_secret: str | None = os.getenv("KITE_API_SECRET")
    redirect_url: str = os.getenv("KITE_REDIRECT_URL", "http://127.0.0.1:8000/callback")


settings = Settings()
