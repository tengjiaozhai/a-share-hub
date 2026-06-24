# DeepSeek 混合模型 + 超时 + 重试 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 DeepSeek 调用从"单一模型 + 硬编码超时 + 无重试"改为"per-call 模型选择 + 可配置超时 + 指数退避重试"，解决分析报告链路中 `deepseek-v4-pro` 思维链导致 30 秒超时的问题。

**Architecture:** 在 `LLMClient.generate_json()` 和 `generate()` 增加 `model` 和 `timeout` 参数，Research 用 `deepseek-v4-pro`，Trader 用 `deepseek-v4-flash`。超时从 `Settings.llm_timeout` 读取，默认 300 秒。重试 3 次，指数退避（2s, 4s, 8s）。

**Tech Stack:** Python 3.11, httpx, pydantic-settings

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `src/core/config.py:48-51` | Modify | 新增 `llm_timeout` 和 `llm_model_research` / `llm_model_trader` 配置 |
| `src/agents/llm_client.py` | Modify | `generate_json()` / `generate()` / `_post_chat()` 增加 model/timeout/retry 参数 |
| `src/alpha/analysis_agents.py:116-117` | Modify | `ResearchManager` 和 `Trader` 使用不同模型 |
| `src/alpha/analysis_run_service.py:243-252` | Modify | 构造 `ResearchManager` / `Trader` 时传入不同模型 |
| `tests/test_llm_client_model_override.py` | Create | 测试 per-call 模型选择、超时、重试 |
| `tests/test_analysis_agents_model_selection.py` | Create | 测试 Research 用 pro、Trader 用 flash |

---

## Task 1: Settings 增加新配置项

**Files:**
- Modify: `src/core/config.py:48-51`
- Test: `tests/test_llm_client_model_override.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_llm_client_model_override.py
from src.core.config import Settings


def test_settings_has_llm_timeout():
    s = Settings(llm_timeout=300)
    assert s.llm_timeout == 300


def test_settings_default_llm_timeout():
    s = Settings()
    assert s.llm_timeout == 30


def test_settings_has_research_model():
    s = Settings(llm_model_research="deepseek-v4-pro")
    assert s.llm_model_research == "deepseek-v4-pro"


def test_settings_has_trader_model():
    s = Settings(llm_model_trader="deepseek-v4-flash")
    assert s.llm_model_trader == "deepseek-v4-flash"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_llm_client_model_override.py -v`
Expected: FAIL with `ValidationError: Field required`

- [ ] **Step 3: 修改 Settings**

```python
# src/core/config.py:48-51 改为：
llm_provider: str = "deepseek"
llm_api_key: str = ""
llm_model: str = "deepseek-v4-pro"
llm_model_research: str = "deepseek-v4-pro"
llm_model_trader: str = "deepseek-v4-flash"
llm_base_url: str = "https://api.deepseek.com"
llm_timeout: int = 300
```

- [ ] **Step 4: 运行测试确认通过**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_llm_client_model_override.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/core/config.py tests/test_llm_client_model_override.py
git commit -m "feat(config): add llm_timeout, llm_model_research, llm_model_trader"
```

---

## Task 2: LLMClient 支持 per-call model/timeout/retry

**Files:**
- Modify: `src/agents/llm_client.py`
- Test: `tests/test_llm_client_model_override.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_llm_client_model_override.py (追加)
import json
from unittest.mock import patch, MagicMock
from src.agents.llm_client import LLMClient


def test_generate_json_uses_per_call_model():
    """generate_json 的 model 参数应覆盖默认模型"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client.generate_json(
            system_prompt="test",
            user_prompt="test",
            model="deepseek-v4-flash",
        )

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][2]
        assert payload["model"] == "deepseek-v4-flash"


def test_generate_json_uses_default_model_when_none():
    """model=None 时使用 self.model"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client.generate_json(system_prompt="test", user_prompt="test")

        call_kwargs = mock_client.post.call_args
        payload = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][2]
        assert payload["model"] == "deepseek-v4-pro"


def test_generate_json_uses_configured_timeout():
    """超时应从 Settings.llm_timeout 读取"""
    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value = mock_client

        client.generate_json(system_prompt="test", user_prompt="test")

        call_kwargs = mock_client_cls.call_args
        assert call_kwargs[1]["timeout"] == 300.0


def test_generate_json_retries_on_timeout():
    """超时应重试 3 次"""
    import httpx

    client = LLMClient(Settings(
        llm_provider="deepseek",
        llm_api_key="test-key",
        llm_model="deepseek-v4-pro",
        llm_timeout=300,
    ))

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": '{"rating":"HOLD","confidence":0.5}'}}]
    }
    mock_response.raise_for_status = MagicMock()

    call_count = 0
    def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.TimeoutException("timeout")
        return mock_response

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = mock_post
        mock_client_cls.return_value = mock_client

        result = client.generate_json(system_prompt="test", user_prompt="test")

        assert call_count == 3
        assert result == {"rating": "HOLD", "confidence": 0.5}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_llm_client_model_override.py -v`
Expected: FAIL with `TypeError: generate_json() got an unexpected keyword argument 'model'`

- [ ] **Step 3: 修改 LLMClient**

```python
# src/agents/llm_client.py 完整替换

import json
import logging
import time
from typing import Optional

import httpx

from src.core.config import Settings

logger = logging.getLogger(__name__)


class LLMGenerationError(RuntimeError):
    pass


def _normalize_model_name(model_name: str) -> str:
    return model_name.strip().lower()


def _loads_json_object(content: str) -> dict:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        parsed = None
        for idx, char in enumerate(content):
            if char != "{":
                continue
            try:
                candidate, _ = decoder.raw_decode(content[idx:])
            except json.JSONDecodeError:
                continue
            parsed = candidate
            break
        if parsed is None:
            raise
    if not isinstance(parsed, dict):
        raise LLMGenerationError("DeepSeek JSON response must be an object")
    return parsed


class LLMClient:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        s = settings or Settings()
        self.provider = s.llm_provider
        self.model = _normalize_model_name(s.llm_model)
        self.model_research = _normalize_model_name(s.llm_model_research)
        self.model_trader = _normalize_model_name(s.llm_model_trader)
        self.api_key = s.llm_api_key
        self.base_url = s.llm_base_url.rstrip("/")
        self.timeout = float(s.llm_timeout)

    def _resolve_model(self, model: Optional[str] = None) -> str:
        if model:
            return _normalize_model_name(model)
        return self.model

    def _post_chat(self, payload: dict, timeout: Optional[float] = None) -> str:
        t = timeout or self.timeout
        for attempt in range(3):
            try:
                with httpx.Client(timeout=t) as client:
                    response = client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                response.raise_for_status()
                content = str(response.json()["choices"][0]["message"]["content"])
                logger.info(
                    "DeepSeek call OK model=%s attempt=%d content_len=%d",
                    payload.get("model"), attempt + 1, len(content),
                )
                return content
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                logger.warning(
                    "DeepSeek call failed model=%s attempt=%d: %s",
                    payload.get("model"), attempt + 1, exc,
                )
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        model: Optional[str] = None,
    ) -> Optional[str]:
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
            system_prompt = (
                "你是一个A股量化交易助手。请只输出合法json，不要输出多余解释。"
                "返回字段必须包含 symbol, action, confidence, target_position_ratio, reason。"
                "示例json: {\"symbol\":\"600519.SH\",\"action\":\"BUY\",\"confidence\":80,"
                "\"target_position_ratio\":0.1,\"reason\":\"示例理由\"}"
            )
            resolved = self._resolve_model(model)
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": resolved,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": 512,
                        "response_format": {"type": "json_object"},
                    },
                )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info("LLMClient: 调用成功 model=%s", resolved)
            return content
        except Exception as e:
            logger.error("LLMClient: 调用失败 %s，降级为 mock", e)
            return json.dumps({
                "symbol": "600519.SH",
                "action": "HOLD",
                "confidence": 0,
                "target_position_ratio": 0.0,
                "reason": f"LLM call failed: {e}",
            }, ensure_ascii=False)

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        model: Optional[str] = None,
    ) -> dict:
        if self.provider == "mock" or not self.api_key:
            raise LLMGenerationError("DeepSeek analysis requires LLM_API_KEY")
        resolved = self._resolve_model(model)
        payload = {
            "model": resolved,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        try:
            content = self._post_chat(payload)
            logger.info("DeepSeek raw content: %r", content[:2000])
            parsed = _loads_json_object(content)
        except json.JSONDecodeError as exc:
            raise LLMGenerationError("DeepSeek returned invalid JSON") from exc
        except (httpx.HTTPError, KeyError, TypeError) as exc:
            raise LLMGenerationError(f"DeepSeek request failed: {exc}") from exc
        return parsed
```

- [ ] **Step 4: 运行测试确认通过**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_llm_client_model_override.py -v`
Expected: PASS

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py tests/test_alpha_portfolio_service.py tests/test_alpha_runtime_store.py tests/test_dashboard_page_contract.py -q`
Expected: PASS (no regressions)

- [ ] **Step 6: 提交**

```bash
git add src/agents/llm_client.py tests/test_llm_client_model_override.py
git commit -m "feat(llm): add per-call model selection, configurable timeout, retry with backoff"
```

---

## Task 3: ResearchManager / Trader 使用不同模型

**Files:**
- Modify: `src/alpha/analysis_agents.py:116-117,143-144`
- Modify: `src/alpha/analysis_run_service.py:243-252`
- Test: `tests/test_analysis_agents_model_selection.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_analysis_agents_model_selection.py
from unittest.mock import MagicMock, patch
from src.alpha.analysis_agents import ResearchManager, Trader
from src.alpha.analysis_models import AnalysisSnapshot, ResearchPlan, TraderProposal


def _make_snapshot() -> AnalysisSnapshot:
    return AnalysisSnapshot(
        symbol="MU.US",
        market="us",
        currency="USD",
        as_of="2026-06-22",
        quantity=0.022,
        weighted_avg_cost=1006.68,
        close=1133.99,
        market_value=24.95,
        unrealized_pnl=2.79,
        unrealized_pnl_ratio=0.126,
        position_ratio=0.01,
        stop_loss_ratio=-0.08,
        take_profit_ratio=0.20,
        technical={"ma20": 1100, "ma60": 1050},
        fundamentals={"status": "ok", "pe_ratio": 15.2},
        news={},
        data_quality={},
    )


def test_research_manager_uses_model_research():
    """ResearchManager 应使用 model_research 参数"""
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "rating": "HOLD",
        "thesis": "test",
        "technical_view": "test",
        "fundamental_view": "test",
        "sentiment_view": "test",
        "catalysts": [],
        "risks": ["test"],
        "confidence": 0.5,
        "data_gaps": [],
    }

    rm = ResearchManager(mock_llm, model="deepseek-v4-pro")
    rm.analyze(_make_snapshot())

    call_kwargs = mock_llm.generate_json.call_args[1]
    assert call_kwargs["model"] == "deepseek-v4-pro"


def test_trader_uses_model_trader():
    """Trader 应使用 model_trader 参数"""
    mock_llm = MagicMock()
    mock_llm.generate_json.return_value = {
        "action": "HOLD",
        "reasoning": "test",
        "entry_low": 1100,
        "entry_high": 1200,
        "stop_loss": 1000,
        "take_profit": 1300,
        "position_ratio": 0.0,
    }

    research = ResearchPlan(
        rating="HOLD",
        thesis="test",
        technical_view="test",
        fundamental_view="test",
        sentiment_view="test",
        catalysts=[],
        risks=["test"],
        confidence=0.5,
        data_gaps=[],
    )

    t = Trader(mock_llm, model="deepseek-v4-flash")
    t.propose(_make_snapshot(), research)

    call_kwargs = mock_llm.generate_json.call_args[1]
    assert call_kwargs["model"] == "deepseek-v4-flash"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_analysis_agents_model_selection.py -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'model'`

- [ ] **Step 3: 修改 ResearchManager 和 Trader**

```python
# src/alpha/analysis_agents.py 修改两处：

# ResearchManager.__init__ 改为：
class ResearchManager:
    SYSTEM_PROMPT = (
        "你是持仓研究经理。只能使用输入 JSON 中的证据。"
        "输出 BUY/OVERWEIGHT/HOLD/UNDERWEIGHT/SELL 五档评级。"
        "数据缺失必须写入 data_gaps 并降低 confidence，不得补写未提供的新闻或财务事实。"
        "只输出合法 json，不要输出 markdown，不要输出解释。"
        "输出格式必须是："
        '{"rating":"HOLD","thesis":"证据不足，暂时观察",'
        '"technical_view":"趋势证据中性","fundamental_view":"基本面数据有限",'
        '"sentiment_view":"新闻数据不可用","catalysts":[],"risks":["数据缺失"],'
        '"confidence":0.4,"data_gaps":["news"]}'
    )

    def __init__(self, llm, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    def analyze(self, snapshot: AnalysisSnapshot) -> ResearchPlan:
        try:
            payload = self._llm.generate_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=snapshot.model_dump_json(),
                temperature=0.2,
                max_tokens=1400,
                model=self._model,
            )
            return ResearchPlan.model_validate(_normalize_research_payload(payload, snapshot))
        except (LLMGenerationError, ValidationError) as exc:
            return _research_fallback(snapshot, str(exc))


# Trader.__init__ 改为：
class Trader:
    SYSTEM_PROMPT = (
        "你是交易员。不要重新研究公司，只把研究计划和当前持仓转换为 BUY/HOLD/SELL。"
        "给出入场区间、止损、止盈和建议仓位。已有持仓时 BUY 表示建议加仓。"
        "只输出合法 json，不要输出 markdown，不要输出解释。"
        "输出格式必须是："
        '{"action":"HOLD","reasoning":"等待价格确认，暂不加仓",'
        '"entry_low":12.3,"entry_high":12.8,"stop_loss":11.5,'
        '"take_profit":15.0,"position_ratio":0.0}'
    )

    def __init__(self, llm, model: str | None = None) -> None:
        self._llm = llm
        self._model = model

    def propose(self, snapshot: AnalysisSnapshot, research: ResearchPlan) -> TraderProposal:
        context = {"snapshot": snapshot.model_dump(), "research": research.model_dump()}
        try:
            payload = self._llm.generate_json(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=json.dumps(context, ensure_ascii=False, sort_keys=True),
                temperature=0.1,
                max_tokens=1500,
                model=self._model,
            )
            return TraderProposal.model_validate(_normalize_trader_payload(payload, snapshot))
        except (LLMGenerationError, ValidationError) as exc:
            return _trader_fallback(snapshot, str(exc))
```

- [ ] **Step 4: 运行测试确认通过**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_analysis_agents_model_selection.py -v`
Expected: PASS

- [ ] **Step 5: 修改 analysis_run_service.py 传入模型**

```python
# src/alpha/analysis_run_service.py 找到构造 ResearchManager 和 Trader 的位置
# 大约在 _build_run_service 函数中（routes_alpha.py:179-252）
# 修改为：

    research_manager = ResearchManager(llm, model=settings.llm_model_research)
    trader = Trader(llm, model=settings.llm_model_trader)
```

具体位置：`src/api/routes_alpha.py:243-252` 附近，找到 `ResearchManager(llm)` 和 `Trader(llm)` 改为带 model 参数。

- [ ] **Step 6: 运行全量测试确认无回归**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py tests/test_alpha_portfolio_service.py tests/test_analysis_agents_model_selection.py tests/test_llm_client_model_override.py -q`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add src/alpha/analysis_agents.py src/api/routes_alpha.py tests/test_analysis_agents_model_selection.py
git commit -m "feat(alpha): use deepseek-v4-pro for research, deepseek-v4-flash for trader"
```

---

## Task 4: 验证端到端

**Files:**
- No file changes

- [ ] **Step 1: 本地运行全量测试**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py tests/test_alpha_portfolio_service.py tests/test_alpha_runtime_store.py tests/test_alpha_portfolio_report_service.py tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py tests/test_llm_client_model_override.py tests/test_analysis_agents_model_selection.py -q`
Expected: All PASS

- [ ] **Step 2: 提交 + 推送 + 部署**

```bash
git push origin master
ssh -i ~/.ssh/xingxing.pem ec2-user@13.214.201.113 "cd /home/ec2-user/a-share-hub && git pull && pkill -f uvicorn; sleep 2; cd /home/ec2-user/a-share-hub && nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 & sleep 3 && curl -s http://localhost:8000/health"
```

- [ ] **Step 3: 浏览器验收**

用 browser-use 登录 `http://13.214.201.113:8000/dashboard`（tengjiaozhai / Lcx20001201），进入持仓分析，点击"生成分析"，确认：
1. Research 阶段使用 `deepseek-v4-pro`
2. Trader 阶段使用 `deepseek-v4-flash`
3. 不再出现 "LLM 输出不可用"
4. 分析报告正常生成

---

## Success Criteria

| 标准 | 验证方法 |
|------|---------|
| Research 使用 deepseek-v4-pro | 日志显示 `model=deepseek-v4-pro` |
| Trader 使用 deepseek-v4-flash | 日志显示 `model=deepseek-v4-flash` |
| 超时从 30s 改为 300s | 代码检查 `self.timeout = float(s.llm_timeout)` |
| 超时重试 3 次 | 测试 `test_generate_json_retries_on_timeout` 通过 |
| 不再出现 "LLM 输出不可用" | 浏览器验收 |
| 现有测试无回归 | 全量测试 PASS |
| 配置可调 | `.env` 中 `LLM_MODEL_RESEARCH` / `LLM_MODEL_TRADER` / `LLM_TIMEOUT` 生效 |

---

## 风险与约束

1. **deepseek-v4-flash 准确率**：如果 Trader 分类准确率不够，回退到方案 B（统一用 pro + 5 分钟超时）
2. **成本**：pro 比 flash 贵，但只用 1 次（research），trader 用 flash 省钱
3. **向后兼容**：`model=None` 时使用 `self.model`，现有调用方不受影响
4. **不改动 `generate()` 方法的模型选择**：只改 `generate_json()`，因为 `generate()` 只用于 dashboard 决策，不涉及分析报告链路
