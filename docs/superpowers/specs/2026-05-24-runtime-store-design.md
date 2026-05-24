# RuntimeStore 设计文档

## 项目概述

为 A 股自动交易系统实现运行时存储和控制平面行为，包括：
1. 创建 `src/storage/runtime_store.py` - SQLite 存储
2. 修改 `src/execution/execution_plan_service.py` - 生成稳定 ID
3. 修改 API 路由使用 runtime_store
4. 创建 Windows 代理拉取执行计划脚本
5. 修改本地风险检查实现 fail-closed

## 当前状态分析

### 现有实现问题

1. **执行计划服务** (`src/execution/execution_plan_service.py`):
   - 没有生成稳定 ID
   - 返回的计划没有持久化

2. **API 路由**:
   - `routes_execution_plans.py`: 返回空列表，没有实际存储
   - `routes_broker_events.py`: 仅返回确认，没有存储事件
   - `routes_kill_switch.py`: 使用内存状态，重启后丢失

3. **Windows 代理**:
   - 缺少拉取执行计划的脚本
   - `local_risk_check.py`: 没有实现 fail-closed 逻辑

### 技术栈

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0+
- SQLite (运行时存储)
- Pydantic 数据验证

## 设计方案

### 方案一：SQLite 单文件存储 (推荐)

**优点**：
- 简单轻量，无需额外服务
- 支持事务和并发读
- 适合单机部署场景

**缺点**：
- 不支持分布式部署
- 写入性能有限

### 方案二：PostgreSQL 存储

**优点**：
- 支持分布式部署
- 更好的并发性能
- 更丰富的功能

**缺点**：
- 需要额外服务
- 部署复杂度高

### 方案三：Redis + 持久化

**优点**：
- 高性能
- 支持分布式

**缺点**：
- 需要额外服务
- 数据持久化复杂

**推荐方案一**：SQLite 单文件存储，因为当前系统是单机部署，SQLite 足够满足需求。

## 详细设计

### 1. RuntimeStore 类设计

```python
class RuntimeStore:
    def __init__(self, db_path: str = "runtime.db"):
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}")
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def init_schema(self):
        """初始化数据库表结构"""
        pass
    
    def insert_execution_plan(self, plan: Dict[str, Any]) -> str:
        """插入执行计划，返回计划 ID"""
        pass
    
    def list_ready_execution_plans(self) -> List[Dict[str, Any]]:
        """获取待执行的计划列表"""
        pass
    
    def mark_plan_acknowledged(self, plan_id: str) -> bool:
        """标记计划已确认"""
        pass
    
    def insert_broker_event(self, event: Dict[str, Any]) -> str:
        """插入经纪商事件"""
        pass
    
    def list_broker_events(self) -> List[Dict[str, Any]]:
        """获取经纪商事件列表"""
        pass
    
    def set_kill_switch(self, active: bool) -> None:
        """设置紧急停止状态"""
        pass
    
    def get_kill_switch(self) -> bool:
        """获取紧急停止状态"""
        pass
```

### 2. 数据库表结构

#### execution_plans 表
```sql
CREATE TABLE execution_plans (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    action TEXT NOT NULL,
    target_value REAL NOT NULL,
    ready BOOLEAN NOT NULL,
    reason TEXT,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP
);
```

#### broker_events 表
```sql
CREATE TABLE broker_events (
    id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    order_id TEXT,
    plan_id TEXT,
    payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### kill_switch 表
```sql
CREATE TABLE kill_switch (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    active BOOLEAN NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. 稳定 ID 生成

使用 `hashlib` 生成基于内容的稳定 ID：

```python
import hashlib
import json

def generate_plan_id(plan: Dict[str, Any]) -> str:
    """生成稳定的计划 ID"""
    content = json.dumps(plan, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]
```

### 4. Fail-Closed 风险检查

修改 `local_risk_check.py` 实现 fail-closed：

```python
def local_gate(trader_connected: bool, available_cash: float, requested_value: float) -> Dict[str, Any]:
    """本地风险检查 - fail-closed 设计"""
    # 默认拒绝
    result = {"approved": False, "reason": "unknown error"}
    
    try:
        if not trader_connected:
            return {"approved": False, "reason": "trader disconnected"}
        if requested_value > available_cash:
            return {"approved": False, "reason": "insufficient local cash"}
        return {"approved": True, "reason": "approved"}
    except Exception as e:
        # 任何异常都拒绝
        return {"approved": False, "reason": f"risk check failed: {str(e)}"}
```

### 5. Windows 代理脚本

创建 `windows_agent/pull_execution_plans.py`：

```python
import requests
from typing import List, Dict, Any

def pull_execution_plans(api_base_url: str) -> List[Dict[str, Any]]:
    """从服务器拉取待执行的计划"""
    try:
        response = requests.get(f"{api_base_url}/api/v1/execution-plans/ready")
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Failed to pull execution plans: {e}")
        return []
```

## 实现步骤

1. **创建 RuntimeStore** (`src/storage/runtime_store.py`)
   - 实现 SQLite 存储
   - 实现所有必需方法
   - 添加单元测试

2. **修改 execution_plan_service.py**
   - 添加稳定 ID 生成
   - 集成 RuntimeStore

3. **修改 API 路由**
   - `routes_execution_plans.py`: 使用 RuntimeStore
   - `routes_broker_events.py`: 使用 RuntimeStore
   - `routes_kill_switch.py`: 使用 RuntimeStore

4. **创建 Windows 代理脚本**
   - `pull_execution_plans.py`: 拉取执行计划
   - 修改 `local_risk_check.py`: 实现 fail-closed

5. **更新测试**
   - 更新现有测试
   - 添加新测试覆盖 RuntimeStore

## 待澄清问题

### 问题 1：数据库路径配置

**选项 A：固定路径**
```python
# 使用固定路径
DB_PATH = "runtime.db"
```

**选项 B：可配置路径**
```python
# 通过环境变量或配置文件配置
DB_PATH = os.getenv("RUNTIME_DB_PATH", "runtime.db")
```

**选项 C：使用项目数据目录**
```python
# 使用项目的数据目录
DB_PATH = Path("data/runtime.db")
```

**推荐选项 B**：可配置路径，便于测试和部署。

### 问题 2：并发访问策略

**选项 A：单连接串行化**
```python
# 使用单连接，所有操作串行化
engine = create_engine("sqlite:///runtime.db", connect_args={"check_same_thread": False})
```

**选项 B：连接池**
```python
# 使用连接池，限制并发数
engine = create_engine("sqlite:///runtime.db", pool_size=5, max_overflow=10)
```

**选项 C：WAL 模式**
```python
# 使用 WAL 模式支持并发读
engine = create_engine("sqlite:///runtime.db")
with engine.connect() as conn:
    conn.execute("PRAGMA journal_mode=WAL")
```

**推荐选项 C**：WAL 模式，支持并发读，提高性能。

### 问题 3：数据保留策略

**选项 A：无限保留**
```python
# 保留所有历史数据
```

**选项 B：按时间清理**
```python
# 清理超过 30 天的数据
def cleanup_old_data(self, days: int = 30):
    pass
```

**选项 C：按数量限制**
```python
# 只保留最近的 1000 条记录
def cleanup_old_data(self, max_records: int = 1000):
    pass
```

**推荐选项 B**：按时间清理，保留 30 天数据，便于审计。

### 问题 4：错误处理策略

**选项 A：抛出异常**
```python
def insert_execution_plan(self, plan: Dict[str, Any]) -> str:
    try:
        # 数据库操作
    except Exception as e:
        raise RuntimeError(f"Failed to insert plan: {e}")
```

**选项 B：返回错误码**
```python
def insert_execution_plan(self, plan: Dict[str, Any]) -> tuple[str, str]:
    try:
        # 数据库操作
        return plan_id, None
    except Exception as e:
        return None, str(e)
```

**选项 C：记录日志并返回默认值**
```python
def insert_execution_plan(self, plan: Dict[str, Any]) -> str:
    try:
        # 数据库操作
    except Exception as e:
        logger.error(f"Failed to insert plan: {e}")
        return None
```

**推荐选项 A**：抛出异常，让调用者处理错误。

## 验证标准

1. **功能验证**：
   - 所有 API 端点正常工作
   - 数据持久化正确
   - 稳定 ID 生成正确

2. **测试验证**：
   - 所有现有测试通过
   - 新增测试覆盖 RuntimeStore
   - 测试覆盖率 > 80%

3. **代码质量**：
   - 通过 ruff lint 检查
   - 通过 mypy 类型检查
   - 无安全漏洞

## 风险评估

1. **数据迁移**：当前是全新实现，无需迁移
2. **并发问题**：SQLite 支持并发读，但写入需要串行化
3. **性能问题**：单机部署场景下性能足够

## 依赖项

- SQLAlchemy 2.0+
- FastAPI
- Pydantic
- hashlib (标准库)

## 时间估算

- RuntimeStore 实现：2 小时
- API 路由修改：1 小时
- Windows 代理脚本：1 小时
- 测试更新：1 小时
- 总计：5 小时
