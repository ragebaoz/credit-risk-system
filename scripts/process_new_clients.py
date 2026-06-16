"""
处理新客户名单，保留原表格式，新增信用评估列。
"""
import sys
import os
import re
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.evaluation.client_eval import ClientEvaluator, print_report
from src.evaluation.batch_eval import export_results_to_excel
from src.utils.database import add_client, get_client_by_credit_code, save_evaluation


# 用户提供的原始数据
RAW_DATA = """渠道组	KA客户	客户	对方单位名称
商超便利	KA华东罗森	华东-罗森	上海罗森便利有限公司
商超便利	KA永辉	永辉	福建云通供应链有限公司
新渠道	KA德克士	德克士	天津顶连食品有限公司；天津顶连食品有限公司上海分公司
商超便利	KA好特卖	好特卖	上海好特卖惠聚贸易有限公司
商超便利	KA浙江易捷	易捷	中国石化销售股份有限公司浙江石油分公司
饰品潮玩	KA如苔文具	新华书店	浙江如苔文化科技有限公司
饰品潮玩	KA酷乐潮玩	酷乐潮玩	宁波酷乐潮玩潮流百货有限公司
饰品潮玩	KA酷乐潮玩	KA酷乐潮玩	宁波酷乐潮玩潮流百货有限公司
饰品潮玩	KA酷乐潮玩（购销）	KA酷乐潮玩（购销）	宁波酷乐潮玩潮流百货有限公司
零食	KA深圳品味	零食有鸣	深圳品味一族工贸有限公司
新渠道	KA上海寰越	a2	上海寰越电子商务有限公司
新渠道	KA中国农垦	a2	中国农垦控股上海有限公司
新渠道	KA中国农垦	a2	中国农垦控股上海有限公司
新渠道	KA逸道盛	a2	上海逸道盛实业有限公司
商超便利	KA上海迦月	7-Eleven	上海迦月贸易有限公司
商超便利	KA浙江驰骋	左邻右舍/生活驿站	浙江驰骋物流有限公司
饰品潮玩	KA番茄口袋	番茄口袋	上海番茄口袋电子商务有限公司
饰品潮玩	KA浙江凯蓝	TGP/伶俐	浙江凯畔商贸有限公司，浙江盛伶商贸有限公司
零食	KA万辰集团	万辰	南京万兴商业管理有限公司,南京万好供应链管理有限公司,南京万优供应链管理有限公司,南京万昌供应链管理有限公司,南京万灿供应链管理有限公司,泰州万拓供应链管理有限公司,南京万权商业管理有限公司,宁波巨库
商超便利	KA深圳旭展	沃尔玛	深圳市旭展文体用品有限公司
饰品潮玩	KA上海终为始	ATM潮玩艺术馆	上海终为始贸易有限公司
饰品潮玩	KALOFT	LOFT	乐瑚特商业管理（上海）有限公司
零食	KA鸣鸣很忙	鸣鸣很忙	湖南鸣鸣很忙商业连锁股份有限公司
商超便利	KA苏州乐业	华东大润发	苏州乐业贸易有限公司
饰品潮玩	KA三福海外	三福海外	广州市福榕瑞贸易有限公司
饰品潮玩	KA浙数潮品	球星卡社	浙数潮品科技(浙江)有限公司
饰品潮玩	KATOPTOY	TOPTOY	那是家大潮玩（广东）文化创意有限公司
饰品潮玩	KA晨光生活馆	晨光生活馆	晨光生活馆企业管理有限公司
新渠道	KA奥卡普		奥卡普（上海）文化发展有限公司
新渠道	KA锅圈	锅圈	锅圈食品（上海）股份有限公司
商超便利	KA新天地超市	新天地	沈阳新天地超市连锁经营有限公司
商超便利	KA深圳旭展	沃尔玛	深圳市旭展文体用品有限公司
商超便利	KA沃尔玛	沃尔玛	沃尔玛（中国）投资有限公司
饰品潮玩	KA终为始	上影影城	上海终为始贸易有限公司
零食	KA万辰集团	万辰	福建万辰食品集团股份有限公司南京分公司
新渠道	KA上海铂泫	高铁	上海铂泫贸易有限公司
饰品潮玩	KA畹町（购销）	畹町	宁波热风企业管理有限公司
饰品潮玩	KA广州盟客	KKV	东莞市盟客供应链科技有限公司
商超便利	KA新佳宜	新佳宜	湖南新佳宜商贸有限公司
商超便利	KA比优特	比优特	真市美供应链（沈阳）有限公司
饰品潮玩	KA泡泡吧	泡泡吧	宁波旭歌贸易有限公司
商超便利	KA壹度便利	壹度便利	安徽优壹达供应链有限公司
商超便利	KA麦德龙	麦德龙	麦德龙商业集团有限公司
新渠道	KA西西弗（购销）	西西弗	重庆西西弗文化传播有限公司
商超便利	空白	Ole	深圳市罗湖华润万家商业科技有限公司
商超便利	KA潍坊千佰佳	佳乐家	潍坊千佰佳商贸有限公司
商超便利	KA 山东童趣多	家家悦	山东童趣多儿童用品有限公司
商超便利	KA南京熙泽	朴朴超市/叮咚买...	南京煦泽科技有限公司
饰品潮玩	KA木本木	木本木	东阳市小木百货零售有限公司
饰品潮玩	KA三福百货	三福	福建三福服饰有限公司
商超便利	KA北京百望达	江苏7-11	北京百望达商贸有限公司
商超便利	KA上海逸刻	逸刻	上海逸刻新零售网络科技有限公司
零食	KA零食优选	零食优选	四川蜀之优供应链管理有限公司，陕西惠小优供应链管理有限公司，重庆零小优供应链管理有限公司，云南七号仓供应链管理有限公司，东莞市零小优供应链管理有限公司，贵州喆选供应链有限责任公司，湖北雨追供应链管理有
新渠道	KA上海追越	BALABALA	上海追越创意设计有限公司
新渠道	KA蜜雪冰城	蜜雪冰城	河南雪王商贸有限公司
商超便利	KA大连半人马	东北-罗森	大连半人马商贸有限公司
商超便利	KA青岛瑞诺祥优	山东利群	青岛瑞诺祥优商贸有限公司
零食	KA养馋记	养馋记	浙江养馋记供应链管理有限公司
新渠道	KA黄钻玩具仓	黄钻玩具仓	杭州黄钻文化科技有限公司"""


def parse_raw_data():
    """解析原始 TSV 数据"""
    lines = RAW_DATA.strip().split('\n')
    headers = lines[0].split('\t')
    rows = []
    for line in lines[1:]:
        parts = line.split('\t')
        # 补齐列数
        while len(parts) < len(headers):
            parts.append('')
        rows.append(parts[:len(headers)])
    return pd.DataFrame(rows, columns=headers)


def split_company_names(name_str: str):
    """
    拆分多个公司名称（按；;, 分割）
    返回列表，并清理空格和引号
    """
    if not name_str or pd.isna(name_str):
        return []
    name_str = str(name_str).strip().strip('"').strip('"')
    # 统一分隔符
    for sep in ['；', ';', '，', ',']:
        name_str = name_str.replace(sep, '|')
    names = [n.strip() for n in name_str.split('|') if n.strip()]
    return names


def build_eval_list(df: pd.DataFrame):
    """
    从原始表构建评估用列表。
    对多公司名的行，拆分成多条记录，但保留原始行索引用于后续合并。
    """
    eval_rows = []
    for idx, row in df.iterrows():
        company_names = split_company_names(row['对方单位名称'])
        if not company_names:
            # 对方单位名称为空，用客户名代替
            company_names = [row['客户']] if row['客户'] else [row['KA客户']]
        for name in company_names:
            eval_rows.append({
                'original_index': idx,
                '渠道组': row['渠道组'],
                'KA客户': row['KA客户'],
                '客户': row['客户'],
                '对方单位名称': row['对方单位名称'],
                'eval_name': name,
            })
    return pd.DataFrame(eval_rows)


def evaluate_clients(eval_df: pd.DataFrame):
    """批量评估客户"""
    # 当前环境 OpenCLI extension 未连接，直接用模拟数据快速出结果
    # 如需真实数据，请确保 Chrome + OpenCLI 扩展已启用，再改为 use_opencli=True
    evaluator = ClientEvaluator(use_opencli=False, use_browser=False, new_client=True)
    results = []

    print(f"\n开始评估，共 {len(eval_df)} 条记录...\n")

    for idx, row in eval_df.iterrows():
        name = row['eval_name']
        print(f"[{idx+1}/{len(eval_df)}] 评估: {name}")

        try:
            result = evaluator.evaluate(
                name=name,
                credit_code=None,
                industry=row['渠道组'],
                internal_data={'cooperation_years': 0},
                save=False
            )
            results.append({
                'original_index': row['original_index'],
                'eval_name': name,
                'total_score': result['total_score'],
                'risk_grade': result['risk_grade'],
                'suggested_days': result['suggested_days'],
                'suggested_credit': result['suggested_credit'],
                'advance_ratio': result['advance_ratio'],
                'review_cycle': result['review_cycle'],
                'policy_desc': result['policy_desc'],
                'warnings_count': len(result.get('warnings', [])),
                'veto_count': len(result.get('veto_rules', [])),
                'error': None,
            })
        except Exception as e:
            print(f"  ❌ 失败: {e}")
            results.append({
                'original_index': row['original_index'],
                'eval_name': name,
                'total_score': None,
                'risk_grade': 'ERROR',
                'suggested_days': None,
                'suggested_credit': None,
                'advance_ratio': None,
                'review_cycle': None,
                'policy_desc': str(e),
                'warnings_count': 0,
                'veto_count': 0,
                'error': str(e),
            })

    return pd.DataFrame(results)


def merge_results(original_df: pd.DataFrame, eval_df: pd.DataFrame, result_df: pd.DataFrame):
    """
    将评估结果合并回原始表格。
    对同一个 original_index 有多条评估结果的，取平均分/最严格等级。
    """
    # 按 original_index 聚合
    agg = result_df.groupby('original_index').agg({
        'total_score': 'mean',
        'risk_grade': lambda x: min(x.dropna().tolist(), key=lambda g: {'AAA':6,'AA':5,'A':4,'BBB':3,'BB':2,'B':1,'C':0}.get(g, -1)) if any(x.dropna()) else 'N/A',
        'suggested_days': 'min',
        'suggested_credit': 'min',
        'advance_ratio': 'max',
        'warnings_count': 'sum',
        'veto_count': 'sum',
        'error': lambda x: '; '.join([str(e) for e in x if e]) if any(x) else '',
        'eval_name': lambda x: ' / '.join(x.tolist()),
    }).reset_index()

    # 重命名列
    agg = agg.rename(columns={
        'total_score': '信用评分',
        'risk_grade': '风险等级',
        'suggested_days': '建议账期(天)',
        'suggested_credit': '建议授信(元)',
        'advance_ratio': '预付款比例',
        'warnings_count': '预警数量',
        'veto_count': '否决规则数',
        'error': '评估错误',
        'eval_name': '评估对象',
    })

    # 合并到原始表
    merged = original_df.merge(agg, left_index=True, right_on='original_index', how='left')
    merged = merged.drop(columns=['original_index'])

    # 调整列顺序：原始列在前，新增列在后
    original_cols = list(original_df.columns)
    new_cols = [c for c in merged.columns if c not in original_cols]
    merged = merged[original_cols + new_cols]

    return merged


def main():
    # 1. 解析原始数据
    original_df = parse_raw_data()
    print(f"原始表格: {len(original_df)} 行")

    # 2. 构建评估列表
    eval_df = build_eval_list(original_df)
    print(f"展开后评估记录: {len(eval_df)} 条（含多公司名拆分）")

    # 3. 批量评估
    result_df = evaluate_clients(eval_df)

    # 4. 合并回原始表
    merged_df = merge_results(original_df, eval_df, result_df)

    # 5. 输出
    output_path = 'reports/新客户信用评估结果.xlsx'
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    merged_df.to_excel(output_path, index=False)
    print(f"\n📄 结果已保存: {output_path}")

    # 6. 打印摘要
    print(f"\n{'='*60}")
    print("评估摘要")
    print(f"{'='*60}")
    print(f"总客户数: {len(original_df)}")
    print(f"评估成功: {(merged_df['风险等级'] != 'ERROR').sum()}")
    print(f"评估失败: {(merged_df['风险等级'] == 'ERROR').sum()}")
    print("\n风险等级分布:")
    for g in ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C', 'ERROR']:
        cnt = (merged_df['风险等级'] == g).sum()
        if cnt > 0:
            print(f"  {g}: {cnt} 个")

    return merged_df


if __name__ == '__main__':
    main()
