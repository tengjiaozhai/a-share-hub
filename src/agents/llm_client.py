from typing import Optional

class LLMClient:
    def __init__(self, provider: str = "mock", model: str = "mock") -> None:
        self.provider = provider
        self.model = model

    def generate(self, prompt: str, temperature: float = 0.7) -> Optional[str]:
        """生成LLM响应（mock模式返回固定响应）"""
        if self.provider == "mock":
            return '{"symbol": "600519.SH", "action": "BUY", "confidence": 75, "target_position_ratio": 0.1, "reason": "Mock decision"}'
        return None
