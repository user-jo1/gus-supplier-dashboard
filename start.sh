#!/bin/bash
# GUS 劳务供应商管理看板 - 一键启动脚本
# 用法: ./start.sh   (或 bash start.sh)
# 启动后访问: http://localhost:8899/login.html
#
# 重要: 必须使用 --directory 参数强制指定项目目录启动！
# 原因: 曾多次出现服务器从错误目录启动导致所有页面404，
#       --directory 不依赖进程工作目录，一劳永逸。

PYTHON3="/usr/bin/python3"
CURL="/usr/bin/curl"
LSOF="/usr/sbin/lsof"
NOHUP="/usr/bin/nohup"
KILL="/bin/kill"
PORT=8899
DIR="/Users/mac/CodeBuddy/20260618112854"

# 检查端口是否已被占用
if $LSOF -i :$PORT >/dev/null 2>&1; then
  # 测试是否服务正确目录
  if $CURL -s -o /dev/null "http://localhost:$PORT/login.html"; then
    echo "OK 服务器已在运行: http://localhost:$PORT/login.html"
    exit 0
  else
    # 端口被占用但服务异常（工作目录不对），杀掉重启
    echo "端口被异常进程占用（可能服务错误目录），正在重启..."
    $LSOF -ti :$PORT | xargs $KILL -9 2>/dev/null
  fi
fi

# 用 --directory 强制指定项目目录启动（不依赖 cwd）
$NOHUP $PYTHON3 -m http.server $PORT --bind 0.0.0.0 --directory "$DIR" > /tmp/gus_http_server.log 2>&1 &
/usr/bin/python3 -c "import time;time.sleep(2)"

# 验证启动成功
if $CURL -s -o /dev/null "http://localhost:$PORT/login.html"; then
  echo "OK GUS 看板服务器已启动"
  echo "登录入口: http://localhost:$PORT/login.html"
  echo "管理入口: http://localhost:$PORT/admin.html"
else
  echo "启动失败，请检查 /tmp/gus_http_server.log"
  /usr/bin/cat /tmp/gus_http_server.log 2>/dev/null
fi
