import json, re
with open('/Users/mac/CodeBuddy/20260618112854/dashboard_peaksupply.html', 'r') as f:
    c = f.read()

# 1. 检查meta标题
m = re.search(r'"title":\s*"([^"]+)"', c)
print('meta title:', m.group(1) if m else '未找到')

# 2. 检查D对象JSON
a2 = c.find('D={')
s2 = a2 + 2
e2 = c.find(';init();', s2)
try:
    d = json.loads(c[s2:e2])
    print('\nD对象JSON有效')
    print('meta:', d.get('meta', {}).get('title'))
    print('warehouse_550:', len(d['warehouse_550']), '条')
    w0 = d['warehouse_550'][0]
    print('warehouse_550[0]:', json.dumps(w0, ensure_ascii=False))
    
    # 检查是否有6月字段残留
    has_6jun = '6月在岗人数' in json.dumps(d, ensure_ascii=False)
    print('含6月在岗字段:', has_6jun)
except Exception as ex:
    print('JSON失败:', ex)

# 3. 检查页面文本中的6月引用
print('\n=== 页面中"6月"出现次数:', c.count('6月'))
print('=== 页面中"7月"出现次数:', c.count('7月'))
