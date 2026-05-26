import json
import logging
from typing import Optional

import httpx

from src.core.config import Settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        s = settings or Settings()
        self.provider = s.llm_provider
        self.model = s.llm_model
        self.api_key = s.llm_api_key
        self.base_url = s.llm_base_url.rstrip("/")

    def generate(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """生成LLM响应，provider=mock 时返回固定响应，否则调用真实接口"""
        if self.provider == "mock" or not self.api_key:
            logger.debug("LLMClient: 使用 mock 模式")
            return json.dumps({
                "symbol": "600519.SH",
                "action": "BUY",
                "confidence": 75,
                "target_position_ratio": 0.1,
                "reason": "Mock decision",
            }, ensure_ascii=False)

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "response_format": {"type": "json_object"},
                    },
                )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info(f"LLMClient: 调用成功 model={self.model}")
            return content
        except Exception as e:
            logger.error(f"LLMClient: 调用失败 {e}，降级为 mock")
            return json.dumps({
                "symbol": "600519.SH",
                "action": "HOLD",
                "confidence": 0,
                "target_position_ratio": 0.0,
                "reason": f"LLM call failed: {e}",
            }, ensure_ascii=False)
