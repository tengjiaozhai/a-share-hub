import httpx


class BinanceAlphaPublicClient:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_tokenized_securities(self) -> dict:
        response = await self._http.get("/bapi/defi/v1/public/alpha-trade/tokenized-securities/list")
        response.raise_for_status()
        return response.json()
