# 腾讯历史 K 线替换计划

## 问题

`AkshareProvider.get_history()` 当前返回空 DataFrame，因为东方财富 `push2his.eastmoney.com` 被代理拦截。回测和信号生成都依赖历史数据。

## 解决方案

用腾讯财经 `web.ifzq.gtimg.cn` 的 K 线接口替换，该接口已验证可用。

### 腾讯 K 线 API

```
GET https://web.ifzq.gtimg.cn/appstock/app/fqkline/get
参数: param={tx_code},{freq},{start},{end},{limit},{adjust}

tx_code:  sh600519 / sz000858
freq:     day / week / month
adjust:   qfq(前复权) / hfq(后复权) / 空(不复权)
```

返回格式:
```json
{
  "code": 0,
  "data": {
    "sh600519": {
      "qfqday": [
        ["2025-01-02", "1472.443", "1436.443", "1472.933", "1428.443", "50029.000"],
        // [日期, 开盘, 收盘, 最高, 最低, 成交量]
      ]
    }
  }
}
```

## 改动范围

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/data/providers/akshare_provider.py` | 修改 | `get_history()` 实现腾讯 K 线 |
| `tests/test_akshare_provider.py` | 新建 | 测试 `get_history()` |
| `docs/dev-memory/decisions.md` | 更新 | 记录腾讯 K 线决策 |

## 实现细节

### akshare_provider.py

新增辅助函数:
```python
def _fetch_tencent_kline(symbol: str, start_date: str, end_date: str, freq: str = "day") -> pd.DataFrame:
    """腾讯历史 K 线。返回 columns: [date, open, close, high, low, volume]"""
```

修改 `get_history()`:
- symbol `600519.SH` → 腾讯 code `sh600519`
- 调用 `_fetch_tencent_kline()`
- 返回标准 DataFrame（与 akshare 原格式对齐）

### 测试

mock `requests.get`，验证:
- 正常返回解析
- 空数据处理
- 网络异常降级

## 验证

```bash
# 单元测试
/opt/anaconda3/envs/py311/bin/python3 -m pytest tests/test_akshare_provider.py -v

# 手动验证
/opt/anaconda3/envs/py311/bin/python3 -c "
from src.data.providers.akshare_provider import AkshareProvider
p = AkshareProvider()
from datetime import datetime
df = p.get_history('600519.SH', datetime(2025,1,1), datetime(2025,3,31))
print(df.head())
print(f'rows: {len(df)}')
"

# 回测验证
/opt/anaconda3/envs/py311/bin/python3 -m src.main backtest --symbols 600519.SH --start 2025-01-01 --end 2025-03-31
```
