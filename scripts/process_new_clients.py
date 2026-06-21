"""
处理新客户名单，保留原表格式，新增信用评估列。

用法:
    python scripts/process_new_clients.py --input data/new_clients_template.tsv
"""
import sys
import os
import re
import argparse
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.evaluation.client_eval import ClientEvaluator, print_report
from src.evaluation.batch_eval import export_results_to_excel
from src.utils.database import add_client, get_client_by_credit_code, save_evaluation


DEFAULT_INPUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "new_clients_template.tsv")


def parse_raw_data(input_path: str = DEFAULT_INPUT):
    """从 TSV 文件解析原始数据"""
    df = pd.read_csv(input_path, sep='\t', dtype=str).fillna('')
    return df


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
    evaluator = ClientEvaluator(use_opencli=True, use_browser=True, new_client=True)
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
    parser = argparse.ArgumentParser(description='处理新客户名单并生成信用评估')
    parser.add_argument('--input', default=DEFAULT_INPUT, help='新客户名单 TSV 文件路径')
    args = parser.parse_args()

    # 1. 解析原始数据
    original_df = parse_raw_data(args.input)
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
