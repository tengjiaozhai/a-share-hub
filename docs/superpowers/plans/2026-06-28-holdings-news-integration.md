# Holdings Analysis News Data Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 akshare `stock_news_em` 接入 Alpha 持仓分析流式管线，使 ResearchManager 能基于真实新闻数据生成 sentiment_view 和 confidence。

**Architecture:** 在 `AnalysisSnapshotBuilder` 新增 `news_loader` 回调（与现有 `history_loader`/`fundamental_loader` 模式一致），在 `routes_alpha.py` 中用 `akshare.stock_news_em` 构造该回调。前端在分析抽屉的 research section 下方展示新闻列表。

**Tech Stack:** Python 3.11, akshare, FastAPI, Pydantic 2, vanilla JS, pytest

---

## Task 1: 接入 news_loader 到 AnalysisSnapshotBuilder

**Files:**
- Modify: `src/alpha/analysis_snapshot.py`
- Test: `tests/test_alpha_analysis_snapshot.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_alpha_analysis_snapshot.py 末尾追加

def test_snapshot_uses_news_loader_when_provided():
    bars = [{"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000} for i in range(61)]
    news_data = {
        "status": "ok",
        "items": [
            {"title": "利好消息", "summary": "公司业绩超预期", "source": "东方财富", "published_at": "2026-06-26"},
            {"title": "行业分析", "summary": "行业景气度提升", "source": "证券时报", "published_at": "2026-06-25"},
        ],
    }
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=lambda symbol: news_data,
    )
    snapshot = builder.build(symbol="600519", lots=[{"buy_price": 12.0, "quantity": 100}], portfolio_market_value=10000.0)
    assert snapshot.news["status"] == "ok"
    assert len(snapshot.news["items"]) == 2
    assert snapshot.news["items"][0]["title"] == "利好消息"
    assert "news" not in snapshot.data_quality["missing"]


def test_snapshot_gracefully_handles_news_loader_failure():
    bars = [{"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000} for i in range(61)]

    def failing_loader(symbol):
        raise RuntimeError("network error")

    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
        news_loader=failing_loader,
    )
    snapshot = builder.build(symbol="600519", lots=[{"buy_price": 12.0, "quantity": 100}], portfolio_market_value=10000.0)
    assert snapshot.news["status"] == "error"
    assert snapshot.news["items"] == []
    assert "news" in snapshot.data_quality["missing"]


def test_snapshot_without_news_loader_behaves_as_before():
    bars = [{"date": f"2026-03-{i+1:02d}", "close": 10.0 + i * 0.1, "volume": 1000} for i in range(61)]
    builder = AnalysisSnapshotBuilder(
        history_loader=lambda symbol: bars,
        fundamental_loader=lambda symbol: {"status": "ok"},
    )
    snapshot = builder.build(symbol="600519", lots=[{"buy_price": 12.0, "quantity": 100}], portfolio_market_value=10000.0)
    assert snapshot.news == {"status": "unavailable", "items": []}
    assert "news" in snapshot.data_quality["missing"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_snapshot.py -q`
Expected: FAIL（`__init__` 不接受 `news_loader` 参数）

- [ ] **Step 3: 修改 AnalysisSnapshotBuilder**

```python
# src/alpha/analysis_snapshot.py

class AnalysisSnapshotBuilder:
    def __init__(
        self,
        history_loader: Callable[[str], list[dict[str, Any]]],
        fundamental_loader: Callable[[str], dict[str, Any]],
        news_loader: Callable[[str], dict[str, Any]] | None = None,  # 新增
    ) -> None:
        self._history_loader = history_loader
        self._fundamental_loader = fundamental_loader
        self._news_loader = news_loader  # 新增

    def build(self, *, symbol, lots, portfolio_market_value) -> AnalysisSnapshot:
        # ... 现有 history/fundamental 逻辑不变 ...

        # 替换原来的:
        #   missing.append("news")
        #   news={"status": "unavailable", "items": []}
        # 改为:
        if self._news_loader:
            try:
                news = self._news_loader(symbol)
            except Exception:
                news = {"status": "error", "items": []}
        else:
            news = {"status": "unavailable", "items": []}

        if news.get("status") != "ok" or not news.get("items"):
            missing.append("news")

        return AnalysisSnapshot(
            # ... 其他字段不变 ...
            news=news,  # 替换硬编码
            # ...
        )
```

- [ ] **Step 4: 运行测试确认通过**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_snapshot.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/alpha/analysis_snapshot.py tests/test_alpha_analysis_snapshot.py
git commit -m "feat(alpha): add news_loader to AnalysisSnapshotBuilder"
```

---

## Task 2: 构造 akshare news_loader 并接入路由

**Files:**
- Modify: `src/api/routes_alpha.py`

- [ ] **Step 1: 在 `_build_run_service` 中添加 news_loader**

```python
def _build_run_service(store, user_id, holdings_store, tenant):
    # ... 现有 history_loader / fundamental_loader 不变 ...

    def news_loader(symbol: str) -> dict:
        import akshare as ak
        # 去掉 .US 后缀（akshare 用纯代码如 AAPL、600519）
        raw = symbol.replace(".US", "") if symbol.upper().endswith(".US") else symbol
        df = ak.stock_news_em(symbol=raw)
        items = []
        for _, row in df.head(10).iterrows():
            items.append({
                "title": str(row.get("新闻标题", "")),
                "summary": str(row.get("新闻内容", ""))[:200],
                "source": str(row.get("文章来源", "")),
                "published_at": str(row.get("发布时间", "")),
                "url": str(row.get("新闻链接", "")),
            })
        return {"status": "ok", "items": items}

    snapshot_builder = AnalysisSnapshotBuilder(
        history_loader=history_loader,
        fundamental_loader=fundamental_loader,
        news_loader=news_loader,  # 新增
    )
```

- [ ] **Step 2: 运行现有测试确认不破坏**

Run: `/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_alpha_analysis_run_service.py tests/test_alpha_analysis_snapshot.py -q`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add src/api/routes_alpha.py
git commit -m "feat(alpha): wire akshare news_loader into analysis pipeline"
```

---

## Task 3: 前端展示新闻数据

**Files:**
- Modify: `src/api/dashboard_page/scripts/alpha.js`
- Modify: `src/api/dashboard_page/styles/alpha.css`
- Test: `tests/test_dashboard_page_contract.py`

- [ ] **Step 1: 添加新闻渲染函数**

在 `alpha.js` 中 `renderAnalysisObject` 附近添加：

```javascript
function renderNewsItems(news) {
  if (!news || !news.items || !news.items.length) {
    return '<div class="alpha-empty-state">暂无新闻数据</div>';
  }
  return '<div class="alpha-news-list">' +
    news.items.map(item => `
      <div class="alpha-news-item">
        <div class="alpha-news-head">
          <span class="alpha-news-source">${escapeHtml(item.source || '--')}</span>
          <span class="alpha-news-time">${escapeHtml(item.published_at || '--')}</span>
        </div>
        <a class="alpha-news-title" href="${escapeHtml(item.url || '#')}" target="_blank" rel="noopener">${escapeHtml(item.title || '--')}</a>
        <div class="alpha-news-summary">${escapeHtml(item.summary || '')}</div>
      </div>
    `).join('') +
    '</div>';
}
```

- [ ] **Step 2: 在 openAlphaAnalysisDrawer 中渲染新闻**

在 `setDrawerSection('research', ...)` 之后添加：

```javascript
setDrawerSection('news', renderNewsItems(detail.snapshot?.news));
```

- [ ] **Step 3: 在 view_alpha.html 添加 news section**

在 research section 之后添加：

```html
<section class="alpha-analysis-drawer-section" data-section="news">
  <h4>📰 新闻舆情</h4>
  <div class="alpha-analysis-drawer-content"></div>
</section>
```

- [ ] **Step 4: 添加新闻样式**

```css
/* alpha.css */
.alpha-news-list { display: flex; flex-direction: column; gap: 12px; }
.alpha-news-item { padding: 10px; border: 1px solid var(--stroke); border-radius: 8px; background: rgba(255,255,255,.02); }
.alpha-news-head { display: flex; justify-content: space-between; font-size: 11px; color: var(--dim); margin-bottom: 4px; }
.alpha-news-title { font-size: 13px; font-weight: 600; color: var(--accent); text-decoration: none; }
.alpha-news-title:hover { text-decoration: underline; }
.alpha-news-summary { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.5; }
```

- [ ] **Step 5: 更新 contract 测试**

```python
# tests/test_dashboard_page_contract.py 追加
def test_dashboard_contains_news_section(_patch_auth):
    html = _dashboard_html()
    assert 'data-section="news"' in html
    assert "新闻舆情" in html
```

- [ ] **Step 6: 提交**

```bash
git add src/api/dashboard_page/scripts/alpha.js src/api/dashboard_page/styles/alpha.css src/api/dashboard_page/partials/view_alpha.html tests/test_dashboard_page_contract.py
git commit -m "feat(alpha): display news evidence in analysis drawer"
```

---

## Task 4: 端到端验证

- [ ] **Step 1: 启动服务**

```bash
/opt/anaconda3/envs/py311/bin/python3 -m src.main serve &
```

- [ ] **Step 2: 通过 API 触发分析并验证 news 字段**

```bash
# 触发 MU.US 分析
curl -sS -b /tmp/ashub-jar -X POST http://127.0.0.1:8000/api/v1/alpha/analysis-runs \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"MU.US","backtest_window":"60d","include_backtest":true}' | python3 -m json.tool

# 等待完成后查看 snapshot.news
curl -sS -b /tmp/ashub-jar http://127.0.0.1:8000/api/v1/alpha/analysis-runs/<run_id> | python3 -c "
import sys, json
data = json.load(sys.stdin)
news = data.get('snapshot', {}).get('news', {})
print(f'news status: {news.get(\"status\")}')
print(f'news count: {len(news.get(\"items\", []))}')
if news.get('items'):
    print(f'first title: {news[\"items\"][0].get(\"title\")}')
"
```

- [ ] **Step 3: 浏览器验收**

打开 `http://13.214.201.113:8000/dashboard`，切换到"持仓分析"，点击 MU.US 的"分析"按钮，等待完成后在抽屉中验证"新闻舆情"section 可见且有内容。
