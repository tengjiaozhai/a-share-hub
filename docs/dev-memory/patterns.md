# 项目模式

## LLM 客户端调用模式

```python
# 从 Settings 初始化，自动读取 .env
client = LLMClient()       # provider/api_key/model/base_url 全从 settings 来
raw = client.generate(prompt)  # mock 或真实，失败降级，永远不抛异常
decision = parse_decision_output(raw)  # HOLD/confidence=0 作为失败兜底
```

规则：`LLMClient` 不接受手动参数，必须从 `Settings` 读取，确保 `.env` 是唯一配置入口。

---

## 行情数据提供者模式

```python
provider = AkshareProvider()
if provider.is_available():          # 探针：检查 import akshare
    snap = provider.get_realtime_quote("600519.SH")
    hist = provider.get_history("600519.SH", start, end)
```

规则：`ProviderChain` 内按顺序尝试多个 provider，全部失败返回 `None` / 空 DataFrame，不抛异常。

---

## 服务部署完整依赖清单（AWS py311 环境）

每次在新服务器上部署必须安装：

```bash
~/miniconda3/envs/py311/bin/pip install psycopg[binary] httpx akshare
# 然后
~/miniconda3/envs/py311/bin/pip install -e .
```

顺序：先手动装驱动层（psycopg3、httpx），再装项目包。

---

## 远程服务器管理

### SSH连接模式

使用sshpass工具进行非交互式SSH连接：

```bash
sshpass -p '密码' ssh -o StrictHostKeyChecking=no root@服务器IP '命令'
```

或使用SSH密钥：

```bash
ssh -i /path/to/key.pem user@server '命令'
```

### 服务管理模式

检查和管理系统服务：

```bash
# 检查服务状态
systemctl status 服务名

# 停止服务
systemctl stop 服务名
systemctl disable 服务名

# 检查Docker容器
docker ps
docker stop 容器名
```

### 资源监控模式

检查服务器资源使用：

```bash
# CPU和内存
top -bn1 | head -20
free -h
uptime

# 磁盘
df -h

# 进程
ps aux --sort=-%cpu | head -10
ps aux --sort=-%mem | head -10
```

---

## Python环境管理

### conda环境调用模式

使用完整路径调用conda环境中的Python：

```bash
/home/ec2-user/miniconda3/envs/py311/bin/python
/home/ec2-user/miniconda3/envs/py311/bin/pip
```

### 依赖安装模式

在项目目录中安装依赖：

```bash
cd /home/ec2-user/a-share-hub
/home/ec2-user/miniconda3/envs/py311/bin/pip install -e .
```

---

## 数据库连接模式

### PostgreSQL连接

使用完整路径和密码连接：

```bash
PGPASSWORD=douya psql -U douya -h localhost -d douya
```

### Python中的数据库连接

使用SQLAlchemy连接PostgreSQL：

```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://douya:douya@localhost:5432/douya"
engine = create_engine(DATABASE_URL)
```

---

## Git同步模式

### 服务器推送

```bash
cd /home/ec2-user/a-share-hub
git add .
git commit -m "描述"
git push origin master
```

### 本地拉取

```bash
cd ~/workSpace/tranding/a-share-hub
git pull origin master
```

### SSH密钥生成

```bash
ssh-keygen -t rsa -b 4096 -C 'email@example.com' -f ~/.ssh/id_rsa -N ''
cat ~/.ssh/id_rsa.pub
```

---

## 仪表盘模式

### FastAPI仪表盘路由

```python
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    with open("src/api/dashboard.html", "r", encoding="utf-8") as f:
        return f.read()
```

### 仪表盘API端点

```python
@router.get("/api/v1/dashboard/status")
def get_system_status():
    return {
        "timestamp": datetime.now().isoformat(),
        "system": {"name": "A股自动交易系统", "version": "0.1.0"},
        "components": {"database": {"status": "connected"}},
    }
```

---

## 项目结构模式

### 标准Python项目结构

```
项目根目录/
├── src/                # 源代码
│   ├── __init__.py
│   ├── main.py         # 入口点
│   └── core/           # 核心模块
├── tests/              # 测试文件
├── pyproject.toml      # 项目配置
├── .env.example        # 环境变量示例
└── README.md           # 项目说明
```

### FastAPI应用模式

```python
from fastapi import FastAPI
from src.api.routes_health import router as health_router
from src.api.routes_dashboard import router as dashboard_router

def build_app() -> FastAPI:
    app = FastAPI(title="应用名")
    app.include_router(health_router)
    app.include_router(dashboard_router)
    return app
```

---

## 测试模式

### pytest配置

在pyproject.toml中配置pytest：

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

### 测试文件命名

测试文件以`test_`开头，放在`tests/`目录下：

```
tests/
├── test_bootstrap.py
├── test_market_clock.py
└── test_market_rules.py
```

---

## 部署模式

### 阶段门控模式

每个阶段必须通过验收才能进入下一阶段：

1. 编写失败的测试
2. 运行测试验证失败
3. 实现最小代码
4. 运行阶段验收门
5. 提交代码

### 环境变量管理

使用`.env.example`作为模板，实际值放在`.env`中：

```bash
cp .env.example .env
# 编辑.env文件填入实际值
```

### uvicorn启动模式

```bash
# 前台启动
~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# 后台启动
nohup ~/miniconda3/envs/py311/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 > /tmp/uvicorn.log 2>&1 &
```

---

## 错误处理模式

### 进程资源耗尽

当服务器资源耗尽时：

1. 识别占用资源的进程：`ps aux --sort=-%cpu`
2. 停止不必要的服务：`systemctl stop 服务名`
3. 杀死占用资源的进程：`pkill -9 -f 进程名`
4. 检查资源释放情况：`free -h`和`uptime`

### 连接失败处理

SSH或数据库连接失败时：

1. 检查凭据是否正确
2. 检查服务是否运行
3. 检查防火墙设置
4. 使用详细错误信息诊断

### Git推送失败处理

1. 检查SSH密钥是否添加到GitHub
2. 检查GitHub主机密钥是否在known_hosts
3. 检查仓库权限
