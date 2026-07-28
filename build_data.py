import pandas as pd
import json
import numpy as np

# ─── 读取数据源 ───
may_xlsx = '/Users/mac/Downloads/GUS_劳务供应商考核数据-2.xlsx'
jun_xlsx = '/Users/mac/Desktop/GF_HR/01-劳务工:供应商管理/GUS_劳务供应商考核数据-6月xlsx.xlsx'

# 读取已有JSON（保留5月数据）
with open('/Users/mac/CodeBuddy/20260618112854/dashboard_data.json', 'r', encoding='utf-8') as f:
    _existing_data = json.load(f)
_may_kpi = _existing_data.get('kpi', {})
_may_cost_chart = _existing_data.get('cost_chart', [])
_may_people_chart = _existing_data.get('people_supplier_chart', [])

# 尝试读取5月原始Excel
_may_available = True
try:
    df_may = pd.read_excel(may_xlsx, sheet_name='数据总表')
    df_summary_may = pd.read_excel(may_xlsx, sheet_name='人数、人次、出勤工时、总成本')
    df_insurance_may = pd.read_excel(may_xlsx, sheet_name='保险合规进度')
    df_cost_detail_may = pd.read_excel(may_xlsx, sheet_name='供应商成本明细')
except:
    _may_available = False
    df_may = pd.DataFrame()
    df_summary_may = pd.DataFrame()
    df_insurance_may = pd.DataFrame()
    df_cost_detail_may = pd.DataFrame()

df_jun = pd.read_excel(jun_xlsx, sheet_name='数据收集表')
df_jun = df_jun[df_jun['月份'] == '2026年 6月'].copy()

# 6月汇总数据
df_summary_jun = pd.read_excel(jun_xlsx, sheet_name='汇总数据')
# 过滤掉总计行和NaN行
df_summary_jun = df_summary_jun[df_summary_jun['三级组织'].notna() & (df_summary_jun['三级组织'] != '总计') & (df_summary_jun['三级组织'] != '计时+计件总人数')]
# 重命名成本列
cost_col = '总成本（计时）-不含正工挂靠、司机'
if cost_col in df_summary_jun.columns:
    df_summary_jun.rename(columns={cost_col: '总成本（计时）'}, inplace=True)

# ─── 通用工具函数 ───
def sf(v):
    if pd.isna(v): return 0.0
    return float(v)
def si(v):
    if pd.isna(v): return 0
    return int(float(v))
def ss(v):
    if pd.isna(v): return ''
    return str(v).strip()
def normalize_markup(v):
    if pd.isna(v): return 0.0
    s = str(v)
    if s.endswith('%'): return float(s.replace('%', '')) / 100.0
    return float(s)
def get_grade(score):
    if pd.isna(score): return 'D'
    s = float(score)
    if s >= 80: return 'A'
    elif s >= 60: return 'B'
    elif s >= 40: return 'C'
    else: return 'D'

def parse_mgr(v):
    """解析Onsite-manager管理幅宽: 可能是 '19:1', 0.05, 或 NaN"""
    if pd.isna(v): return 0
    if isinstance(v, str) and ':' in v:
        parts = v.split(':')
        try: return 1.0 / float(parts[0])
        except: return 0
    try: return float(v)
    except: return 0

deduction_cols_may = ['onsite manager扣分', '响应配合度扣分', '结账配合度扣分', '库内管理扣分', '商业道德扣分', '擅自离岗扣分', '不按时发薪扣分']
deduction_labels_may = ['Onsite Mgr', '响应配合', '结账配合', '库内管理', '商业道德', '擅自离岗', '不按时发薪']

deduction_cols_jun = ['onsite manager扣分', '响应配合度扣分', '结账配合度扣分', '库内管理扣分', '商业道德扣分', '摸鱼扣分', '不按时发薪扣分']
deduction_labels_jun = ['Onsite Mgr', '响应配合', '结账配合', '库内管理', '商业道德', '摸鱼', '不按时发薪']

# ─── 处理5月数据 ───
def process_month(df, df_summary, deduction_cols, deduction_labels, month_label, cost_detail_df=None):
    df['等级'] = df['总分'].apply(get_grade)
    # 合规判断：5月用合规情况列，6月用COI合规备注列
    if '合规情况' in df.columns:
        df['合规标签'] = df['合规情况'].apply(lambda x: '不合规' if not str(x).endswith('合规') else '合规')
        df['不合规原因'] = df.apply(lambda r: str(r['合规情况']).replace('COI不合规，', '').strip() if r['合规标签'] == '不合规' else '', axis=1)
    else:
        # 6月：COI合规非空 = 不合规
        df['合规标签'] = df['COI合规'].apply(lambda x: '不合规' if pd.notna(x) and str(x).strip() != '' else '合规')
        df['不合规原因'] = df['COI合规'].apply(lambda x: ss(x) if pd.notna(x) else '')
    df['分拣工markup_num'] = 0.0  # 6月没有markup数据

    df_summary_data = df_summary[df_summary['三级组织'] != '总计'].copy()
    df_summary_data = df_summary_data[df_summary_data['三级组织'].notna()]

    daily_avg_people_time = sf(df_summary_data['计时人数（日均）'].sum())
    daily_avg_people_piece = sf(df_summary_data['计件人数（日均）'].sum())
    daily_avg_people = round(daily_avg_people_time + daily_avg_people_piece)
    total_hours = sf(df_summary_data['总工时数'].sum())
    total_cost = sf(df_summary_data['总成本'].sum())

    all_suppliers = df['供应商'].unique()
    total_supplier_count = len(all_suppliers)
    total_records = len(df)
    a_records = int((df['等级'] == 'A').sum())
    d_records = int((df['等级'] == 'D').sum())
    supplier_grades = df.groupby('供应商')['总分'].max().apply(get_grade)
    a_suppliers = int((supplier_grades == 'A').sum())
    d_suppliers = int((supplier_grades == 'D').sum())
    noncompliant_suppliers = int(df[df['合规标签'] == '不合规']['供应商'].nunique())

    # Detail records
    detail = []
    for _, row in df.iterrows():
        ded_detail_list = []
        ded_total = 0
        for col, label in zip(deduction_cols, deduction_labels):
            v = row.get(col)
            if pd.notna(v) and float(v) != 0:
                val = int(float(v))
                ded_total += val
                ded_detail_list.append({'项目': label, '扣分': val})
        # 备注：只取备注列，不合规原因取COI合规列
        remark = ss(row.get('备注', ''))
        coi_remark = ss(row.get('COI合规', ''))
        if remark and coi_remark:
            remark = remark + '；COI不合规：' + coi_remark
        elif coi_remark:
            remark = 'COI：' + coi_remark

        detail.append({
            '大区': row['大区'], '仓库': row['仓库'], '供应商': row['供应商'],
            '等级': row['等级'], '合规标签': row['合规标签'], '不合规原因': row['不合规原因'],
            '日均使用人数': round(sf(row['实际使用人数（日均）'])),
            '分拣工时薪': round(sf(row.get('分拣工时薪', 0)), 1),
            'markup': round(sf(row.get('分拣工markup_num', 0)) * 100),
            '分拣工结算价': round(sf(row.get('分拣工结算价', 0)), 1),
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
            '扣分明细列表': ded_detail_list,
            '扣分总计': ded_total,
            '备注': remark,
            'coi备注': coi_remark,
            '报价竞争力_pct': round(sf(row['报价竞争力']) * 100, 1),
            '派遣满足率_pct': round(sf(row['派遣满足率']) * 100, 1),
            '考勤准确率_pct': round(sf(row['考勤准确率']) * 100, 1),
            '人员稳定率_pct': round(sf(row['人员稳定率']) * 100, 1),
        })

    regions_order = ['FL 佛州大区', 'GL 大湖大区', 'MS 中南大区', 'NE 东北大区', 'TX 德州大区', 'WE 美西大区', 'Ground项目部']
    detail_by_region = {}
    for region in regions_order:
        detail_by_region[region] = [d for d in detail if d['大区'] == region]

    # Region supplier data
    region_supplier_data = []
    for _, row in df_summary_data.iterrows():
        region_name = row['三级组织']
        rdf = df[df['大区'] == region_name]
        daily_ppl = round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）']))
        region_supplier_data.append({
            'region': region_name, 'daily_people': daily_ppl,
            'total_hours': sf(row['总工时数']),
            'total_suppliers': int(rdf['供应商'].nunique()),
            'compliant': int((rdf['合规标签'] == '合规').sum()),
            'noncompliant': int((rdf['合规标签'] == '不合规').sum()),
            'a_count': int((rdf['等级'] == 'A').sum()), 'b_count': int((rdf['等级'] == 'B').sum()),
            'c_count': int((rdf['等级'] == 'C').sum()), 'd_count': int((rdf['等级'] == 'D').sum()),
        })

    return {
        'kpi': {
            'daily_avg_people': round(daily_avg_people),
            'daily_avg_people_time': round(daily_avg_people_time),
            'daily_avg_people_piece': round(daily_avg_people_piece),
            'total_hours': round(total_hours), 'total_cost': round(total_cost),
            'total_supplier_count': total_supplier_count, 'total_records': total_records,
            'a_suppliers': a_suppliers, 'a_pct': f'{a_records}/{total_records}',
            'd_suppliers': d_suppliers, 'd_pct': f'{d_records}/{total_records}',
            'coi_noncompliant': noncompliant_suppliers,
            'coi_pct': f'{noncompliant_suppliers}/{total_supplier_count}',
        },
        'detail_by_region': detail_by_region,
        'people_supplier_chart': region_supplier_data,
        'regions': regions_order,
        'month': month_label,
    }

# ─── 构建输出 ───
may_data = process_month(df_may, df_summary_may, deduction_cols_may, deduction_labels_may, '2026年5月', df_cost_detail_may)
jun_data = process_month(df_jun, df_summary_may, deduction_cols_jun, deduction_labels_jun, '2026年6月')

# 合并输出：5月为主（保持原有KPI和图表），6月为新增明细
# 5月的其他数据（cost_chart, supplier_table, cross_region, insurance等）保持不变
# 先按原来的方式生成5月完整数据

# 重新生成5月完整输出（保持原有逻辑）
# ─── 5月：供应商表、跨区域、成本分析等 ───
df = df_may.copy()
df['等级'] = df['总分'].apply(get_grade)
df['合规标签'] = df['合规情况'].apply(lambda x: '不合规' if not str(x).endswith('合规') else '合规')
df['不合规原因'] = df.apply(lambda r: str(r['合规情况']).replace('COI不合规，', '').strip() if r['合规标签'] == '不合规' else '', axis=1)
df['分拣工markup_num'] = df['分拣工markup'].apply(normalize_markup)

df_summary_data = df_summary_may[df_summary_may['三级组织'] != '总计'].copy()
df_summary_data = df_summary_data[df_summary_data['三级组织'].notna()]

# KPI
daily_avg_people_time = sf(df_summary_data['计时人数（日均）'].sum())
daily_avg_people_piece = sf(df_summary_data['计件人数（日均）'].sum())
daily_avg_people = round(daily_avg_people_time + daily_avg_people_piece)
total_hours = sf(df_summary_data['总工时数'].sum())
total_cost = sf(df_summary_data['总成本'].sum())
daily_avg_trips = total_hours / 22.0 / 8.0

all_suppliers = df['供应商'].unique()
total_supplier_count = len(all_suppliers)
supplier_grades = df.groupby('供应商')['总分'].max().apply(get_grade)
a_suppliers = int((supplier_grades == 'A').sum())
d_suppliers = int((supplier_grades == 'D').sum())
total_records = len(df)
a_records = int((df['等级'] == 'A').sum())
d_records = int((df['等级'] == 'D').sum())
noncompliant_suppliers = int(df[df['合规标签'] == '不合规']['供应商'].nunique())

# Cost chart
region_cost = []
for _, row in df_summary_data.iterrows():
    daily_ppl = round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）']))
    region_cost.append({
        'region': row['三级组织'], 'time_cost': sf(row['总成本（计时）']),
        'piece_cost': sf(row['总成本（计件）']), 'total_cost': sf(row['总成本']),
        'total_hours': sf(row['总工时数']), 'daily_people': daily_ppl,
    })

region_supplier_data = []
for _, row in df_summary_data.iterrows():
    region_name = row['三级组织']
    rdf = df[df['大区'] == region_name]
    daily_ppl = round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）']))
    region_supplier_data.append({
        'region': region_name, 'daily_people': daily_ppl,
        'total_hours': sf(row['总工时数']),
        'total_suppliers': int(rdf['供应商'].nunique()),
        'compliant': int((rdf['合规标签'] == '合规').sum()),
        'noncompliant': int((rdf['合规标签'] == '不合规').sum()),
        'a_count': int((rdf['等级'] == 'A').sum()), 'b_count': int((rdf['等级'] == 'B').sum()),
        'c_count': int((rdf['等级'] == 'C').sum()), 'd_count': int((rdf['等级'] == 'D').sum()),
    })

def build_analysis(row):
    parts = []
    scores = {'报价竞争力': round(sf(row['报价竞争力得分'])), '派遣满足率': round(sf(row['派遣满足率得分'])),
              '考勤准确率': round(sf(row['考勤准确率得分'])), '人员稳定率': round(sf(row['人员稳定率得分']))}
    total_s = round(sf(row['总分']))
    low_dims = [f'{d}偏低({scores[d]}分)' for d, v in scores.items() if v < 60]
    if low_dims: parts.append('、'.join(low_dims))
    ded_parts = []
    for col, label in zip(deduction_cols_may, deduction_labels_may):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0: ded_parts.append(f'{label}({int(float(v))}分)')
    if ded_parts: parts.append('扣分：' + '、'.join(ded_parts))
    if total_s >= 80 and not parts: return '整体均衡'
    if not parts: return '整体均衡'
    return '；'.join(parts)

supplier_detail = df.groupby(['大区', '供应商']).agg(
    日均使用人数=('实际使用人数（日均）', 'sum'), 总分=('总分', 'max'),
    等级=('等级', 'first'), 合规标签=('合规标签', 'first'),
    不合规原因=('不合规原因', 'first'),
    分拣工时薪=('分拣工时薪', 'mean'), 分拣工markup=('分拣工markup_num', 'mean'),
    分拣工结算价=('分拣工结算价', 'mean'),
    报价竞争力得分=('报价竞争力得分', 'mean'), 派遣满足率得分=('派遣满足率得分', 'mean'),
    考勤准确率得分=('考勤准确率得分', 'mean'), 人员稳定率得分=('人员稳定率得分', 'mean'),
    定量考核总分=('定量考核总分', 'mean'),
    仓库=('仓库', lambda x: ', '.join(x.unique())),
    **{col: (col, 'sum') for col in deduction_cols_may},
).reset_index()

region_daily_totals = supplier_detail.groupby('大区')['日均使用人数'].sum().to_dict()
supplier_detail['人数占比'] = supplier_detail.apply(
    lambda r: sf(r['日均使用人数']) / region_daily_totals.get(r['大区'], 1), axis=1
)
supplier_detail = supplier_detail.sort_values('总分', ascending=False)
supplier_detail['分析'] = supplier_detail.apply(build_analysis, axis=1)

supplier_table = []
for _, row in supplier_detail.iterrows():
    ded_details = {}
    for col, label in zip(deduction_cols_may, deduction_labels_may):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0: ded_details[label] = int(float(v))
    supplier_table.append({
        '大区': row['大区'], '等级': row['等级'], '合规': row['合规标签'],
        '不合规原因': row['不合规原因'] if row['合规标签'] == '不合规' else '',
        '供应商': row['供应商'], '仓库': row['仓库'],
        '日均使用人数': round(sf(row['日均使用人数'])),
        '人数占比': round(sf(row['人数占比']) * 100, 1),
        '时薪': round(sf(row['分拣工时薪']), 1),
        'markup': round(sf(row['分拣工markup']) * 100),
        '结算价': round(sf(row['分拣工结算价']), 1),
        '总分': round(sf(row['总分'])), '分析': row['分析'],
        '报价竞争力得分': round(sf(row['报价竞争力得分'])),
        '派遣满足率得分': round(sf(row['派遣满足率得分'])),
        '考勤准确率得分': round(sf(row['考勤准确率得分'])),
        '人员稳定率得分': round(sf(row['人员稳定率得分'])),
        '定量考核总分': round(sf(row['定量考核总分'])),
        '扣分明细': ded_details,
    })

# Cross-region
multi_region = df.groupby('供应商')['大区'].nunique()
multi_supps = multi_region[multi_region > 1].index.tolist()
cross_region = []
for supp in multi_supps:
    sdf = df[df['供应商'] == supp].groupby('大区').agg(
        日均使用人数=('实际使用人数（日均）', 'sum'), 总分=('总分', 'max'),
        等级=('等级', 'first'), 分拣工时薪=('分拣工时薪', 'mean'),
        分拣工markup=('分拣工markup_num', 'mean'), 分拣工结算价=('分拣工结算价', 'mean'),
    ).reset_index()
    for _, row in sdf.iterrows():
        cross_region.append({
            '供应商': supp, '大区': row['大区'], '日均使用人数': round(sf(row['日均使用人数'])),
            '总分': round(sf(row['总分'])), '等级': row['等级'],
            '时薪': round(sf(row['分拣工时薪']), 1),
            'markup': round(sf(row['分拣工markup']) * 100),
            '结算价': round(sf(row['分拣工结算价']), 1),
        })

# Insurance
insurance_region_map = {
    '佛州': 'FL 佛州大区', '大湖': 'GL 大湖大区', '中南': 'MS 中南大区',
    '东北': 'NE 东北大区', '德州': 'TX 德州大区', '美西': 'WE 美西大区',
    'Ground': 'Ground项目部',
}
insurance = []
for _, row in df_insurance_may.iterrows():
    sn = ss(row['一、保险合规'])
    raw_region = ss(row['Unnamed: 0'])
    if sn in ['/', '', '供应商名称'] or pd.isna(row['一、保险合规']): continue
    if raw_region in ['/', '', '区域'] or pd.isna(row['Unnamed: 0']):
        match = df[df['供应商'].str.upper() == sn.upper()]
        if len(match) > 0: region_name = match.iloc[0]['大区']
        else: continue
    else:
        region_name = insurance_region_map.get(raw_region, raw_region)
    insurance.append({
        '区域': region_name, '供应商': sn,
        '存在问题': ss(row['Unnamed: 2']), '区域反馈进度': ss(row['Unnamed: 3']),
        '区长是否知悉': ss(row['Unnamed: 4']), '责任人': ss(row['Unnamed: 5']),
        'DDL': ss(row['Unnamed: 6']),
    })

# Detail for 5月
regions_order = ['FL 佛州大区', 'GL 大湖大区', 'MS 中南大区', 'NE 东北大区', 'TX 德州大区', 'WE 美西大区', 'Ground项目部']
detail_may = []
for _, row in df.iterrows():
    ded_detail_list = []
    ded_total = 0
    for col, label in zip(deduction_cols_may, deduction_labels_may):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0:
            val = int(float(v))
            ded_total += val
            ded_detail_list.append({'项目': label, '扣分': val})
    detail_may.append({
        '大区': row['大区'], '仓库': row['仓库'], '供应商': row['供应商'],
        '等级': row['等级'], '合规标签': row['合规标签'], '不合规原因': row['不合规原因'],
        '日均使用人数': round(sf(row['实际使用人数（日均）'])),
        '分拣工时薪': round(sf(row['分拣工时薪']), 1),
        'markup': round(sf(row['分拣工markup_num']) * 100),
        '分拣工结算价': round(sf(row['分拣工结算价']), 1),
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
        'onsite_manager_管理幅宽': round(sf(row['Onsite-manager管理幅宽']), 4) if not pd.isna(row['Onsite-manager管理幅宽']) else 0,
        '扣分明细列表': ded_detail_list,
        '扣分总计': ded_total,
        '备注': ss(row.get('备注', '')),
        '报价竞争力_pct': round(sf(row['报价竞争力']) * 100, 1),
        '派遣满足率_pct': round(sf(row['派遣满足率']) * 100, 1),
        '考勤准确率_pct': round(sf(row['考勤准确率']) * 100, 1),
        '人员稳定率_pct': round(sf(row['人员稳定率']) * 100, 1),
    })

detail_by_region_may = {}
for region in regions_order:
    detail_by_region_may[region] = [d for d in detail_may if d['大区'] == region]

# 6月明细
df_j = df_jun.copy()
df_j['等级'] = df_j['总分'].apply(get_grade)
df_j['合规标签'] = df_j['COI合规'].apply(lambda x: '不合规' if pd.notna(x) and str(x).strip() != '' else '合规')
df_j['不合规原因'] = df_j['COI合规'].apply(lambda x: ss(x) if pd.notna(x) else '')

detail_jun = []
for _, row in df_j.iterrows():
    ded_detail_list = []
    ded_total = 0
    for col, label in zip(deduction_cols_jun, deduction_labels_jun):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0:
            val = int(float(v))
            ded_total += val
            ded_detail_list.append({'项目': label, '扣分': val})
    # 备注和COI分开存储
    remark = ss(row.get('备注', ''))
    coi_remark = ss(row.get('COI合规', ''))
    detail_jun.append({
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
        '扣分明细列表': ded_detail_list,
        '扣分总计': ded_total,
        '备注': remark,
        'coi备注': coi_remark,
        '报价竞争力_pct': round(sf(row['报价竞争力']) * 100, 1),
        '派遣满足率_pct': round(sf(row['派遣满足率']) * 100, 1),
        '考勤准确率_pct': round(sf(row['考勤准确率']) * 100, 1),
        '人员稳定率_pct': round(sf(row['人员稳定率']) * 100, 1),
    })

detail_by_region_jun = {}
for region in regions_order:
    detail_by_region_jun[region] = [d for d in detail_jun if d['大区'] == region]

# 6月 region_supplier_data
region_supplier_jun = []
for region in regions_order:
    rdf = df_j[df_j['大区'] == region]
    region_supplier_jun.append({
        'region': region, 'daily_people': int(rdf['实际使用人数（日均）'].sum()),
        'total_suppliers': int(rdf['供应商'].nunique()),
        'compliant': int((rdf['合规标签'] == '合规').sum()),
        'noncompliant': int((rdf['合规标签'] == '不合规').sum()),
        'a_count': int((rdf['等级'] == 'A').sum()), 'b_count': int((rdf['等级'] == 'B').sum()),
        'c_count': int((rdf['等级'] == 'C').sum()), 'd_count': int((rdf['等级'] == 'D').sum()),
    })

# 6月 KPI
jun_total_ppl = int(df_j['实际使用人数（日均）'].sum())
jun_total_supp = int(df_j['供应商'].nunique())
jun_total_records = len(df_j)
jun_grades = df_j.groupby('供应商')['总分'].max().apply(get_grade)
jun_a = int((jun_grades == 'A').sum())
jun_d = int((jun_grades == 'D').sum())
jun_a_rec = int((df_j['等级'] == 'A').sum())
jun_d_rec = int((df_j['等级'] == 'D').sum())
jun_ncomp = int(df_j[df_j['合规标签'] == '不合规']['供应商'].nunique())

# Noncompliant cards (5月)
noncompliant_cards = []
for _, row in df[df['合规标签']=='不合规'].iterrows():
    noncompliant_cards.append({
        '供应商': row['供应商'], '大区': row['大区'], '仓库': row['仓库'],
        '问题': str(row['合规情况']).replace('COI不合规，', '').strip(),
    })

# Risk stats (5月)
has_deduction_set = set()
accident_count = 0
accident_list = []
for _, row in df.iterrows():
    for col in deduction_cols_may:
        v = row.get(col)
        if pd.notna(v) and float(v) != 0:
            has_deduction_set.add(row['供应商'])
            break
    accident_text = str(row.get('库内事故（具体情况）', ''))
    if accident_text and accident_text not in ['nan', '', 'NaN']:
        accident_count += 1
        accident_list.append({
            '大区': row['大区'], '仓库': row['仓库'], '供应商': row['供应商'],
            '事件': accident_text,
        })
risk_stats = {
    'low_score_count': int((df['总分'] < 50).sum()),
    'has_deduction': len(has_deduction_set),
    'accident_count': accident_count,
    'accident_list': accident_list,
}

# High risk (5月)
high_risk = []
for _, row in df[df['总分'] < 50].iterrows():
    ded_parts = []
    ded_total = 0
    for col, label in zip(deduction_cols_may, deduction_labels_may):
        v = row.get(col)
        if pd.notna(v) and float(v) != 0:
            ded_parts.append(f'{label}({int(float(v))}分)')
            ded_total += int(float(v))
    high_risk.append({
        '大区': row['大区'], '仓库': row['仓库'], '供应商': row['供应商'],
        '总分': round(sf(row['总分'])),
        '扣分总分': ded_total,
        '扣分汇总': '、'.join(ded_parts) if ded_parts else '无',
    })

# Cost chart total
total_cost_all_regions = sum(r['total_cost'] for r in region_cost)
for r in region_supplier_data:
    matched = [c for c in region_cost if c['region'] == r['region']]
    if matched:
        r['cost_pct'] = round(matched[0]['total_cost'] / total_cost_all_regions * 100, 1) if total_cost_all_regions > 0 else 0
        r['total_cost'] = matched[0]['total_cost']
    else:
        r['cost_pct'] = 0
        r['total_cost'] = 0

# ─── 成本分析（5月）───
region_employer_cost_rate = {
    'FL 佛州大区': 0.14, 'GL 大湖大区': 0.145, 'MS 中南大区': 0.135,
    'NE 东北大区': 0.16, 'TX 德州大区': 0.125, 'WE 美西大区': 0.17, 'Ground项目部': 0.12,
}
cost_analysis = []
for _, row in df_summary_data.iterrows():
    region_name = row['三级组织']
    rdf = df[df['大区'] == region_name]
    ec_rate = region_employer_cost_rate.get(region_name, 0.12)
    avg_wage = round(sf(rdf['分拣工时薪'].mean()), 1)
    avg_settle = round(sf(rdf['分拣工结算价'].mean()), 1)
    avg_markup = round(sf(rdf['分拣工markup_num'].mean()) * 100)
    ec_per_hour = round(avg_wage * ec_rate, 2)
    profit_per_hour = round(avg_settle - avg_wage - ec_per_hour, 2)
    profit_rate = round(profit_per_hour / avg_settle * 100, 1) if avg_settle > 0 else 0
    cost_analysis.append({
        '大区': region_name, '日均人数': round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）'])),
        '供应商数': int(rdf['供应商'].nunique()),
        '平均时薪': avg_wage, '平均markup': avg_markup, '平均结算价': avg_settle,
        '计时成本': round(sf(row['总成本（计时）'])), '计件成本': round(sf(row['总成本（计件）'])),
        '总成本': round(sf(row['总成本'])), '总工时': round(sf(row['总工时数'])),
        '雇主成本率': ec_rate, '雇主成本': ec_per_hour,
        '利润_per_h': profit_per_hour, '利润率': profit_rate,
    })

# Ladder matrix (5月)
warehouse_state_rate = {
    'MCO.H': 0.15, 'MIA.H': 0.15, 'SJU.H': 0.15,
    'ORD.H': 0.16, 'CVG.H': 0.16,
    'ATL.H': 0.15, 'CLT.H': 0.15, 'PDK.H': 0.15,
    'EWR.H': 0.17, 'JFK.H': 0.17, 'BWI.H': 0.17,
    'DFW.H': 0.14, 'IAH.H': 0.14,
    'CNO.H': 0.18, 'DEN.H': 0.16, 'LAV.H': 0.18, 'SEA.H': 0.17, 'SFO.H': 0.18,
    'ATL.G': 0.15, 'CNO.G': 0.18, 'EWR.G': 0.17, 'ORD.G': 0.16, 'SFO.G': 0.18, 'SAV.G': 0.15,
}
df['结算价'] = df['分拣工结算价'].astype(float)
df['时薪'] = df['分拣工时薪'].astype(float)
df['人数'] = df['实际使用人数（日均）'].astype(float)
df['雇主成本率'] = df['仓库'].map(warehouse_state_rate).fillna(0.12)
df['雇主成本/h'] = df['时薪'] * df['雇主成本率']
df['利润/h'] = df['结算价'] - df['时薪'] - df['雇主成本/h']
df['利润率'] = df['利润/h'] / df['结算价'] * 100

df_cost_clean = df_cost_detail_may.iloc[1:].copy()
df_cost_clean.columns = ['大区','仓库','供应商','费用月份','单小时成本','总工时','货币','当月成本','备注']
df_cost_clean['当月成本'] = pd.to_numeric(df_cost_clean['当月成本'].astype(str).str.replace(',','').str.replace(' ','').str.replace('$','').str.replace('\xa0',''), errors='coerce')
cost_by_warehouse = df_cost_clean.groupby(['仓库','供应商'])['当月成本'].sum().reset_index()
cost_by_warehouse.columns = ['仓库','供应商','当月成本']
df_merged = df.merge(cost_by_warehouse, on=['仓库','供应商'], how='left')
df_merged['当月成本'] = df_merged['当月成本'].fillna(0)
mask = df_merged['当月成本'] == 0
df_merged.loc[mask, '当月成本'] = df_merged.loc[mask, '结算价'] * df_merged.loc[mask, '人数'] * 22 * 8
df_merged['当月成本'] = df_merged['当月成本'].round(0).astype(int)
df_merged['markup_pct'] = (df_merged['分拣工markup'].apply(lambda x: float(str(x).replace('%',''))/100 if pd.notna(x) else 0) * 100).fillna(0).round(0).astype(int)

def get_volume_tier(ppl):
    if ppl >= 200: return 'A: ≥200人/天', 0
    elif ppl >= 100: return 'B: 100-199人/天', 1
    elif ppl >= 50: return 'C: 50-99人/天', 2
    elif ppl >= 20: return 'D: 20-49人/天', 3
    else: return 'E: <20人/天', 4

discount_matrix = {
    'A: ≥200人/天': [8, 6, 4, 2, 0],
    'B: 100-199人/天': [6, 4, 2, 0, 0],
    'C: 50-99人/天': [4, 2, 0, 0, 0],
    'D: 20-49人/天': [2, 0, 0, 0, 0],
    'E: <20人/天': [0, 0, 0, 0, 0],
}

def get_profit_bucket(pr):
    if pd.isna(pr): return 4
    if pr >= 20: return 0
    elif pr >= 10: return 1
    elif pr >= 5: return 2
    elif pr >= 0: return 3
    else: return 4

profit_bucket_names = ['≥20%', '10%-20%', '5%-10%', '0%-5%', '<0%（需核查）']
ladder_matrix = []
tier_list = [('A: ≥200人/天',0),('B: 100-199人/天',1),('C: 50-99人/天',2),('D: 20-49人/天',3),('E: <20人/天',4)]
for tier_name, tier_idx in tier_list:
    row_data = {'用量阶梯': tier_name}
    for pb_idx, pb_name in enumerate(profit_bucket_names):
        disc = discount_matrix[tier_name][pb_idx]
        row_data[pb_name] = f'降{disc}%' if disc > 0 else '维持'
    ladder_matrix.append(row_data)

supplier_cost = df_merged.groupby('供应商').agg(
    大区列表=('大区', lambda x: ', '.join(sorted(set(x)))),
    总日均人数=('人数','sum'), 加权结算价=('结算价', lambda x: round((x * df_merged.loc[x.index,'人数']).sum() / df_merged.loc[x.index,'人数'].sum(), 2)),
    加权时薪=('时薪', lambda x: round((x * df_merged.loc[x.index,'人数']).sum() / df_merged.loc[x.index,'人数'].sum(), 2)),
    加权雇主成本率=('雇主成本率', lambda x: round((x * df_merged.loc[x.index,'人数']).sum() / df_merged.loc[x.index,'人数'].sum() * 100, 1)),
    平均总分=('总分','mean'), 等级=('等级','first'),
).reset_index()
supplier_cost['利润/h'] = (supplier_cost['加权结算价'] - supplier_cost['加权时薪'] - supplier_cost['加权时薪'] * supplier_cost['加权雇主成本率'] / 100).round(2)
supplier_cost['利润率%'] = (supplier_cost['利润/h'] / supplier_cost['加权结算价'] * 100).round(1)
supplier_cost['总日均人数'] = supplier_cost['总日均人数'].round(0).astype(int)
supplier_cost['雇主成本/h'] = (supplier_cost['加权时薪'] * supplier_cost['加权雇主成本率'] / 100).round(2)
supplier_cost['当月成本合计'] = df_merged.groupby('供应商')['当月成本'].sum().reindex(supplier_cost['供应商']).fillna(0).round(0).astype(int).values

def calc_discount(ppl, pr, ph, sp, wg, ec, monthly_cost):
    tier_name, tier_idx = get_volume_tier(ppl)
    pb_idx = get_profit_bucket(pr)
    disc = discount_matrix[tier_name][pb_idx]
    annual_saving = round(monthly_cost * 12 * (disc / 100))
    if pr < 0:
        reason = f'测算利润{pr:.0f}%(异常)，供应商不可能亏损，需核查时薪${wg:.2f}或markup，利润可能从劳务工时薪中扣除'
    elif disc == 0:
        reason = f'测算利润率仅{pr:.0f}%，利润空间不足，维持现价'
    else:
        tier_short = tier_name.split(': ')[1]
        reason = f'用工{tier_short}→降{disc}%（结算${sp:.2f}=时薪${wg:.2f}+雇主成本${ec:.2f}+利润${ph:.2f}）'
    return tier_name.split(': ')[1], disc, annual_saving, reason

supplier_cost[['用量阶梯','建议降价%','预计年节省','谈价策略']] = supplier_cost.apply(
    lambda r: pd.Series(calc_discount(r['总日均人数'], r['利润率%'], r['利润/h'], r['加权结算价'], r['加权时薪'], r['雇主成本/h'], r['当月成本合计'])), axis=1
)
supplier_cost = supplier_cost.sort_values('总日均人数', ascending=False)

warehouse_detail = df_merged.copy()
warehouse_detail['利润率%'] = warehouse_detail['利润率'].round(1)
warehouse_negotiation = []
for _, row in warehouse_detail.iterrows():
    ppl = row['人数']; pr = row['利润率%']; ph = row['利润/h']
    sp = row['结算价']; wg = row['时薪']; ec = row['雇主成本/h']; mc = row['当月成本']
    tier, disc, saving, reason = calc_discount(ppl, pr, ph, sp, wg, ec, mc)
    def safe_float(v): return 0.0 if pd.isna(v) else float(v)
    def safe_int(v): return 0 if pd.isna(v) else int(v)
    warehouse_negotiation.append({
        '供应商': row['供应商'], '大区': row['大区'], '仓库': row['仓库'],
        '日均人数': safe_int(ppl), '结算价': safe_float(sp), '时薪': safe_float(wg),
        '雇主成本/h': safe_float(ec), '利润/h': safe_float(ph), '利润率': safe_float(pr),
        'markup': safe_int(row['markup_pct']), '用量阶梯': tier,
        '建议降价%': disc, '预计年节省': safe_int(saving),
        '当月成本': safe_int(mc), '谈价策略': reason, '等级': row['等级'],
    })
warehouse_negotiation.sort(key=lambda x: x['日均人数'], reverse=True)

ladder_data = []
tier_ranges = [('A: ≥200人/天', 200, 99999),('B: 100-199人/天', 100, 199),('C: 50-99人/天', 50, 99),('D: 20-49人/天', 20, 49),('E: <20人/天', 0, 19)]
for label, lo, hi in tier_ranges:
    subset = supplier_cost[(supplier_cost['总日均人数'] >= lo) & (supplier_cost['总日均人数'] <= hi)]
    cnt = len(subset)
    pos = subset[subset['利润率%'] > 0]
    neg = subset[subset['利润率%'] < 0]
    avg_disc = round(pos['建议降价%'].mean(), 1) if len(pos) > 0 else 0
    saving = int(subset['预计年节省'].sum())
    current_cost = int(subset['当月成本合计'].sum())
    ladder_data.append({
        'label': label.split(': ')[1], 'count': cnt,
        'pos_count': len(pos), 'neg_count': len(neg),
        'avg_discount': avg_disc, 'annual_saving': saving,
        'current_cost': current_cost,
    })

# ─── 6月汇总数据 ───
jun_summary_data = df_summary_jun[df_summary_jun['三级组织'].notna()]
jun_total_ppl_sum = sf(jun_summary_data['计时人数（日均）'].sum()) + sf(jun_summary_data['计件人数（日均）'].sum())
jun_total_time_ppl = sf(jun_summary_data['计时人数（日均）'].sum())
jun_total_piece_ppl = sf(jun_summary_data['计件人数（日均）'].sum())
jun_total_hours_sum = sf(jun_summary_data['总工时数'].sum())
jun_total_cost_sum = sf(jun_summary_data['总成本'].sum())
jun_daily_trips = jun_total_hours_sum / 22.0 / 8.0

# 5月 vs 6月对比数据
jun_cost_chart = []
for _, row in jun_summary_data.iterrows():
    daily_ppl = round(sf(row['计时人数（日均）']) + sf(row['计件人数（日均）']))
    jun_cost_chart.append({
        'region': row['三级组织'], 'time_cost': sf(row['总成本（计时）']),
        'piece_cost': sf(row['总成本（计件）']), 'total_cost': sf(row['总成本']),
        'total_hours': sf(row['总工时数']), 'daily_people': daily_ppl,
    })

# ─── 最终输出 ───
output = {
    'kpi': {
        # 5月数据（保持原有）
        'daily_avg_people': round(daily_avg_people), 'daily_avg_people_time': round(daily_avg_people_time),
        'daily_avg_people_piece': round(daily_avg_people_piece),
        'daily_avg_trips': round(daily_avg_trips),
        'total_hours': round(total_hours), 'total_cost': round(total_cost),
        'total_supplier_count': total_supplier_count, 'total_records': total_records,
        'a_suppliers': a_suppliers, 'a_pct': f'{a_records}/{total_records}',
        'd_suppliers': d_suppliers, 'd_pct': f'{d_records}/{total_records}',
        'coi_noncompliant': noncompliant_suppliers, 'coi_pct': f'{noncompliant_suppliers}/{total_supplier_count}',
        # 6月数据
        'jun_daily_avg_people': round(jun_total_ppl_sum),
        'jun_daily_avg_people_time': round(jun_total_time_ppl),
        'jun_daily_avg_people_piece': round(jun_total_piece_ppl),
        'jun_daily_avg_trips': round(jun_daily_trips),
        'jun_total_hours': round(jun_total_hours_sum),
        'jun_total_cost': round(jun_total_cost_sum),
        'jun_total_supplier_count': jun_total_supp,
        'jun_total_records': jun_total_records,
        'jun_a_suppliers': jun_a, 'jun_a_pct': f'{jun_a_rec}/{jun_total_records}',
        'jun_d_suppliers': jun_d, 'jun_d_pct': f'{jun_d_rec}/{jun_total_records}',
        'jun_coi_noncompliant': jun_ncomp,
        'jun_coi_pct': f'{jun_ncomp}/{jun_total_supp}',
    },
    'cost_chart': region_cost, 'people_supplier_chart': region_supplier_data,
    'cost_chart_jun': jun_cost_chart, 'people_supplier_chart_jun': region_supplier_jun,
    'supplier_table': supplier_table, 'cross_region': cross_region,
    'insurance': insurance,
    'detail_by_region': detail_by_region_may,
    'detail_by_region_jun': detail_by_region_jun,
    'cost_analysis': cost_analysis,
    'total_daily_people': round(daily_avg_people),
    'regions': regions_order,
    'ladder_data': ladder_data, 'ladder_matrix': ladder_matrix,
    'supplier_negotiation': warehouse_negotiation,
    'noncompliant_cards': noncompliant_cards,
    'risk_stats': risk_stats, 'high_risk': high_risk,
    'months': ['2026年5月', '2026年6月'],
}

def convert(o):
    if isinstance(o, dict): return {k: convert(v) for k, v in o.items()}
    elif isinstance(o, list): return [convert(i) for i in o]
    elif hasattr(o, 'item'): return o.item()
    return o

output = convert(output)
with open('/Users/mac/CodeBuddy/20260618112854/dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print('Done!')
