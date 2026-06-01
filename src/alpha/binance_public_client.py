from typing import Any, cast

import httpx


class BinanceAlphaPublicClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_tokenized_securities(self) -> dict[str, Any]:
        response = await self._http.get("/bapi/defi/v1/public/alpha-trade/tokenized-securities/list")
        response.raise_for_status()
        return cast(dict[str, Any], response.json())
