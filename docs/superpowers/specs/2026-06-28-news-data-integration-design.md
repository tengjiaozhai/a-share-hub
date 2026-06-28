# News Data Integration Design

> 将新闻数据接入 Alpha 持仓分析流式管线

## 问题

`AnalysisSnapshotBuilder.build()` 在 `src/alpha/analysis_snapshot.py:56` 硬编码 `missing.append("news")` 并返回 `news={"status":"unavailable","items":[]}`。导致：
- research 阶段 `confidence` 被强制降到 0.2-0.4
- `sentiment_view` 固定为"新闻/舆情数据不可用"
- LLM 缺少舆情证据，评级保守

## 数据源选型

| 源 | A股 | 美股 | 免费 | 免登录 | 封禁风险 | 已有依赖 |
|---|---|---|---|---|---|---|
| **akshare `stock_news_em`** | ✅ | ✅ | ✅ | ✅ | 低 | ✅ |
| 雪球 | ✅ | ❌IP被封 | ✅ | ❌cookie | 高 | ❌ |
| TradingView | ❌无API | ❌ | N/A | N/A | N/A | ❌ |
| EMQuant | ✅ | ✅ | ❌ | ❌ | 低 | ❌ |

**选定：`akshare.stock_news_em`**（东方财富新闻接口）
- 验证：`stock_news_em("600519")` 返回10条，列：`关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接`
- 验证：`stock_news_em("AAPL")` 返回10条美股新闻
- 零新增依赖

## 架构变更

### 现状
```
routes_alpha.py → AnalysisSnapshotBuilder(history_loader, fundamental_loader)
                  build() → news={"status":"unavailable","items":[]}
```

### 目标
```
routes_alpha.py → AnalysisSnapshotBuilder(history_loader, fundamental_loader, news_loader)
                  build() → news=news_loader(symbol) or {"status":"error","items":[]}
```

### 接口契约

`news_loader(symbol: str) -> dict` 返回：
```json
{
  "status": "ok",
  "items": [
    {"title": "...", "summary": "...", "source": "...", "published_at": "...", "url": "..."}
  ]
}
```

失败时返回 `{"status": "error", "items": [], "error": "..."}`

### 文件变更

| 文件 | 操作 | 变更 |
|------|------|------|
| `src/alpha/analysis_snapshot.py` | Modify | 加 `news_loader` 参数，`build()` 调用它 |
| `src/api/routes_alpha.py` | Modify | 构造 `news_loader` 并传入 builder |
| `src/api/dashboard_page/scripts/alpha.js` | Modify | 抽屉 research section 加新闻展示 |
| `src/api/dashboard_page/partials/view_alpha.html` | Modify | news section HTML |
| `src/api/dashboard_page/styles/alpha.css` | Modify | 新闻列表样式 |
| `tests/test_alpha_analysis_snapshot.py` | Modify | 测试 news_loader 有/无场景 |
| `tests/test_dashboard_page_contract.py` | Modify | 验证 news section 存在 |

### 不变
- `AnalysisSnapshot` Pydantic 模型：`news: dict` 类型不变
- `analysis_agents.py`：LLM prompt 不变（已有 data_gaps 降级逻辑，有新闻后自然不再降级）
- 数据库：无需 migration

## 风险与降级
- akshare 接口变动 → `news_loader` 返回 error → 降级为 unavailable，行为与现在一致
- 东方财富限流 → try/except 兜底，不影响主流程
