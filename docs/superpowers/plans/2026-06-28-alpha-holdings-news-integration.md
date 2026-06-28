# Alpha 持仓分析新闻数据接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 akshare `stock_news_em` 接入 `AnalysisSnapshotBuilder`，消除持仓分析中的 news 缺口，提升 LLM 研究结论质量。

**Architecture:** 在 `AnalysisSnapshotBuilder` 增加 `news_loader` 回调（与现有 `history_loader`/`fundamental_loader` 模式一致），在 `routes_alpha.py` 构造该回调时调用 `akshare.stock_news_em`。失败时降级为 unavailable，不阻断快照构建。

**Tech Stack:** Python 3.11, akshare, Pydantic 2, pytest

---

## Task 1: 接入 news_loader 到 AnalysisSnapshotBuilder

**Files:**
- Modify: `src/alpha/analysis_snapshot.py`
- Test: `tests/test_alpha_analysis_snapshot.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_alpha_analysis_snapshot.py 末尾追加
def test_snapshot_passes_news_from_loader():
    bars = [{"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000} for i in range(61)]
    news_data = {
        "status": "ok",
        "count": 2,
        "items": [
            {"title": "利好消息", "summary": "公司业绩超预期", "source": "财经网", "published_at": "2026-06-26"},
            {"title": "行业分析", "summary": "行业前景看好", "source": "证券时报", "published_at": "2026-06-25"},
        ],
    }
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=lambda symbol: news_data,
    )
    snapshot = builder.build(symbol="600703.SH", lots=[{"buy_price": 12.0, "quantity": 100}], portfolio_market_value=10000.0)
    assert snapshot.news["status"] == "ok"
    assert len(snapshot.news["items"]) == 2
    assert "news" not in snapshot.data_quality.get("missing", [])


def test_snapshot_gracefully_handles_news_loader_failure():
    bars = [{"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000} for i in range(61)]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=lambda symbol: (_ for _ in ()).throw(RuntimeError("network error")),
    )
    snapshot = builder.build(symbol="600703.SH", lots=[{"buy_price": 12.0, "quantity": 100}], portfolio_market_value=10000.0)
    assert snapshot.news["status"] == "error"
    assert "news" in snapshot.data_quality.get("missing", [])


def test_snapshot_works_without_news_loader():
    """不传 news_loader 时行为与改造前一致"""
    bars = [{"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000} for i in range(61)]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
    )
    snapshot = builder.build(symbol="600703.SH", lots=[{"buy_price": 12.0, "quantity": 100}], portfolio_market_value=10000.0)
    assert snapshot.news == {"status": "unavailable", "items": []}
    assert "news" in snapshot.data_quality.get("missing", [])
```

- [ ] **Step 2: 运行测试确认失败**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_snapshot.py -q
```

Expected: 新测试 FAIL（`__init__` 不接受 `news_loader` 参数）

- [ ] **Step 3: 修改 AnalysisSnapshotBuilder**

`src/alpha/analysis_snapshot.py`:
- `__init__` 新增 `news_loader: Callable[[str], dict[str, Any]] | None = None`
- `build()` 中替换硬编码的 news 逻辑

- [ ] **Step 4: 运行测试确认通过**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_snapshot.py -q
```

- [ ] **Step 5: 提交**

```bash
git add src/alpha/analysis_snapshot.py tests/test_alpha_analysis_snapshot.py
git commit -m "feat(alpha): add news_loader to AnalysisSnapshotBuilder"
```

---

## Task 2: 在 routes_alpha.py 构造 news_loader

**Files:**
- Modify: `src/api/routes_alpha.py`
- Test: 手动验证

- [ ] **Step 1: 添加 news_loader 函数**

在 `_build_run_service` 中构造 `news_loader`，调用 `akshare.stock_news_em`。

- [ ] **Step 2: 传入 AnalysisSnapshotBuilder**

```python
snapshot_builder = AnalysisSnapshotBuilder(
    history_loader=history_loader,
    fundamental_loader=fundamental_loader,
    news_loader=news_loader,  # 新增
)
```

- [ ] **Step 3: 运行现有测试确认不破坏**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_service.py tests/test_alpha_analysis_snapshot.py -q
```

- [ ] **Step 4: 提交**

```bash
git add src/api/routes_alpha.py
git commit -m "feat(alpha): wire akshare news_loader into analysis pipeline"
```

---

## Task 3: 更新 ResearchManager prompt 适配真实新闻

**Files:**
- Modify: `src/alpha/analysis_agents.py`
- Test: `tests/test_alpha_analysis_agents.py`

- [ ] **Step 1: 写失败测试**

验证当 `snapshot.news.items` 非空时，ResearchManager 不再在 `data_gaps` 中包含 "news"。

- [ ] **Step 2: 更新 prompt**

移除 `SYSTEM_PROMPT` 中"新闻数据不可用"的默认假设，改为"基于提供的新闻列表分析舆情"。

- [ ] **Step 3: 运行测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_agents.py -q
```

- [ ] **Step 4: 提交**

```bash
git add src/alpha/analysis_agents.py tests/test_alpha_analysis_agents.py
git commit -m "feat(alpha): update research prompt for real news data"
```

---

## Task 4: Dashboard 抽屉展示新闻证据

**Files:**
- Modify: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `src/api/dashboard_page/partials/view_alpha.html`
- Test: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: 在 drawer 中添加 news section**

在 `view_alpha.html` 的 drawer body 中，在 research section 之前添加 news section。

- [ ] **Step 2: 在 alpha.js 中渲染新闻**

在 `openAlphaAnalysisDrawer` 中添加 news 渲染逻辑。

- [ ] **Step 3: 运行测试**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_dashboard_page_contract.py tests/test_dashboard_alpha_tab.py -q
```

- [ ] **Step 4: 提交**

```bash
git add src/api/dashboard_page/scripts/alpha.js src/api/dashboard_page/partials/view_alpha.html
git commit -m "feat(alpha): display news evidence in analysis drawer"
```
