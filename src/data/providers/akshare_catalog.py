from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

import pandas as pd


def infer_exchange(code: str) -> str:
    if code.startswith(("600", "601", "603", "605", "688", "689", "900")):
        return "SH"
    if code.startswith(("000", "001", "002", "003", "200", "300", "301", "302")):
        return "SZ"
    if code.startswith(("430", "440", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "874", "875", "876", "877", "878", "879", "920")):
        return "BJ"
    raise ValueError(f"unsupported stock code: {code}")


def normalize_symbol(symbol: str) -> str:
    text = symbol.strip().upper().replace("-", ".")
    if "." in text:
        code, exchange = text.split(".", 1)
        return f"{code}.{exchange}"
    if text.startswith(("SH", "SZ", "BJ")) and text[2:].isdigit():
        return f"{text[2:]}.{text[:2]}"
    return f"{text}.{infer_exchange(text)}"


def _safe_infer_exchange(code: str) -> str | None:
    try:
        return infer_exchange(code)
    except ValueError:
        return None


def normalize_stock_list_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.rename(columns={"code": "code", "name": "name"})[["code", "name"]].copy()
    normalized["code"] = normalized["code"].astype(str).str.zfill(6)
    normalized["exchange"] = normalized["code"].map(_safe_infer_exchange)
    normalized = normalized[normalized["exchange"].notna()].copy()
    normalized["symbol"] = normalized["code"] + "." + normalized["exchange"]
    return normalized[["symbol", "code", "name", "exchange"]]


@dataclass
class StockCatalogCache:
    ttl_seconds: int = 86400
    _frame: pd.DataFrame | None = field(default=None, init=False)
    _expires_at: datetime | None = field(default=None, init=False)

    def load(self, fetcher: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        now = datetime.utcnow()
        if self._frame is not None and self._expires_at is not None and now < self._expires_at:
            return self._frame
        frame = normalize_stock_list_frame(fetcher())
        self._frame = frame
        self._expires_at = now + timedelta(seconds=self.ttl_seconds)
        return frame

    def search(self, query: str = "", exchange: str = "all", limit: int = 50) -> list[dict]:
        frame = self._frame if self._frame is not None else pd.DataFrame(columns=["symbol", "code", "name", "exchange"])
        query_text = query.strip()
        exchange_text = exchange.strip().upper()
        if exchange_text and exchange_text != "ALL":
            frame = frame[frame["exchange"] == exchange_text]
        if query_text:
            frame = frame[
                frame["symbol"].str.contains(query_text, case=False, na=False)
                | frame["code"].str.contains(query_text, case=False, na=False)
                | frame["name"].str.contains(query_text, case=False, na=False)
            ]
        return frame.head(limit).to_dict("records")
