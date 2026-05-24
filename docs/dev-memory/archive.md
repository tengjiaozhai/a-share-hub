# 归档信息

## 已弃用的服务器配置

**弃用时间**: 2026-05-23  
**原因**: 服务器配置过低，无法满足方案运行需求

### 原配置

- **服务器**: 121.43.231.155
- **CPU**: 2核
- **内存**: 2GB
- **磁盘**: 40GB

### 问题

- 安装依赖时CPU和内存耗尽
- 负载平均达到18+
- Swap过度使用导致性能下降

### 替代方案

升级到4核8GB或迁移到Oracle Cloud免费实例。

---

## 已停止的服务

**停止时间**: 2026-05-23  
**原因**: 释放服务器资源

### 服务列表

1. **MySQL**
   - 状态: 已停止并禁用
   - 内存占用: 约85MB
   - 原因: 不需要，PostgreSQL已足够

2. **ChromaDB容器**
   - 状态: 已停止
   - 内存占用: 约400MB
   - 原因: 向量数据库暂不需要

3. **MinIO容器**
   - 状态: 已停止
   - 内存占用: 约115MB
   - 原因: 对象存储暂不需要

### 恢复方法

如需恢复这些服务：

```bash
# 恢复MySQL
systemctl start mysql
systemctl enable mysql

# 恢复Docker容器
docker start chroma
docker start minio
```

---

## 已弃用的数据库配置

**弃用时间**: 2026-05-23  
**原因**: 权限限制，改用现有数据库

### 原配置

```python
DATABASE_URL=postgresql://douya:douya@localhost:5432/a_share_hub
```

### 问题

douya用户没有创建数据库的权限。

### 新配置

```python
DATABASE_URL=postgresql://douya:douya@localhost:5432/douya
```

---

## 已弃用的conda配置

**弃用时间**: 2026-05-23  
**原因**: 自动激活消耗资源

### 原配置

在`~/.bashrc`中添加conda初始化代码。

### 问题

每次SSH连接时conda自动激活，消耗额外CPU和内存。

### 新配置

从`~/.bashrc`中移除conda初始化代码，使用完整路径调用Python。

---

## 已弃用的pyproject.toml配置

**弃用时间**: 2026-05-23  
**原因**: build-backend配置错误

### 原配置

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.backends._legacy:_Backend"
```

### 问题

pip安装时报错"Cannot import 'setuptools.backends._legacy'"

### 新配置

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"
```
