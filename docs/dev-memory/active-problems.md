# 活跃问题

## 服务器资源不足

**状态**: ✅ 已解决  
**发现时间**: 2026-05-23  
**解决时间**: 2026-05-24  
**影响**: 已解决

### 问题描述

阿里云服务器（121.43.231.155）配置为2核2GB内存，无法满足A股自动交易系统的运行需求。

### 解决方案

迁移到AWS EC2服务器（13.214.201.113），配置2核4GB，满足基本运行需求。

### 新服务器信息

- **IP**: 13.214.201.113
- **用户**: ec2-user
- **配置**: 2核4GB内存
- **操作系统**: Amazon Linux 2023
- **Python**: 3.11.15 (via Miniconda)
- **数据库**: PostgreSQL 15.16

---

## PostgreSQL权限限制

**状态**: ✅ 已解决  
**发现时间**: 2026-05-23  
**影响**: 低

### 解决方案

AWS EC2上已配置douya用户和douya数据库，连接正常。

### 配置

```
DATABASE_URL=postgresql://douya:douya@localhost:5432/douya
```

---

## conda自动激活问题

**状态**: ✅ 已解决  
**发现时间**: 2026-05-23  
**影响**: 中

### 解决方案

使用完整路径`/home/ec2-user/miniconda3/envs/py311/bin/python`调用Python。

---

## 代码同步问题

**状态**: ✅ 已解决  
**发现时间**: 2026-05-24  
**影响**: 高

### 问题描述

AWS EC2服务器上的代码需要与本地同步，方便版本迭代。

### 解决方案

使用GitHub私有仓库同步代码：
- **仓库地址**: https://github.com/tengjiaozhai/a-share-hub
- **认证方式**: SSH密钥
- **同步方式**: git push/pull

### 同步流程

```bash
# 服务器推送
cd /home/ec2-user/a-share-hub
git add .
git commit -m "描述"
git push origin master

# 本地拉取
cd ~/workSpace/tranding/a-share-hub
git pull origin master
```

---

## AWS安全组端口未开放

**状态**: ⏸️ 待处理  
**发现时间**: 2026-05-24  
**影响**: 中

### 问题描述

AWS EC2的8000端口未从外部开放，无法直接访问仪表盘。

### 临时解决方案

使用SSH隧道访问：
```bash
ssh -i /Users/shenmingjie/.ssh/xingxing.pem -L 8000:localhost:8000 ec2-user@13.214.201.113
# 浏览器访问: http://localhost:8000/dashboard
```

### 永久解决方案

在AWS控制台开放8000端口入站规则。
