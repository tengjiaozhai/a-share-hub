# 币安Alpha代币交易模块设计文档

> 生成日期：2026-05-30
> 版本：1.0

---

## 1. 项目概述

### 1.1 项目目标

在现有A股自动交易系统基础上，增加独立的加密货币交易模块，支持币安Alpha代币证券板块交易。

### 1.2 核心需求

- 支持币安Alpha代币交易
- 独立运行，与A股系统并行
- 复用现有风控框架
- 实现稳定交易并获取收益

### 1.3 成功标准

1. 能稳定运行加密货币交易
2. 实现正收益
3. 风险控制有效
4. 系统可扩展

---

## 2. 架构设计

### 2.1 整体架构

```
a-share-hub/
├── src/                    # A股系统
├── crypto-hub/            # 加密货币模块（新增）
│   ├── src/
│   │   ├── data/          # 数据层
│   │   ├── execution/     # 执行层
│   │   ├── strategy/      # 策略层
│   │   ├── risk/          # 风控层
│   │   └── api/           # API层
│   ├── config/            # 配置
│   └── tests/             # 测试
├── shared/                # 共享组件
│   ├── core/              # 核心工具
│   ├── risk/              # 风控框架
│   └── decision/          # 决策引擎
└── docs/
```

### 2.2 模块关系

- **独立模块**：crypto-hub作为独立模块，拥有完整的数据、执行、策略、风控和API层
- **共享组件**：复用A股系统的核心工具、风控框架和决策引擎
- **松耦合**：通过共享接口通信，避免直接依赖

### 2.3 技术栈

- **语言**：Python 3.11+
- **框架**：FastAPI
- **数据库**：PostgreSQL（现有）
- **缓存**：Redis（新增）
- **API**：币安官方REST/WebSocket API
- **测试**：pytest

---

## 3. 数据层设计

### 3.1 数据提供者

#### BinanceProvider

```python
class BinanceProvider:
    """币安数据提供者"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.binance.com"
        self.ws_url = "wss://stream.binance.com:9443"
    
    async def get_klines(self, symbol: str, interval: str, limit: int = 1000):
        """获取K线数据"""
        pass
    
    async def get_ticker(self, symbol: str):
        """获取实时价格"""
        pass
    
    async def get_order_book(self, symbol: str, limit: int = 100):
        """获取订单簿"""
        pass
    
    async def subscribe_websocket(self, symbols: list, callback):
        """订阅WebSocket实时数据"""
        pass
```

#### 数据模型

```python
# crypto_market_bar表
class CryptoMarketBar(Base):
    __tablename__ = "crypto_market_bar"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)  # 如 BTCUSDT
    trade_time = Column(DateTime, nullable=False)
    open = Column(Numeric(20, 8))
    high = Column(Numeric(20, 8))
    low = Column(Numeric(20, 8))
    close = Column(Numeric(20, 8))
    volume = Column(Numeric(20, 8))
    quote_volume = Column(Numeric(20, 8))
    trades_count = Column(Integer)
    created_at = Column(DateTime, default=func.now())

# crypto_position表
class CryptoPosition(Base):
    __tablename__ = "crypto_position"
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    quantity = Column(Numeric(20, 8))
    avg_cost = Column(Numeric(20, 8))
    market_value = Column(Numeric(20, 8))
    unrealized_pnl = Column(Numeric(20, 8))
    realized_pnl = Column(Numeric(20, 8))
    updated_at = Column(DateTime, onupdate=func.now())

# crypto_order表
class CryptoOrder(Base):
    __tablename__ = "crypto_order"
    
    id = Column(Integer, primary_key=True)
    order_id = Column(String(50), unique=True)  # 币安订单ID
    symbol = Column(String(20), nullable=False)
    side = Column(String(10))  # BUY/SELL
    type = Column(String(20))  # LIMIT/MARKET/STOP_LOSS
    quantity = Column(Numeric(20, 8))
    price = Column(Numeric(20, 8))
    status = Column(String(20))  # NEW/FILLED/CANCELED
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
```

### 3.2 数据缓存

使用Redis缓存实时数据：

```python
class CryptoDataCache:
    """加密货币数据缓存"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.ttl = 60  # 缓存60秒
    
    async def get_ticker(self, symbol: str):
        """获取缓存的ticker"""
        key = f"crypto:ticker:{symbol}"
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None
    
    async def set_ticker(self, symbol: str, data: dict):
        """设置ticker缓存"""
        key = f"crypto:ticker:{symbol}"
        await self.redis.setex(key, self.ttl, json.dumps(data))
```

### 3.3 WebSocket连接

```python
class CryptoWebSocketManager:
    """WebSocket管理器"""
    
    def __init__(self, provider: BinanceProvider):
        self.provider = provider
        self.connections = {}
        self.callbacks = {}
    
    async def subscribe_ticker(self, symbol: str, callback):
        """订阅实时价格"""
        pass
    
    async def subscribe_kline(self, symbol: str, interval: str, callback):
        """订阅K线数据"""
        pass
    
    async def unsubscribe(self, symbol: str):
        """取消订阅"""
        pass
```

---

## 4. 执行层设计

### 4.1 币安API客户端

```python
class BinanceClient:
    """币安API客户端"""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = aiohttp.ClientSession()
    
    async def create_order(self, symbol: str, side: str, type: str, 
                          quantity: float, price: float = None):
        """创建订单"""
        pass
    
    async def cancel_order(self, symbol: str, order_id: str):
        """取消订单"""
        pass
    
    async def get_order(self, symbol: str, order_id: str):
        """查询订单"""
        pass
    
    async def get_account(self):
        """查询账户信息"""
        pass
    
    async def get_balance(self, asset: str = None):
        """查询余额"""
        pass
```

### 4.2 订单管理器

```python
class CryptoOrderManager:
    """加密货币订单管理器"""
    
    def __init__(self, client: BinanceClient, risk_manager):
        self.client = client
        self.risk_manager = risk_manager
    
    async def place_order(self, order_request: OrderRequest):
        """下单"""
        # 1. 风控检查
        risk_check = await self.risk_manager.check_order(order_request)
        if not risk_check.passed:
            raise RiskCheckFailed(risk_check.reason)
        
        # 2. 创建订单
        order = await self.client.create_order(
            symbol=order_request.symbol,
            side=order_request.side,
            type=order_request.type,
            quantity=order_request.quantity,
            price=order_request.price
        )
        
        # 3. 保存订单
        await self.save_order(order)
        
        return order
    
    async def cancel_order(self, symbol: str, order_id: str):
        """取消订单"""
        pass
    
    async def get_open_orders(self, symbol: str = None):
        """获取未成交订单"""
        pass
```

### 4.3 账户管理器

```python
class CryptoAccountManager:
    """加密货币账户管理器"""
    
    def __init__(self, client: BinanceClient):
        self.client = client
    
    async def get_balance(self):
        """获取账户余额"""
        pass
    
    async def get_positions(self):
        """获取持仓"""
        pass
    
    async def get_portfolio_value(self):
        """获取投资组合价值"""
        pass
```

---

## 5. 策略层设计

### 5.1 Alpha代币策略

```python
class AlphaTokenStrategy:
    """Alpha代币交易策略"""
    
    def __init__(self, config: dict):
        self.config = config
        self.indicators = CryptoIndicators()
    
    async def analyze(self, market_data: pd.DataFrame) -> Signal:
        """分析市场数据，生成交易信号"""
        # 1. 计算技术指标
        indicators = self.indicators.calculate(market_data)
        
        # 2. 分析流动性
        liquidity_score = self.analyze_liquidity(market_data)
        
        # 3. 分析波动率
        volatility_score = self.analyze_volatility(market_data)
        
        # 4. 生成信号
        signal = self.generate_signal(indicators, liquidity_score, volatility_score)
        
        return signal
    
    def analyze_liquidity(self, data: pd.DataFrame) -> float:
        """分析流动性
        计算方法：使用24小时交易量和订单簿深度评估流动性
        分数范围：0-100，越高表示流动性越好
        """
        # 计算24小时交易量
        volume_24h = data['volume'].tail(24).sum()
        
        # 计算买卖价差（模拟）
        spread = (data['high'].iloc[-1] - data['low'].iloc[-1]) / data['close'].iloc[-1]
        
        # 综合评分
        volume_score = min(volume_24h / 1000000, 100)  # 交易量分数
        spread_score = max(0, 100 - spread * 1000)  # 价差分数
        
        return (volume_score + spread_score) / 2
    
    def analyze_volatility(self, data: pd.DataFrame) -> float:
        """分析波动率
        计算方法：使用ATR（平均真实波幅）和价格标准差
        分数范围：0-100，越高表示波动率越大
        """
        # 计算ATR
        high_low = data['high'] - data['high'].shift(1)
        high_close = abs(data['high'] - data['close'].shift(1))
        low_close = abs(data['low'] - data['close'].shift(1))
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=14).mean().iloc[-1]
        
        # 计算价格标准差
        price_std = data['close'].tail(20).std()
        
        # 综合评分
        atr_score = min(atr / data['close'].iloc[-1] * 1000, 100)
        std_score = min(price_std / data['close'].iloc[-1] * 1000, 100)
        
        return (atr_score + std_score) / 2
```

### 5.2 技术指标

```python
class CryptoIndicators:
    """加密货币技术指标"""
    
    def calculate(self, data: pd.DataFrame) -> dict:
        """计算技术指标"""
        return {
            "ma5": self.ma(data['close'], 5),
            "ma10": self.ma(data['close'], 10),
            "ma20": self.ma(data['close'], 20),
            "rsi": self.rsi(data['close'], 14),
            "macd": self.macd(data['close']),
            "bollinger": self.bollinger(data['close'], 20),
            "atr": self.atr(data, 14),
            "volume_ma": self.ma(data['volume'], 20)
        }
    
    def ma(self, series: pd.Series, period: int) -> pd.Series:
        """移动平均"""
        return series.rolling(window=period).mean()
    
    def rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """RSI指标"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def macd(self, series: pd.Series) -> dict:
        """MACD指标"""
        ema12 = series.ewm(span=12, adjust=False).mean()
        ema26 = series.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line
        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram
        }
```

### 5.3 信号融合

```python
class CryptoSignalFusion:
    """加密货币信号融合"""
    
    def __init__(self, config: dict):
        self.config = config
        self.weights = {
            "technical": 0.4,
            "liquidity": 0.2,
            "volatility": 0.2,
            "momentum": 0.2
        }
    
    def fuse(self, signals: dict) -> FinalSignal:
        """融合多个信号"""
        # 计算加权分数
        score = 0
        for key, weight in self.weights.items():
            if key in signals:
                score += signals[key] * weight
        
        # 确定动作
        if score >= 75:
            action = "BUY"
        elif score >= 60:
            action = "WATCH"
        elif score >= 40:
            action = "HOLD"
        else:
            action = "SELL"
        
        return FinalSignal(
            score=score,
            action=action,
            confidence=score / 100,
            details=signals
        )
```

---

## 6. 风险控制设计

### 6.1 扩展现有风控框架

```python
class CryptoPreTradeRisk(PreTradeRisk):
    """加密货币交易前风控"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.crypto_config = config.get("crypto", {})
    
    async def check_order(self, order_request: OrderRequest) -> RiskCheckResult:
        """检查订单风险"""
        # 1. 基础检查（复用A股风控）
        base_check = await super().check_order(order_request)
        if not base_check.passed:
            return base_check
        
        # 2. 加密货币特有检查
        crypto_check = await self.crypto_specific_checks(order_request)
        if not crypto_check.passed:
            return crypto_check
        
        return RiskCheckResult(passed=True)
    
    async def crypto_specific_checks(self, order_request: OrderRequest) -> RiskCheckResult:
        """加密货币特有风险检查"""
        # 波动率检查
        volatility = await self.check_volatility(order_request.symbol)
        if volatility > self.crypto_config.get("max_volatility", 0.1):
            return RiskCheckResult(
                passed=False,
                reason=f"波动率过高: {volatility:.2%}"
            )
        
        # 流动性检查
        liquidity = await self.check_liquidity(order_request.symbol)
        if liquidity < self.crypto_config.get("min_liquidity", 1000000):
            return RiskCheckResult(
                passed=False,
                reason=f"流动性不足: ${liquidity:,.0f}"
            )
        
        return RiskCheckResult(passed=True)
```

### 6.2 加密货币特有风控

```python
class CryptoRiskManager:
    """加密货币风险管理器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.max_position_ratio = config.get("max_position_ratio", 0.1)
        self.max_daily_loss = config.get("max_daily_loss", 0.05)
        self.max_volatility = config.get("max_volatility", 0.1)
    
    async def check_position_limit(self, symbol: str, quantity: float) -> bool:
        """检查持仓限制
        检查逻辑：单个代币持仓不超过总资产的max_position_ratio
        返回：True表示通过，False表示超限
        """
        # 获取当前持仓价值
        position_value = await self.get_position_value(symbol)
        
        # 获取总资产
        total_assets = await self.get_total_assets()
        
        # 计算持仓比例
        position_ratio = position_value / total_assets if total_assets > 0 else 0
        
        return position_ratio < self.max_position_ratio
    
    async def check_daily_loss(self) -> bool:
        """检查每日亏损限制
        检查逻辑：当日亏损不超过总资产的max_daily_loss
        返回：True表示通过，False表示亏损超限
        """
        # 获取当日盈亏
        daily_pnl = await self.get_daily_pnl()
        
        # 获取总资产
        total_assets = await self.get_total_assets()
        
        # 计算亏损比例
        loss_ratio = abs(daily_pnl) / total_assets if daily_pnl < 0 and total_assets > 0 else 0
        
        return loss_ratio < self.max_daily_loss
    
    async def check_volatility(self, symbol: str) -> float:
        """检查波动率
        计算方法：使用24小时ATR计算波动率
        返回：波动率百分比
        """
        # 获取K线数据
        klines = await self.get_klines(symbol, interval="1h", limit=24)
        
        # 计算ATR
        high_low = klines['high'] - klines['low']
        atr = high_low.mean()
        
        # 计算波动率
        volatility = atr / klines['close'].iloc[-1]
        
        return volatility
    
    async def check_liquidity(self, symbol: str) -> float:
        """检查流动性
        计算方法：使用24小时交易量评估流动性
        返回：流动性金额（美元）
        """
        # 获取24小时交易量
        ticker = await self.get_ticker(symbol)
        volume_24h = float(ticker['quoteVolume'])
        
        return volume_24h
```

### 6.3 资金管理

```python
class CryptoFundManager:
    """加密货币资金管理"""
    
    def __init__(self, config: dict):
        self.config = config
        self.total_capital = config.get("total_capital", 10000)
        self.max_risk_per_trade = config.get("max_risk_per_trade", 0.02)
    
    def calculate_position_size(self, symbol: str, price: float, 
                               stop_loss: float) -> float:
        """计算仓位大小"""
        risk_amount = self.total_capital * self.max_risk_per_trade
        risk_per_unit = abs(price - stop_loss)
        position_size = risk_amount / risk_per_unit
        return min(position_size, self.total_capital * self.max_position_ratio)
```

---

## 7. API设计

### 7.1 新增API端点

```python
# crypto_routes.py

@router.get("/crypto/health")
async def crypto_health():
    """加密货币模块健康检查"""
    return {"status": "ok", "module": "crypto"}

@router.get("/crypto/balance")
async def get_balance():
    """获取账户余额"""
    pass

@router.get("/crypto/positions")
async def get_positions():
    """获取持仓"""
    pass

@router.get("/crypto/orders")
async def get_orders(symbol: str = None, status: str = None):
    """获取订单列表"""
    pass

@router.post("/crypto/orders")
async def create_order(order_request: CryptoOrderRequest):
    """创建订单"""
    pass

@router.delete("/crypto/orders/{order_id}")
async def cancel_order(order_id: str):
    """取消订单"""
    pass

@router.get("/crypto/market/{symbol}")
async def get_market_data(symbol: str, interval: str = "1h", limit: int = 100):
    """获取市场数据"""
    pass

@router.get("/crypto/strategy/signals")
async def get_signals(symbol: str = None):
    """获取交易信号"""
    pass
```

### 7.2 仪表盘扩展

在现有仪表盘中增加加密货币板块：

```python
@router.get("/dashboard/crypto")
async def crypto_dashboard():
    """加密货币仪表盘"""
    return {
        "balance": await get_crypto_balance(),
        "positions": await get_crypto_positions(),
        "recent_orders": await get_recent_crypto_orders(),
        "signals": await get_recent_signals(),
        "pnl": await get_crypto_pnl()
    }
```

---

## 8. 配置设计

### 8.1 配置文件

```yaml
# config/crypto.yaml

binance:
  api_key: "${BINANCE_API_KEY}"
  api_secret: "${BINANCE_API_SECRET}"
  testnet: true  # 使用测试网

trading:
  enabled: true
  symbols:
    - "BTCUSDT"
    - "ETHUSDT"
    - "BNBUSDT"
  intervals:
    - "1h"
    - "4h"
    - "1d"

risk:
  max_position_ratio: 0.1
  max_daily_loss: 0.05
  max_volatility: 0.1
  min_liquidity: 1000000
  stop_loss_ratio: 0.02

strategy:
  name: "alpha_token"
  parameters:
    ma_short: 5
    ma_long: 20
    rsi_period: 14
    rsi_overbought: 70
    rsi_oversold: 30
```

### 8.2 环境变量

```env
# .env

# 币安API
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# 加密货币模块
CRYPTO_ENABLED=true
CRYPTO_TESTNET=true
CRYPTO_MAX_POSITION_RATIO=0.1
CRYPTO_MAX_DAILY_LOSS=0.05

# Redis
REDIS_URL=redis://localhost:6379/1
```

---

## 9. 测试设计

### 9.1 单元测试

```python
# tests/test_crypto_data.py
class TestBinanceProvider:
    """测试币安数据提供者"""
    
    async def test_get_klines(self):
        """测试获取K线数据"""
        pass
    
    async def test_get_ticker(self):
        """测试获取实时价格"""
        pass

# tests/test_crypto_risk.py
class TestCryptoRisk:
    """测试加密货币风控"""
    
    async def test_position_limit(self):
        """测试持仓限制"""
        pass
    
    async def test_volatility_check(self):
        """测试波动率检查"""
        pass

# tests/test_crypto_strategy.py
class TestCryptoStrategy:
    """测试加密货币策略"""
    
    def test_signal_generation(self):
        """测试信号生成"""
        pass
    
    def test_signal_fusion(self):
        """测试信号融合"""
        pass
```

### 9.2 集成测试

```python
# tests/integration/test_crypto_trading.py
class TestCryptoTrading:
    """测试加密货币交易流程"""
    
    async def test_full_trading_cycle(self):
        """测试完整交易周期"""
        # 1. 获取市场数据
        # 2. 生成交易信号
        # 3. 风控检查
        # 4. 创建订单
        # 5. 查询订单状态
        pass
```

---

## 10. 部署设计

### 10.1 部署架构

```
Production Environment:
├── API Server (FastAPI)
│   ├── A股模块
│   └── 加密货币模块
├── Database (PostgreSQL)
├── Cache (Redis)
├── Scheduler (APScheduler)
└── Monitor (Prometheus + Grafana)
```

### 10.2 部署脚本

```bash
#!/bin/bash
# deploy_crypto.sh

# 1. 安装依赖
pip install -r requirements.txt

# 2. 数据库迁移
alembic upgrade head

# 3. 启动服务
uvicorn src.main:app --host 0.0.0.0 --port 8000

# 4. 启动调度器
python -m src.scheduler.crypto_jobs
```

### 10.3 监控告警

```python
# monitoring/crypto_alerts.py

class CryptoAlertManager:
    """加密货币告警管理"""
    
    async def check_balance_alert(self):
        """余额告警"""
        pass
    
    async def check_loss_alert(self):
        """亏损告警"""
        pass
    
    async def check_volatility_alert(self):
        """波动率告警"""
        pass
```

---

## 11. 实现计划

### 11.1 阶段1：基础架构（1-2周）

- [ ] 项目结构搭建
- [ ] 币安API集成
- [ ] 基础数据模型
- [ ] 配置管理
- [ ] 单元测试框架

### 11.2 阶段2：核心功能（2-3周）

- [ ] 数据层实现
  - [ ] BinanceProvider
  - [ ] WebSocket管理
  - [ ] 数据缓存
- [ ] 执行层实现
  - [ ] BinanceClient
  - [ ] OrderManager
  - [ ] AccountManager
- [ ] 策略层实现
  - [ ] AlphaTokenStrategy
  - [ ] 技术指标
  - [ ] 信号融合

### 11.3 阶段3：风控和测试（1-2周）

- [ ] 风控集成
  - [ ] 扩展PreTradeRisk
  - [ ] 加密货币特有风控
  - [ ] 资金管理
- [ ] 单元测试
- [ ] 集成测试
- [ ] 性能测试

### 11.4 阶段4：部署和监控（1周）

- [ ] 部署脚本
- [ ] 监控告警
- [ ] 日志审计
- [ ] 文档完善

---

## 12. 风险评估

### 12.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 币安API限制 | 高 | 使用WebSocket，实现重试机制 |
| 数据延迟 | 中 | 使用缓存，优化数据获取 |
| 系统稳定性 | 高 | 完善错误处理，增加监控 |

### 12.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 市场波动 | 高 | 严格风控，设置止损 |
| 流动性风险 | 中 | 选择高流动性代币 |
| 监管风险 | 高 | 遵守当地法规，设置交易限额 |

---

## 13. 总结

本设计文档详细描述了币安Alpha代币交易模块的架构、数据层、执行层、策略层、风控层、API层、配置、测试、部署和实现计划。通过独立模块设计，既能复用现有A股系统的核心组件，又能保持模块的独立性和可扩展性。

预计总工时：6-8周
预计总成本：主要包括币安API调用费用、服务器资源费用和开发人力成本

---

## 附录

### A. 参考文档

- [币安API文档](https://binance-docs.github.io/apidocs/)
- [币安WebSocket文档](https://binance-docs.github.io/apidocs/ws/en/)
- [加密货币交易最佳实践](https://github.com/binance-exchange/binance-official-api-docs)

### B. 术语表

- **Alpha代币**：币安平台上的链上Web3代币
- **BSC**：币安智能链
- **WebSocket**：实时数据传输协议
- **风控**：风险控制
- **信号融合**：将多个交易信号合并为一个决策
