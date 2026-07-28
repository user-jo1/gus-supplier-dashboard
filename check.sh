#!/bin/bash
# GUS 看板自检脚本 - 部署前必过
cd /Users/mac/CodeBuddy/20260618112854
echo "═══════════════════════════════════════"
echo "🔍 GUS 看板自检"
echo "═══════════════════════════════════════"

PASS=0
FAIL=0
check() {
  if [ $? -eq 0 ]; then
    echo "  ✅ $1"
    PASS=$((PASS+1))
  else
    echo "  ❌ $1"
    FAIL=$((FAIL+1))
  fi
}

# 1. 服务器运行
echo ""
echo "1. 服务器状态"
lsof -i :8899 | grep -q LISTEN
check "HTTP服务器运行(8899端口)"

# 2. JSON数据
echo ""
echo "2. 数据检查"
python3 -c "
import json, math
with open('dashboard_data.json') as f:
    data = json.load(f)
kpi = data.get('kpi',{})
print(f'  日均人数={kpi.get(\"daily_avg_people\",\"?\")} 供应商={kpi.get(\"total_supplier_count\",\"?\")}')
print(f'  5月记录={sum(len(v) for v in data.get(\"detail_by_region\",{}).values())}')
print(f'  6月记录={sum(len(v) for v in data.get(\"detail_by_region_jun\",{}).values())}')
# NaN
def check_nan(obj, path=''):
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            print(f'  ❌ NaN at {path}')
            return False
    elif isinstance(obj, dict):
        for k,v in obj.items():
            if not check_nan(v, f'{path}.{k}'): return False
    elif isinstance(obj, list):
        for i,v in enumerate(obj):
            if not check_nan(v, f'{path}[{i}]'): return False
    return True
if not check_nan(data): exit(1)
" 2>&1
check "JSON数据完整无NaN"

# 3. HTML语法
echo ""
echo "3. HTML语法检查"
python3 -c "
with open('dashboard.html') as f: d=f.read()
with open('login.html') as f: l=f.read()
with open('admin.html') as f: a=f.read()
db=d.count('{')-d.count('}')
lb=l.count('{')-l.count('}')
ab=a.count('{')-a.count('}')
print(f'  dashboard.html braces diff={db}')
print(f'  login.html braces diff={lb}')
print(f'  admin.html braces diff={ab}')
if db!=0 or lb!=0 or ab!=0: exit(1)
" 2>&1
check "HTML括号平衡"

# 4. HTTP访问
echo ""
echo "4. HTTP测试"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8899/login.html | grep -q 200
check "login.html返回200"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8899/dashboard.html | grep -q 200
check "dashboard.html返回200"
curl -s -o /dev/null -w '%{http_code}' http://localhost:8899/dashboard_data.json | grep -q 200
check "dashboard_data.json返回200"

# 5. JS关键函数
echo ""
echo "5. JS逻辑检查"
python3 -c "
with open('login.html') as f: l=f.read()
with open('dashboard.html') as f: d=f.read()
checks = [
    ('sha256函数', 'function sha256' in l),
    ('哈希比对', 'u.hash===inputHash' in l),
    ('DEFAULT_USERS', 'DEFAULT_USERS' in l),
    ('USERS_VERSION=4', 'USERS_VERSION=4' in l),
    ('权限校验', 'sessionStorage.getItem' in d),
    ('雷达图渲染', 'toggleRegDet' in d),
    ('renderRegionContent', 'renderRegionContent' in d),
    ('switchMonth', 'switchMonth' in d),
    ('no-cache meta', 'no-cache' in l),
]
for name, ok in checks:
    print(f'  {\"✅\" if ok else \"❌\"} {name}')
    if not ok: exit(1)
" 2>&1
check "核心JS函数"

# 6. 密码哈希验证
echo ""
echo "6. 密码验证"
python3 -c "
import hashlib, re
with open('login.html') as f: html=f.read()
users=[('admin','gus2026'),('fl','gusfl2026'),('gl','glgl2026'),
       ('ms','msgus2026'),('ne','nenene2026'),('tx','gustx26'),
       ('we','guswe2626'),('ground','og2026'),('ADMIN','ADMIN2026')]
ok=0
for u,p in users:
    h=hashlib.sha256(p.encode()).hexdigest()
    if h in html: ok+=1
    else: print(f'  ❌ {u} 哈希不匹配')
print(f'  验证通过: {ok}/{len(users)}')
if ok!=len(users): exit(1)
" 2>&1
check "密码哈希匹配"

# 结果
echo ""
echo "═══════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
  echo "🎉 全部通过！可以安全部署 ($PASS/$((PASS+FAIL)))"
  echo ""
  echo "本地: http://localhost:8899/login.html"
  echo "公网: https://user-jo1.github.io/gus-supplier-dashboard/"
else
  echo "❌ $FAIL 项失败！请修复后再部署"
fi
echo "═══════════════════════════════════════"
exit $FAIL
