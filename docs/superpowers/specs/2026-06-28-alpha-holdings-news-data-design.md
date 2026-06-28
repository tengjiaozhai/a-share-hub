# Alpha 持仓分析新闻数据接入设计

## 背景

当前持仓分析流式管线（`POST /api/v1/alpha/analysis-runs`）的 `snapshot` 阶段硬编码 `news={"status":"unavailable","items":[]}`，导致 ResearchManager 的置信度始终被降至 0.2-0.4，`sentiment_view` 固定为"新闻/舆情数据不可用"。

## 目标

在 `AnalysisSnapshotBuilder` 中接入真实新闻数据，使 LLM 研究经理能基于新闻证据做出更高质量的评级和置信度判断。

## 数据源选型

| 源 | A 股 | 美股 | 免费 | 免登录 | 封禁风险 | 项目已有依赖 |
|---|---|---|---|---|---|---|
| **akshare `stock_news_em`** | ✅ | ✅ | ✅ | ✅ | 低 | ✅ |
| 雪球 | ✅ | ❌ IP 被封 | ✅ | ❌ | 高 | ❌ |
| TradingView | ❌ 无后端 API | ❌ | N/A | N/A | N/A | ❌ |
| 东方财富 EMQuant | ✅ | ✅ | ❌ | ❌ | 低 | ❌ |

**选定方案：akshare `stock_news_em`**，理由：
- 零新依赖，akshare 已是项目依赖
- A 股美股均覆盖（已验证 600519 和 AAPL 各返回 10 条）
- 免费免登录，东方财富官方接口
- 返回结构化数据：关键词/新闻标题/新闻内容/发布时间/文章来源/新闻链接

## 架构变更

### 现状
```
routes_alpha.py
  └─ AnalysisSnapshotBuilder(history_loader, fundamental_loader)
       └─ build() → news={"status":"unavailable","items":[]}
```

### 目标
```
routes_alpha.py
  └─ AnalysisSnapshotBuilder(history_loader, fundamental_loader, news_loader)
       └─ build() → news=news_loader(symbol) or {"status":"error","items":[]}
```

### 接口契约

`news_loader(symbol: str) -> dict` 返回：
```json
{
  "status": "ok",
  "count": 10,
  "items": [
    {
      "title": "贵州茅台今日分红",
      "summary": "贵州茅台宣布每股派发现金红利28.02423元...",
      "source": "21世纪经济报道",
      "published_at": "2026-06-26 09:17:00",
      "url": "http://finance.eastmoney.com/a/..."
    }
  ]
}
```

### 文件变更清单

| 文件 | 操作 | 变更 |
|------|------|------|
| `src/alpha/analysis_snapshot.py` | Modify | `__init__` 新增 `news_loader` 参数；`build()` 调用 `news_loader`，失败时降级 |
| `src/api/routes_alpha.py` | Modify | `_build_run_service` 中构造 `news_loader` 函数 |
| `src/alpha/analysis_agents.py` | Modify | ResearchManager prompt 适配真实新闻数据 |
| `src/api/dashboard_page/scripts/alpha.js` | Modify | 抽屉 research 区增加新闻展示 |
| `tests/test_alpha_analysis_snapshot.py` | Modify | 新增 news_loader 测试用例 |
| `tests/test_alpha_analysis_agents.py` | Modify | 验证 LLM 收到真实新闻后的行为 |

### 不变的部分

- `AnalysisSnapshot.news` 字段类型保持 `dict`（不改 Pydantic 模型）
- `analysis_run_service.py` 不变（news 数据在 snapshot 阶段注入）
- SSE 事件流结构不变
- 数据库 schema 不变

## 风险与降级

- akshare 接口异常 → `news_loader` 返回 `{"status":"error","items":[], "error":"..."}` → LLM 收到空新闻，行为与现在一致（置信度降低）
- 东方财富接口变动 → akshare 上游会跟进，属常规维护
