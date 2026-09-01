import re
with open('/Users/mac/CodeBuddy/20260618112854/dashboard_peaksupply.html', 'r') as f:
    c = f.read()

# 检查图表数据源 - 人力缺口对比图
idx = c.find("550w · 7月实际使用")
print('550w图表7月:', idx > 0)
idx2 = c.find("660w · 7月实际使用")
print('660w图表7月:', idx2 > 0)

# 检查 renderDual 大数
idx3 = c.find("s+w['7月在岗人数']")
print('renderDual用7月在岗:', idx3 > 0)

# 检查是否有6月图表残留
print('\n"6月实际使用"出现:', c.count("6月实际使用"))
print('"6月在岗总人数"出现:', c.count("6月在岗总人数"))

# 检查总览表头
print('\n"6月在岗"表头残留:', c.count("'<th>6月在岗</th>'"))
print('"6月 / 7月"表头:', c.count("6月 / 7月"))

# 检查图表函数中的历史数据
# 查看图表绘制部分
idx_c = c.find('function charts')
if idx_c < 0: idx_c = c.find('function renderCharts')
if idx_c < 0: idx_c = c.find('function chartAll')
print('\n图表函数位置:', idx_c)
if idx_c > 0:
    seg = c[idx_c:idx_c+500]
    print(seg[:300])
