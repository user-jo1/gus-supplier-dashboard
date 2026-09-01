#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUS 劳务供应商管理看板 · 简易后端
- 静态文件服务（支持 dashboard.html / dashboard_peaksupply.html / dashboard_site.html 等）
- 站点劳务缺口登记：POST /api/site-save  → 追加到 site_data.json
- 记录列表：      GET  /api/site-records → 读取 site_data.json
- 删除记录：      POST /api/site-delete  → 按索引删除

启动：python3 server.py  (默认 8899 端口)
"""
import os
import json
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, 'site_data.json')
MOBILIZE_FILE = os.path.join(BASE_DIR, 'mobilize_data.json')
PORT = 8899

def load_json(file, default):
    if not os.path.exists(file):
        return default
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_records():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_records(records):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def _send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0) or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/site-records':
            self._send_json({'ok': True, 'records': load_records()})
            return
        if parsed.path == '/api/mobilize-records':
            recs = load_json(MOBILIZE_FILE, [])
            self._send_json({'ok': True, 'records': recs})
            return
        # 兼容旧方式启动时缺失 index 的情况
        if parsed.path in ('/', ''):
            self.path = '/dashboard.html'
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/site-save':
            try:
                body = self._read_body()
                records = load_records()
                # 最多保留最近 100 条
                records.append({'time': body.get('time', time.strftime('%Y-%m-%d %H:%M:%S')), 'rows': body.get('rows', [])})
                if len(records) > 100:
                    records = records[-100:]
                save_records(records)
                self._send_json({'ok': True, 'total': len(records)})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
            return

        if parsed.path == '/api/site-delete':
            try:
                body = self._read_body()
                idx = int(body.get('idx', -1))
                records = load_records()
                if 0 <= idx < len(records):
                    records.pop(idx)
                    save_records(records)
                    self._send_json({'ok': True, 'total': len(records)})
                else:
                    self._send_json({'ok': False, 'error': '索引越界'}, 400)
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
            return

        if parsed.path == '/api/mobilize-save':
            try:
                body = self._read_body()
                recs = load_json(MOBILIZE_FILE, [])
                recs.append({'time': body.get('time', time.strftime('%Y-%m-%d %H:%M:%S')), 'ratios': body.get('ratios', {})})
                if len(recs) > 100:
                    recs = recs[-100:]
                save_json(MOBILIZE_FILE, recs)
                self._send_json({'ok': True, 'time': body.get('time', ''), 'total': len(recs)})
            except Exception as e:
                self._send_json({'ok': False, 'error': str(e)}, 500)
            return

        self._send_json({'ok': False, 'error': '接口不存在'}, 404)

    def log_message(self, fmt, *args):
        print('[%s] %s' % (self.log_date_time_string(), fmt % args))

if __name__ == '__main__':
    print('=' * 60)
    print('GUS 看板后端启动：')
    print('  静态目录 :', BASE_DIR)
    print('  数据文件 :', DATA_FILE)
    print('  访问地址 : http://localhost:%d/dashboard.html' % PORT)
    print('  保存接口 : POST /api/site-save')
    print('=' * 60)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
        server.server_close()
