# Alpha Desk Phase 3 Research And Ops UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已有 alpha 数据、建议单和账本基础上，加入研究扫描、候选排序、自动生成建议单，以及更完整的操作台交互。

**Architecture:** 研究自动化只使用 alpha 边界内的 `signal_engine` 和 `watchlist_store`，不复用 A 股 scanner 语义。dashboard 扩展为真正的 alpha 操作台：能管理观察列表、触发扫描、查看候选、从候选直接生成建议单，并按状态筛选工单。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pandas, pytest

---

## 前置条件

- `docs/superpowers/plans/2026-06-01-alpha-desk-phase2-ledger-and-reconciliation.md` 已完成并合入。
- alpha 组合快照、对账结果和 dashboard alpha 面板已经存在。

---

## 文件结构

```
a-share-hub/
├── src/
│   ├── alpha/
│   │   ├── signal_engine.py
│   │   ├── research_service.py
│   │   └── watchlist_service.py
│   ├── api/
│   │   ├── routes_alpha.py
│   │   ├── routes_dashboard.py
│   │   └── dashboard.html
│   └── storage/
│       ├── models.py
│       └── runtime_store.py
└── tests/
    ├── test_alpha_signal_engine.py
    ├── test_alpha_research_service.py
    ├── test_alpha_runtime_store.py
    ├── test_alpha_routes.py
    ├── test_dashboard_alpha_tab.py
    └── test_dashboard_api.py
```

---

### Task 1: 建立 alpha 候选评分与排序引擎

**Files:**
- Create: `src/alpha/signal_engine.py`
- Test: `tests/test_alpha_signal_engine.py`

- [ ] **Step 1: 写失败测试，锁定 alpha 候选评分合同**

```python
import pandas as pd

from src.alpha.signal_engine import AlphaSignalEngine


def test_signal_engine_scores_bullish_asset_as_buy():
    candles = pd.DataFrame(
        [
            {"close": 100.0, "high": 101.0, "low": 99.0, "volume": 1000},
            {"close": 102.0, "high": 103.0, "low": 101.0, "volume": 1100},
            {"close": 104.0, "high": 105.0, "low": 103.0, "volume": 1150},
            {"close": 106.0, "high": 107.0, "low": 105.0, "volume": 1200},
            {"close": 109.0, "high": 110.0, "low": 108.0, "volume": 1300},
        ]
    )
    engine = AlphaSignalEngine(buy_threshold=0.55, sell_threshold=-0.55)

    signal = engine.score_asset(symbol="AAPLx", candles=candles)

    assert signal.symbol == "AAPLx"
    assert signal.action == "BUY"
    assert signal.score >= 0.55
```

- [ ] **Step 2: 运行测试，确认当前缺少 alpha 信号引擎**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_signal_engine.py::test_signal_engine_scores_bullish_asset_as_buy -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'src.alpha.signal_engine'
```

- [ ] **Step 3: 写最小实现，基于趋势和动量输出 BUY/HOLD/SELL**

```python
# src/alpha/signal_engine.py
from dataclasses import dataclass


@dataclass(frozen=True)
class AlphaSignal:
    symbol: str
    score: float
    action: str
    reason: str


class AlphaSignalEngine:
    def __init__(self, buy_threshold: float, sell_threshold: float) -> None:
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def score_asset(self, symbol: str, candles) -> AlphaSignal:
        closes = candles["close"].astype(float)
        fast_ma = closes.tail(3).mean()
        slow_ma = closes.mean()
        trend = (fast_ma - slow_ma) / slow_ma if slow_ma else 0.0
        momentum = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0] if closes.iloc[0] else 0.0
        score = round(0.6 * trend + 0.4 * momentum, 4)
        if score >= self._buy_threshold:
            action = "BUY"
        elif score <= self._sell_threshold:
            action = "SELL"
        else:
            action = "HOLD"
        return AlphaSignal(symbol=symbol, score=score, action=action, reason=f"trend={trend:.4f}, momentum={momentum:.4f}")
```

- [ ] **Step 4: 运行测试，确认候选评分稳定**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_signal_engine.py::test_signal_engine_scores_bullish_asset_as_buy -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha/signal_engine.py tests/test_alpha_signal_engine.py
git commit -m "feat: add alpha signal engine"
```

---

### Task 2: 建立 alpha 观察列表存储

**Files:**
- Modify: `src/storage/models.py`
- Modify: `src/storage/runtime_store.py`
- Test: `tests/test_alpha_runtime_store.py`

- [ ] **Step 1: 写失败测试，锁定观察列表增删查合同**

```python
from sqlalchemy import create_engine

from src.storage.models import Base
from src.storage.runtime_store import RuntimeStore


def test_runtime_store_manages_alpha_watchlist_items(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/runtime.db", future=True)
    Base.metadata.create_all(engine)
    store = RuntimeStore(engine)

    store.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    store.add_alpha_watchlist_item(symbol="SPYx", underlying_symbol="SPY", priority=2)

    items = store.list_alpha_watchlist_items()

    assert [item["symbol"] for item in items] == ["AAPLx", "SPYx"]

    store.remove_alpha_watchlist_item(symbol="SPYx")
    assert [item["symbol"] for item in store.list_alpha_watchlist_items()] == ["AAPLx"]
```

- [ ] **Step 2: 运行测试，确认观察列表存储尚未实现**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_manages_alpha_watchlist_items -q
```

Expected:

```text
E   AttributeError: 'RuntimeStore' object has no attribute 'add_alpha_watchlist_item'
```

- [ ] **Step 3: 写最小实现，新增观察列表表与 store 方法**

```python
# src/storage/models.py
class AlphaWatchlistItemRow(Base):
    __tablename__ = "alpha_watchlist_items"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    underlying_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
```

```python
# src/storage/runtime_store.py
def add_alpha_watchlist_item(self, symbol: str, underlying_symbol: str, priority: int) -> None:
    with self.engine.begin() as conn:
        conn.execute(
            AlphaWatchlistItemRow.__table__.insert().values(
                symbol=symbol,
                underlying_symbol=underlying_symbol,
                priority=priority,
            )
        )


def remove_alpha_watchlist_item(self, symbol: str) -> None:
    with self.engine.begin() as conn:
        conn.execute(
            AlphaWatchlistItemRow.__table__.delete().where(AlphaWatchlistItemRow.symbol == symbol)
        )


def list_alpha_watchlist_items(self) -> list[dict]:
    with self.engine.begin() as conn:
        rows = conn.execute(
            select(AlphaWatchlistItemRow).order_by(AlphaWatchlistItemRow.priority, AlphaWatchlistItemRow.symbol)
        ).fetchall()
        return [
            {
                "symbol": row.symbol,
                "underlying_symbol": row.underlying_symbol,
                "priority": row.priority,
                "created_at": _cst_iso(row.created_at),
            }
            for row in rows
        ]
```

- [ ] **Step 4: 运行测试，确认观察列表存储可用**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_runtime_store.py::test_runtime_store_manages_alpha_watchlist_items -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/storage/models.py src/storage/runtime_store.py tests/test_alpha_runtime_store.py
git commit -m "feat: add alpha watchlist persistence"
```

---

### Task 3: 建立研究扫描 service 与 API

**Files:**
- Create: `src/alpha/research_service.py`
- Create: `src/alpha/watchlist_service.py`
- Modify: `src/api/routes_alpha.py`
- Test: `tests/test_alpha_research_service.py`
- Test: `tests/test_alpha_routes.py`

- [ ] **Step 1: 写失败测试，锁定 watchlist -> ranked candidates -> proposed ticket 的合同**

```python
import pandas as pd
import pytest

from src.alpha.research_service import AlphaResearchService
from src.alpha.signal_engine import AlphaSignalEngine


class FakeHistoryClient:
    async def get_klines(self, symbol: str, interval: str, limit: int) -> list[dict]:
        closes = {
            "AAPLx": [100, 102, 104, 106, 109],
            "SPYx": [500, 499, 498, 497, 496],
        }[symbol]
        return [{"close": close, "high": close + 1, "low": close - 1, "volume": 1000} for close in closes]


@pytest.mark.asyncio
async def test_research_service_ranks_candidates_and_proposes_ticket():
    service = AlphaResearchService(FakeHistoryClient(), AlphaSignalEngine(buy_threshold=0.02, sell_threshold=-0.02))

    ranked = await service.rank_watchlist(["AAPLx", "SPYx"])
    ticket = service.build_ticket_from_signal(ranked[0], thesis_prefix="phase3 auto")

    assert ranked[0]["symbol"] == "AAPLx"
    assert ranked[0]["action"] == "BUY"
    assert ticket["asset_symbol"] == "AAPLx"
    assert ticket["action"] == "BUY"
```

- [ ] **Step 2: 运行测试，确认当前缺少研究扫描 service**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_research_service.py::test_research_service_ranks_candidates_and_proposes_ticket -q
```

Expected:

```text
E   ModuleNotFoundError: No module named 'src.alpha.research_service'
```

- [ ] **Step 3: 写最小实现，提供排名扫描和 ticket proposal 构造器**

```python
# src/alpha/research_service.py
import pandas as pd


class AlphaResearchService:
    def __init__(self, history_client, signal_engine) -> None:
        self._history_client = history_client
        self._signal_engine = signal_engine

    async def rank_watchlist(self, symbols: list[str]) -> list[dict]:
        ranked = []
        for symbol in symbols:
            candles = await self._history_client.get_klines(symbol=symbol, interval="1h", limit=30)
            frame = pd.DataFrame(candles)
            signal = self._signal_engine.score_asset(symbol=symbol, candles=frame)
            ranked.append(
                {"symbol": signal.symbol, "score": signal.score, "action": signal.action, "reason": signal.reason}
            )
        return sorted(ranked, key=lambda item: item["score"], reverse=True)

    def build_ticket_from_signal(self, signal: dict, thesis_prefix: str) -> dict:
        return {
            "asset_symbol": signal["symbol"],
            "underlying_symbol": signal["symbol"].removesuffix("x"),
            "action": signal["action"],
            "thesis": f"{thesis_prefix}: {signal['reason']}",
            "suggested_quantity": 1.0,
            "suggested_limit_price": 0.0,
        }


# src/alpha/watchlist_service.py
class AlphaWatchlistService:
    def __init__(self, store) -> None:
        self._store = store

    def list_symbols(self) -> list[str]:
        return [item["symbol"] for item in self._store.list_alpha_watchlist_items()]
```

```python
# src/api/routes_alpha.py
@router.get("/watchlist")
def list_alpha_watchlist(store=Depends(get_runtime_store)) -> dict:
    return {"items": store.list_alpha_watchlist_items()}


@router.post("/watchlist")
def add_alpha_watchlist(payload: dict, store=Depends(get_runtime_store)) -> dict:
    store.add_alpha_watchlist_item(**payload)
    return {"stored": True, "symbol": payload["symbol"]}


@router.post("/research/scan")
async def scan_alpha_watchlist(store=Depends(get_runtime_store)) -> dict:
    service = _get_alpha_research_service()
    symbols = [item["symbol"] for item in store.list_alpha_watchlist_items()]
    return {"items": await service.rank_watchlist(symbols)}
```

- [ ] **Step 4: 运行测试，确认研究扫描可以产出排序结果**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_research_service.py::test_research_service_ranks_candidates_and_proposes_ticket -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/alpha/research_service.py src/alpha/watchlist_service.py src/api/routes_alpha.py tests/test_alpha_research_service.py tests/test_alpha_routes.py
git commit -m "feat: add alpha research scan and watchlist api"
```

---

### Task 4: 从研究候选直接生成建议单，并扩展 dashboard 操作区

**Files:**
- Modify: `src/api/routes_alpha.py`
- Modify: `src/api/routes_dashboard.py`
- Modify: `src/api/dashboard.html`
- Test: `tests/test_alpha_routes.py`
- Test: `tests/test_dashboard_api.py`
- Test: `tests/test_dashboard_alpha_tab.py`

- [ ] **Step 1: 写失败测试，锁定 auto-propose ticket 和 dashboard 候选区合同**

```python
from fastapi.testclient import TestClient
from pathlib import Path


def test_alpha_research_candidate_can_be_promoted_to_ticket(test_app, pg_store, monkeypatch):
    from src.api import routes_alpha

    class FakeResearchService:
        async def rank_watchlist(self, symbols):
            return [{"symbol": "AAPLx", "action": "BUY", "score": 0.8, "reason": "trend strong"}]

        def build_ticket_from_signal(self, signal, thesis_prefix):
            return {
                "asset_symbol": "AAPLx",
                "underlying_symbol": "AAPL",
                "action": "BUY",
                "thesis": f"{thesis_prefix}: trend strong",
                "suggested_quantity": 1.0,
                "suggested_limit_price": 0.0,
            }

    monkeypatch.setattr(routes_alpha, "_get_alpha_research_service", lambda: FakeResearchService())
    pg_store.add_alpha_watchlist_item(symbol="AAPLx", underlying_symbol="AAPL", priority=1)
    client = TestClient(test_app)

    response = client.post("/api/v1/alpha/research/propose-top-ticket", json={"thesis_prefix": "auto"})

    assert response.status_code == 200
    assert response.json()["asset_symbol"] == "AAPLx"
    assert response.json()["ticket_id"].startswith("alpha-ticket-")


def test_dashboard_contains_alpha_research_controls():
    content = Path("src/api/dashboard.html").read_text(encoding="utf-8")
    assert "观察列表与候选" in content
    assert "runAlphaScan" in content
    assert "proposeTopAlphaTicket" in content
```

- [ ] **Step 2: 运行测试，确认当前还没有自动生成建议单的入口**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_research_candidate_can_be_promoted_to_ticket tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_research_controls -q
```

Expected:

```text
2 failed
```

- [ ] **Step 3: 写最小实现，新增 candidate -> ticket API 并把 research 摘要加入 workbench**

```python
# src/api/routes_alpha.py
@router.post("/research/propose-top-ticket")
async def propose_top_alpha_ticket(payload: dict, store=Depends(get_runtime_store)) -> dict:
    service = _get_alpha_research_service()
    symbols = [item["symbol"] for item in store.list_alpha_watchlist_items()]
    ranked = await service.rank_watchlist(symbols)
    top = ranked[0]
    ticket_payload = service.build_ticket_from_signal(top, thesis_prefix=payload["thesis_prefix"])
    ticket_payload["expires_at"] = payload.get("expires_at", "2026-06-01T16:00:00+08:00")
    ticket_id = store.insert_alpha_ticket(**ticket_payload)
    return {"ticket_id": ticket_id, **ticket_payload}
```

```python
# src/api/routes_dashboard.py
def _build_alpha_panel_payload(store) -> dict:
    tickets = store.list_alpha_tickets()
    latest_ticket_id = tickets[0]["ticket_id"] if tickets else None
    latest_snapshot = store.get_latest_alpha_portfolio_snapshot()
    recon_runs = store.list_alpha_reconciliation_runs()
    latest_recon = recon_runs[0] if recon_runs else None
    return {
        "tickets": tickets,
        "fills": store.list_alpha_manual_fills(ticket_id=latest_ticket_id) if latest_ticket_id else [],
        "portfolio": {
            "positions": store.list_alpha_positions(),
            "snapshot": latest_snapshot,
        },
        "exceptions": {
            "latest_status": latest_recon["status"] if latest_recon else "UNKNOWN",
            "latest_discrepancies": latest_recon["discrepancies"] if latest_recon else {},
        },
        "research": {
            "watchlist": store.list_alpha_watchlist_items(),
            "latest_candidates": [],
        },
    }
```

```html
<!-- src/api/dashboard.html -->
<div class="risk-card">
  <div class="risk-label">观察列表与候选</div>
  <button onclick="runAlphaScan()">运行扫描</button>
  <button onclick="proposeTopAlphaTicket()">生成建议单</button>
  <div id="alpha-watchlist"></div>
  <div id="alpha-candidates"></div>
</div>
<script>
async function runAlphaScan() {
  const res = await fetch('/api/v1/alpha/research/scan', { method: 'POST' });
  const body = await res.json();
  document.getElementById('alpha-candidates').innerHTML = body.items
    .map((item) => `<div>${item.symbol} ${item.action} ${item.score}</div>`)
    .join('');
}

async function proposeTopAlphaTicket() {
  const res = await fetch('/api/v1/alpha/research/propose-top-ticket', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thesis_prefix: 'dashboard auto' }),
  });
  const body = await res.json();
  document.getElementById('alpha-tickets').innerHTML = `<div>${body.asset_symbol} ${body.action}</div>`;
}
</script>
```

- [ ] **Step 4: 运行测试，确认 dashboard 已支持 scan 和 auto-propose**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_routes.py::test_alpha_research_candidate_can_be_promoted_to_ticket tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_research_controls -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add src/api/routes_alpha.py src/api/routes_dashboard.py src/api/dashboard.html tests/test_alpha_routes.py tests/test_dashboard_api.py tests/test_dashboard_alpha_tab.py
git commit -m "feat: promote alpha research candidates into tickets"
```

---

### Task 5: 为 alpha 操作台补状态筛选、研究说明和回归验证

**Files:**
- Create: `docs/runbooks/alpha-research-and-ops-ui.md`
- Modify: `README.md`
- Test: `tests/test_alpha_signal_engine.py`
- Test: `tests/test_alpha_research_service.py`
- Test: `tests/test_alpha_runtime_store.py`
- Test: `tests/test_alpha_routes.py`
- Test: `tests/test_dashboard_api.py`

- [ ] **Step 1: 写运行说明，明确扫描、排序和候选转建议单流程**

```markdown
# Alpha Research And Ops UI Runbook

1. 维护观察列表。
2. 通过 `/api/v1/alpha/research/scan` 生成候选。
3. 检查候选分数和原因。
4. 通过 `/api/v1/alpha/research/propose-top-ticket` 将候选转成建议单。
5. 回到 Phase 1 的 ticket/fill 流程继续执行。
```

- [ ] **Step 2: 运行 Phase 3 核心测试**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_signal_engine.py::test_signal_engine_scores_bullish_asset_as_buy tests/test_alpha_runtime_store.py::test_runtime_store_manages_alpha_watchlist_items tests/test_alpha_research_service.py::test_research_service_ranks_candidates_and_proposes_ticket tests/test_alpha_routes.py::test_alpha_research_candidate_can_be_promoted_to_ticket tests/test_dashboard_alpha_tab.py::test_dashboard_contains_alpha_research_controls -q
```

Expected:

```text
5 passed
```

- [ ] **Step 3: 启动服务并检查 alpha research 路由**

Run:

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve
```

Expected:

```text
Uvicorn running on http://0.0.0.0:8000
```

- [ ] **Step 4: 用 curl 验证 watchlist、scan 和 auto-propose**

Run:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/watchlist -H 'Content-Type: application/json' -d '{"symbol":"AAPLx","underlying_symbol":"AAPL","priority":1}' | head -c 300
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/research/scan | head -c 300
curl -s -X POST http://127.0.0.1:8000/api/v1/alpha/research/propose-top-ticket -H 'Content-Type: application/json' -d '{"thesis_prefix":"dashboard auto"}' | head -c 300
```

Expected:

```text
watchlist stored response
scan returns ranked items
propose-top-ticket returns ticket_id
```

- [ ] **Step 5: 提交**

```bash
cd /Users/shenmingjie/workSpace/tranding/a-share-hub
git add README.md docs/runbooks src tests
git commit -m "docs: add alpha research workflow runbook"
```
