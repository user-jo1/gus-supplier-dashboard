# GUS 劳务供应商管理看板 - Docker 部署指南

## 📁 项目结构

```
20260618112854/
├── Dockerfile              # Docker 多阶段构建文件
├── docker-compose.yml      # 一键编排部署（Nginx + App）
├── .dockerignore           # 构建时排除的文件
├── server/
│   ├── server.js           # Node.js Express 后端（安全头/反爬/限流）
│   └── package.json        # Node.js 依赖
├── nginx/
│   ├── nginx.conf          # Nginx 主配置
│   ├── conf.d/default.conf # 站点配置（反爬/限流/代理）
│   └── ssl/                # SSL 证书目录（可选）
├── login.html              # 登录页
├── admin.html              # 管理后台
├── dashboard.html          # 主看板
├── dashboard_share.html    # 分享版看板
├── dashboard_data.json     # 看板数据
└── robots.txt              # 禁止爬虫
```

## 🔒 安全与反爬机制

| 层级 | 机制 | 说明 |
|------|------|------|
| **Nginx** | 爬虫UA检测 | 拒绝 bot/crawler/spider/python/curl 等UA |
| **Nginx** | 限流 | 每IP 20请求/秒，登录页 5次/分钟 |
| **Nginx** | 并发限制 | 每IP最多10个并发连接 |
| **Nginx** | 安全头 | X-Frame-Options, XSS防护, 内容类型嗅探防护 |
| **Nginx** | 路径保护 | 禁止访问 .git, *.py, server.js 等源码文件 |
| **App** | Helmet | 自动设置 CSP、HSTS、Referrer-Policy 等 |
| **App** | 爬虫频率分析 | 检测异常高频请求（>30/s），自动封禁 |
| **App** | 登录限流 | 每IP每分钟最多10次登录尝试（防暴力破解） |
| **App** | 白名单扩展名 | 仅允许 .html/.json/.css/.js 等公开文件类型 |
| **App** | 源码不打包 | build_data.py、deploy.sh 等不会进入镜像 |

## 🚀 快速部署

### 前置要求

- Docker 20.10+
- Docker Compose 2.0+

### 步骤 1：部署到服务器

将整个项目目录上传到服务器：

```bash
# 在服务器上
cd /path/to/20260618112854
```

### 步骤 2：构建并启动

```bash
# 构建镜像并启动（后台运行）
docker compose up -d --build

# 查看运行状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 步骤 3：验证

```bash
# 访问看板
curl -I http://localhost/login.html

# 应返回 HTTP 200，且包含安全头：
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
```

### 步骤 4：配置域名（可选）

如果你有域名，修改 `nginx/conf.d/default.conf`：

```nginx
server {
    listen 80;
    server_name dashboard.your-domain.com;  # 改为你的域名
    # ... 其余配置不变
}
```

然后重启：

```bash
docker compose restart nginx
```

### 配置 HTTPS（推荐）

1. 将 SSL 证书文件放到 `nginx/ssl/` 目录
2. 修改 `nginx/conf.d/default.conf`，添加443端口监听：

```nginx
server {
    listen 443 ssl http2;
    server_name dashboard.your-domain.com;
    
    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    
    # ... 其余配置与80端口相同
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name dashboard.your-domain.com;
    return 301 https://$host$request_uri;
}
```

3. 更新 `docker-compose.yml` 取消SSL卷挂载的注释，重启服务。

## 🔄 更新数据和账号

### 更新看板数据

```bash
# 1. 在本地运行数据构建脚本
python3 build_data.py

# 2. 将新生成的 dashboard_data.json 上传到服务器
scp dashboard_data.json user@server:/path/to/20260618112854/

# 3. 重新构建并重启
docker compose up -d --build
```

### 管理用户账号

管理员登录后访问 `http://your-domain/admin.html` 即可：
- 新增子账号（用户名、密码、角色、授权大区）
- 修改密码
- 删除账号

> **注意**：账号数据存储在浏览器 localStorage 中。如果用户换了浏览器/设备，管理员需要通过 admin 页面重新创建账号。如需持久化账号数据，需要接入数据库。

## 🛠️ 常用运维命令

```bash
# 查看日志
docker compose logs -f app       # 应用日志
docker compose logs -f nginx     # Nginx 日志

# 重启服务
docker compose restart           # 重启所有服务
docker compose restart app       # 仅重启应用

# 停止服务
docker compose down              # 停止并删除容器

# 完全清理（包括镜像）
docker compose down --rmi all

# 进入容器排查
docker compose exec app sh       # 进入应用容器
docker compose exec nginx sh     # 进入 Nginx 容器

# 查看资源占用
docker stats
```

## 🔍 反爬测试

```bash
# 测试1：正常浏览器UA应返回200
curl -s -o /dev/null -w "%{http_code}" \
  -H "User-Agent: Mozilla/5.0" \
  http://localhost/login.html
# 预期: 200

# 测试2：爬虫UA应返回403
curl -s -o /dev/null -w "%{http_code}" \
  -H "User-Agent: Googlebot" \
  http://localhost/login.html
# 预期: 403

# 测试3：curl UA应返回403
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost/login.html
# 预期: 403

# 测试4：高频请求应被限流（429）
for i in {1..15}; do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "User-Agent: Mozilla/5.0" \
    http://localhost/api/login
done
# 预期: 前几次200，后续429

# 测试5：源码文件应返回404
curl -s -o /dev/null -w "%{http_code}" \
  -H "User-Agent: Mozilla/5.0" \
  http://localhost/server.js
# 预期: 404

# 测试6：Python脚本应返回404
curl -s -o /dev/null -w "%{http_code}" \
  -H "User-Agent: Mozilla/5.0" \
  http://localhost/build_data.py
# 预期: 404
```

## 🏗️ 架构图

```
用户浏览器
    │
    ▼
┌─────────────────────────────────────┐
│  Nginx (反向代理 + 反爬第一层)        │
│  • 限流: 20 req/s per IP            │
│  • 爬虫UA检测 + 403拦截              │
│  • 并发限制: 10 per IP              │
│  • 安全头注入                        │
│  • 禁止访问源码路径                   │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Node.js Express (应用服务器)         │
│  • Helmet 安全头                     │
│  • 登录限流: 10次/分钟               │
│  • 爬虫频率分析（>30/s 封禁）         │
│  • 文件类型白名单                     │
│  • 静态文件服务 (public/)            │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  静态文件 (public/)                  │
│  • login.html, dashboard.html 等    │
│  • dashboard_data.json              │
│  • ❌ build_data.py (不在镜像中)     │
│  • ❌ deploy.sh (不在镜像中)         │
└─────────────────────────────────────┘
```

## ⚠️ 注意事项

1. **账号持久化**：当前版本账号存储在浏览器 localStorage 中，跨设备需管理员重新创建。如需集中管理，可考虑接入 SQLite 或 MongoDB。
2. **数据更新**：每次数据变更需要重新构建 Docker 镜像（`docker compose up -d --build`）。
3. **CDN依赖**：看板依赖 Chart.js CDN（jsdelivr.net），确保服务器能访问外网。
4. **端口**：默认使用 80/443 端口，如被占用可在 `docker-compose.yml` 中修改。
5. **防火墙**：确保服务器防火墙开放 80/443 端口。
