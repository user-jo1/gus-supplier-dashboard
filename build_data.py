import pandas as pd, json

jul_xlsx = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-7月.xlsx'

# 读取现有JSON（5月/6月数据原样保留，不做任何修改）
with open('/Users/mac/CodeBuddy/20260618112854/dashboard_data.json', 'r', encoding='utf-8') as f:
    existing = json.load(f)

def sf(v):
    if pd.isna(v): return 0.0
    return float(v)
def ss(v):
    return str(v).strip() if pd.notna(v) else ''
def get_grade(s):
    if pd.isna(s): return 'D'
    s = float(s)
    return 'A' if s >= 80 else 'B' if s >= 60 else 'C' if s >= 40 else 'D'
def parse_mgr(v):
    if pd.isna(v): return 0
    if isinstance(v, str) and ':' in v:
        try: return 1.0 / float(v.split(':')[0])
        except: return 0
    try: return float(v)
    except: return 0
def normalize_markup(v):
    if pd.isna(v): return 0.0
    s = str(v)
    if s.endswith('%'): return float(s.replace('%', '')) / 100.0
    return float(s)

deduction_cols = ['onsite manager扣分', '响应配合度扣分', '结账配合度扣分', '库内管理扣分', '商业道德扣分', '摸鱼扣分', '不按时发薪扣分']
deduction_labels = ['Onsite Mgr', '响应配合', '结账配合', '库内管理', '商业道德', '摸鱼', '不按时发薪']
regions = ['FL 佛州大区', 'GL 大湖大区', 'MS 中南大区', 'NE 东北大区', 'TX 德州大区', 'WE 美西大区', 'Ground项目部']

# ═══════════════ 仅追加7月数据（5月/6月原样保留） ═══════════════
print('--- 追加7月数据（5月/6月不修改） ---')
df_jul = pd.read_excel(jul_xlsx, sheet_name='数据收集表')
df_jul = df_jul[df_jul['月份'] == '2026年 7月'].copy()
# 列结构变化：'实际使用人数（日均）' 已拆为 '计时使用人数（日均）'+'计件使用人数（日均）'（兼容两种表头）
if '实际使用人数（日均）' not in df_jul.columns:
    df_jul['实际使用人数（日均）'] = df_jul['计时使用人数（日均）'].fillna(0) + df_jul['计件使用人数（日均）'].fillna(0)
# 仓库改名：CNO.G → ONT.G（历史5月/6月数据同步替换，保持跨月对比一致）
for col in ['仓库']:
    df_jul[col] = df_jul[col].replace({'CNO.G': 'ONT.G'})
# 历史月份数据（existing中已有的detail_by_region/detail_by_region_jun）同步改名
for _k in ['detail_by_region', 'detail_by_region_jun']:
    if _k in existing:
        for _region, _rows in existing[_k].items():
            for _r in _rows:
                if _r.get('仓库') == 'CNO.G':
                    _r['仓库'] = 'ONT.G'
for _c in ['people_supplier_chart', 'people_supplier_chart_jun']:
    pass  # 等级统计按大区聚合，不涉及仓库名

# 7月等级：停用/数据不完整=不评级（等级取状态名），其他正常评级
def get_grade_jul(row):
    st = str(row.get('使用状态', '')).strip()
    if st == '停用':
        return '停用'
    if st == '数据不完整':
        return '数据不完整'
    return get_grade(row['总分'])

df_jul['等级'] = df_jul.apply(get_grade_jul, axis=1)
# 7月规则：COI合规='有效'=合规，其余（已过期/未查询到/缺少地址等）=不合规
df_jul['合规标签'] = df_jul['COI合规'].apply(lambda x: '合规' if str(x).strip() == '有效' else '不合规')
df_jul['不合规原因'] = df_jul['COI合规'].apply(lambda x: ss(x) if pd.notna(x) else '')

# 7月 detail_by_region（停用供应商放最下面，不参与排名）
detail_jul = []
for _, row in df_jul.iterrows():
    ded_list = []
    ded_total = 0
    for col, label in zip(deduction_cols, deduction_labels):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0:
            val = int(float(v))
            ded_total += val
            ded_list.append({'项目': label, '扣分': val})
    remark = ss(row.get('备注', ''))
    coi_remark = ss(row.get('COI合规', ''))
    detail_jul.append({
        '大区': row['大区'], '仓库': row['仓库'], '供应商': row['供应商'],
        '等级': row['等级'], '合规标签': row['合规标签'], '不合规原因': row['不合规原因'],
        '使用状态': ss(row.get('使用状态', '')),
        '日均使用人数': round(sf(row['实际使用人数（日均）'])),
        '分拣工时薪': sf(row.get('分拣工时薪', 0)),
        'markup': round(normalize_markup(row.get('分拣工markup', 0)) * 100),
        '分拣工结算价': sf(row.get('分拣工结算价', 0)),
        '报价竞争力得分': round(sf(row['报价竞争力得分'])),
        '派遣满足率得分': round(sf(row['派遣满足率得分'])),
        '考勤准确率得分': round(sf(row['考勤准确率得分'])),
        '人员稳定率得分': round(sf(row['人员稳定率得分'])),
        '定量考核总分': round(sf(row['定量考核总分'])),
        '总分': round(sf(row['总分'])),
        '报价竞争力': round(sf(row['报价竞争力']), 4),
        '派遣满足率': round(sf(row['派遣满足率']), 4),
        '考勤准确率': round(sf(row['考勤准确率']), 4),
        '人员稳定率': round(sf(row['人员稳定率']), 4),
        'onsite_manager_管理幅宽': parse_mgr(row.get('Onsite-manager管理幅宽', 0)),
        '扣分明细列表': ded_list,
        '扣分总计': ded_total,
        '备注': remark,
        'coi备注': coi_remark,
        '报价竞争力_pct': round(sf(row['报价竞争力']) * 100, 1),
        '派遣满足率_pct': round(sf(row['派遣满足率']) * 100, 1),
        '考勤准确率_pct': round(sf(row['考勤准确率']) * 100, 1),
        '人员稳定率_pct': round(sf(row['人员稳定率']) * 100, 1),
    })

# 排序：正常/新增按总分降序 → 停用/数据不完整放最下面（不参与排名）
BOTTOM_STATES = ('停用', '数据不完整')
detail_jul.sort(key=lambda r: (1 if r['使用状态'] in BOTTOM_STATES else 0, -r['总分']))

detail_by_region_jul = {}
for region in regions:
    detail_by_region_jul[region] = [d for d in detail_jul if d['大区'] == region]

# 7月 people_supplier_chart（按标准区域顺序，停用/数据不完整不参与等级统计）
region_supplier_jul = []
for region in regions:
    rdf = df_jul[df_jul['大区'] == region]
    active = rdf[~rdf['使用状态'].isin(BOTTOM_STATES)]
    region_supplier_jul.append({
        'region': region,
        'daily_people': int(rdf['实际使用人数（日均）'].sum()),
        'total_suppliers': int(active['供应商'].nunique()),
        'compliant': int((active['合规标签'] == '合规').sum()),
        'noncompliant': int((active['合规标签'] == '不合规').sum()),
        'a_count': int((active['等级'] == 'A').sum()), 'b_count': int((active['等级'] == 'B').sum()),
        'c_count': int((active['等级'] == 'C').sum()), 'd_count': int((active['等级'] == 'D').sum()),
    })

# 7月KPI汇总（停用/数据不完整不参与统计）
jul_total_ppl = int(df_jul['实际使用人数（日均）'].sum())
jul_total_supp = int(df_jul[~df_jul['使用状态'].isin(BOTTOM_STATES)]['供应商'].nunique())
jul_total_records = len(df_jul)
jul_grades = df_jul[~df_jul['使用状态'].isin(BOTTOM_STATES)].groupby('供应商')['总分'].max().apply(get_grade)
jul_a = int((jul_grades == 'A').sum())
jul_d = int((jul_grades == 'D').sum())
jul_a_rec = int((df_jul['等级'] == 'A').sum())
jul_d_rec = int((df_jul['等级'] == 'D').sum())
jul_ncomp = int(df_jul[(df_jul['合规标签'] == '不合规') & (~df_jul['使用状态'].isin(BOTTOM_STATES))]['供应商'].nunique())

# 只新增7月字段，不修改任何5月/6月已有字段
existing['detail_by_region_jul'] = detail_by_region_jul
existing['people_supplier_chart_jul'] = region_supplier_jul
kpi = existing['kpi']
kpi.update({
    'jul_total_supplier_count': jul_total_supp,
    'jul_total_records': jul_total_records,
    'jul_a_suppliers': jul_a,
    'jul_a_pct': f'{jul_a_rec}/{jul_total_records}',
    'jul_d_suppliers': jul_d,
    'jul_d_pct': f'{jul_d_rec}/{jul_total_records}',
    'jul_coi_noncompliant': jul_ncomp,
    'jul_coi_pct': f'{jul_ncomp}/{jul_total_supp}',
})

# ═══════════════ 7月汇总看板数据（成本图表/KPI/供应商汇总/跨区域） ═══════════════
print('--- 7月汇总看板数据 ---')

# 7月汇总数据（汇总数据 sheet）
df_sum = pd.read_excel(jul_xlsx, sheet_name='汇总数据')
df_sum = df_sum[df_sum['三级组织'].notna() & (df_sum['三级组织'] != '总计') & (df_sum['三级组织'] != '计时+计件总人数')].copy()
cost_col = '总成本（计时）-不含正工挂靠、司机'
if cost_col in df_sum.columns:
    df_sum.rename(columns={cost_col: '总成本（计时）'}, inplace=True)

# 7月 KPI（汇总口径）
jul_total_ppl_sum = round(sf(df_sum['计时人数（日均）'].sum()) + sf(df_sum['计件人数（日均）'].sum()))
jul_total_time_ppl = round(sf(df_sum['计时人数（日均）'].sum()))
jul_total_piece_ppl = round(sf(df_sum['计件人数（日均）'].sum()))
jul_total_hours_sum = round(sf(df_sum['总工时数'].sum()))
jul_total_cost_sum = round(sf(df_sum['总成本'].sum()))

# 7月 cost_chart（强制按标准区域顺序排列，与5月/6月保持一致）
jul_cost_chart = []
for region in regions:
    row = df_sum[df_sum['三级组织'] == region]
    if row.empty: continue
    row = row.iloc[0]
    daily_ppl = round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）']))
    jul_cost_chart.append({
        'region': region, 'time_cost': sf(row['总成本（计时）']),
        'piece_cost': sf(row['总成本（计件）']), 'total_cost': sf(row['总成本']),
        'total_hours': sf(row['总工时数']), 'daily_people': daily_ppl,
    })

# ── 7月供应商数据汇总（总览行 + wh_details 仓库卡片）──
# 供应商+仓库级聚合
supplier_wh_jul = df_jul.groupby(['大区', '供应商', '仓库']).agg(
    日均人数=('实际使用人数（日均）', 'sum'), 总分=('总分', 'max'),
    等级=('等级', 'first'), 合规标签=('合规标签', 'first'),
    不合规原因=('不合规原因', 'first'),
    分拣工时薪=('分拣工时薪', 'mean'), 分拣工markup=('分拣工markup', 'mean'),
    分拣工结算价=('分拣工结算价', 'mean'),
    报价竞争力得分=('报价竞争力得分', 'mean'), 派遣满足率得分=('派遣满足率得分', 'mean'),
    考勤准确率得分=('考勤准确率得分', 'mean'), 人员稳定率得分=('人员稳定率得分', 'mean'),
).reset_index()

# 人数占比（按大区）
region_daily_totals = supplier_wh_jul.groupby('大区')['日均人数'].sum().to_dict()
supplier_wh_jul['人数占比'] = supplier_wh_jul.apply(lambda r: sf(r['日均人数']) / region_daily_totals.get(r['大区'], 1), axis=1)

# 得分分析（低分维度 + 扣分）
def build_analysis_jul(row):
    parts = []
    scores = {'报价竞争力': round(sf(row['报价竞争力得分'])), '派遣满足率': round(sf(row['派遣满足率得分'])),
              '考勤准确率': round(sf(row['考勤准确率得分'])), '人员稳定率': round(sf(row['人员稳定率得分']))}
    low_dims = [f'{d}偏低({v}分)' for d, v in scores.items() if v < 60]
    if low_dims: parts.append('、'.join(low_dims))
    ded_parts = []
    for col, label in zip(deduction_cols, deduction_labels):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0: ded_parts.append(f'{label}({int(float(v))}分)')
    if ded_parts: parts.append('扣分：' + '、'.join(ded_parts))
    if not parts: return '整体均衡'
    return '；'.join(parts)

supplier_wh_jul['得分分析'] = supplier_wh_jul.apply(build_analysis_jul, axis=1)

# 组装 supplier_table（按 大区+供应商 分组，区域按标准顺序）
supplier_table_jul = []
# 按 regions 顺序遍历，确保排序一致
region_order_map = {r: i for i, r in enumerate(regions)}
supplier_wh_jul['_sort'] = supplier_wh_jul['大区'].map(region_order_map)
for (region, supplier), grp in supplier_wh_jul.sort_values('_sort').groupby(['大区', '供应商']):
    wh_details = []
    for _, w in grp.iterrows():
        wh_details.append({
            '仓库': w['仓库'], '日均人数': round(sf(w['日均人数'])),
            '人数占比': round(sf(w['人数占比']) * 100, 1),
            '时薪': round(sf(w['分拣工时薪']), 1),
            'markup': round(sf(w['分拣工markup']) * 100),
            '结算价': round(sf(w['分拣工结算价']), 1),
            '总分': round(sf(w['总分'])), '等级': w['等级'],
            '得分分析': w['得分分析'],
            '合规': w['合规标签'], '不合规原因': w['不合规原因'] if w['合规标签'] == '不合规' else '',
            '报价竞争力得分': round(sf(w['报价竞争力得分'])),
            '派遣满足率得分': round(sf(w['派遣满足率得分'])),
            '考勤准确率得分': round(sf(w['考勤准确率得分'])),
            '人员稳定率得分': round(sf(w['人员稳定率得分'])),
        })
    total_ppl = int(grp['日均人数'].sum())
    region_total = region_daily_totals.get(region, 1)
    # 等级：多仓库用逗号连接（按总分排序）
    grades = sorted(set(wh_details[x]['等级'] for x in range(len(wh_details))), key=lambda g: 'ABCD'.find(g[0]) if g[0] in 'ABCD' else 99)
    has_nc = any(wd['合规'] == '不合规' for wd in wh_details)
    supplier_table_jul.append({
        '大区': region, '供应商': supplier,
        '仓库': ', '.join(grp['仓库'].unique()),
        '日均使用人数': total_ppl,
        '人数占比': round(total_ppl / region_total * 100, 1),
        '合规': '不合规' if has_nc else '合规',
        '等级': ','.join(grades),
        'wh_details': wh_details,
    })
# 按日均人数降序
supplier_table_jul.sort(key=lambda r: -r['日均使用人数'])

# ── 7月跨区域对比（同一供应商出现在多个大区）──
multi_region = df_jul.groupby('供应商')['大区'].nunique()
multi_supps = multi_region[multi_region > 1].index.tolist()
cross_region_jul = []
for supp in multi_supps:
    sdf = df_jul[df_jul['供应商'] == supp].groupby('大区').agg(
        日均使用人数=('实际使用人数（日均）', 'sum'), 总分=('总分', 'max'),
        等级=('等级', 'first'), 分拣工时薪=('分拣工时薪', 'mean'),
        分拣工markup=('分拣工markup', 'mean'), 分拣工结算价=('分拣工结算价', 'mean'),
    ).reset_index()
    for _, row in sdf.iterrows():
        cross_region_jul.append({
            '供应商': supp, '大区': row['大区'],
            '日均使用人数': round(sf(row['日均使用人数'])),
            '总分': round(sf(row['总分'])), '等级': row['等级'],
            '时薪': round(sf(row['分拣工时薪']), 1),
            'markup': round(sf(row['分拣工markup']) * 100),
            '结算价': round(sf(row['分拣工结算价']), 1),
        })

# 更新到 JSON（汇总看板数据覆盖为最新7月版本）
existing['cost_chart_jul'] = jul_cost_chart
existing['supplier_table'] = supplier_table_jul
existing['cross_region'] = cross_region_jul
kpi = existing['kpi']
kpi.update({
    'jul_daily_avg_people': jul_total_ppl_sum,
    'jul_daily_avg_people_time': jul_total_time_ppl,
    'jul_daily_avg_people_piece': jul_total_piece_ppl,
    'jul_daily_avg_trips': round(jul_total_hours_sum / 22.0 / 8.0),
    'jul_total_hours': jul_total_hours_sum,
    'jul_total_cost': jul_total_cost_sum,
})

# months 追加7月（保留5月/6月）
months = existing.get('months', [])
if '2026年7月' not in months:
    months.append('2026年7月')
existing['months'] = months

with open('/Users/mac/CodeBuddy/20260618112854/dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(existing, f, ensure_ascii=False, indent=2)

print(f'7月: 供应商={jul_total_supp}家 记录={jul_total_records}条 停用={len(df_jul[df_jul["使用状态"]=="停用"])}条')
print(f'7月汇总: 人数={jul_total_ppl_sum} 工时={jul_total_hours_sum:,} 成本=${jul_total_cost_sum:,}')
print(f'supplier_table_jul={len(supplier_table_jul)}条 cross_region_jul={len(cross_region_jul)}条')
print(f'months = {existing["months"]}')
