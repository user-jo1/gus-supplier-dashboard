# ============================================================
# GUS 劳务供应商管理看板 - Docker 多阶段构建
# 
# 设计思路：
#   - 阶段1：复制源码 → 生产构建（压缩/混淆可选）
#   - 阶段2：生产运行时（仅包含必要的静态文件 + Node.js服务）
#   - 用户访问到的只有 public/ 中的 HTML/JSON 文件
#   - 源码（build_data.py、deploy.sh等）不会出现在最终镜像中
# ============================================================

# ── 阶段 1：构建阶段 ──
FROM node:20-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache python3 bash

WORKDIR /build

# 复制服务器依赖文件
COPY server/package.json server/package-lock.json* ./

# 安装生产依赖（仅生产依赖，减少镜像体积）
RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev

# ── 阶段 2：生产运行时 ──
FROM node:20-alpine

# 安全加固：创建非root用户
RUN addgroup -g 1001 -S gusapp && \
    adduser -u 1001 -S gusapp -G gusapp

# 安装 dumb-init 以正确处理信号
RUN apk add --no-cache dumb-init tini

# 设置工作目录
WORKDIR /app

# 从构建阶段复制 node_modules
COPY --from=builder /build/node_modules ./node_modules

# 复制服务器代码（server.js + package.json）
COPY server/server.js ./server.js
COPY server/package.json ./package.json

# 创建 public/ 目录并复制公开的静态文件
# 注意：这里只复制HTML文件、JSON数据文件、robots.txt
# 不复制 Python源码、Shell脚本、.git等
RUN mkdir -p public

COPY login.html ./public/
COPY index.html ./public/
COPY admin.html ./public/
COPY dashboard.html ./public/
COPY dashboard_share.html ./public/
COPY dashboard_data.json ./public/
COPY robots.txt ./public/

# 设置正确的文件权限（只读）
RUN chown -R gusapp:gusapp /app && \
    chmod -R 555 /app/public && \
    chmod 555 /app/server.js && \
    chmod 555 /app/package.json && \
    chmod 555 /app/node_modules -R

# 切换到非root用户
USER gusapp

# 暴露端口
EXPOSE 3000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:3000/api/health || exit 1

# 环境变量
ENV NODE_ENV=production
ENV PORT=3000

# 使用 dumb-init 启动（正确处理 SIGTERM/SIGINT）
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]
