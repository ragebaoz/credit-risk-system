"""
批量评估工具
支持从 Excel 文件批量导入客户并评估
"""
import sys
import os
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.evaluation.client_eval import ClientEvaluator, print_report
from src.utils.database import add_client, get_client_by_credit_code, save_evaluation


def batch_evaluate_from_excel(excel_path: str, evaluator: ClientEvaluator = None) -> List[Dict[str, Any]]:
    """
    从 Excel 批量评估客户
    
    Excel 列名要求：
    - name: 客户名称（必填）
    - credit_code: 统一社会信用代码
    - industry: 行业
    - on_time_rate: 回款准时率
    - avg_overdue_days: 平均逾期天数
    - max_overdue_amount: 最大逾期金额占比
    - cooperation_years: 合作年限
    """
    df = pd.read_excel(excel_path)
    results = []
    
    print(f"\n开始批量评估，共 {len(df)} 个客户...\n")
    
    for idx, row in df.iterrows():
        name = row.get('name')
        if pd.isna(name):
            continue
        
        print(f"\n[{idx+1}/{len(df)}] 评估客户: {name}")
        
        credit_code = str(row.get('credit_code', '')) if not pd.isna(row.get('credit_code')) else None
        industry = str(row.get('industry', '')) if not pd.isna(row.get('industry')) else None
        
        # 构建内部数据
        internal_data = {}
        for col in ['on_time_rate', 'avg_overdue_days', 'max_overdue_amount', 'cooperation_years']:
            if col in row and not pd.isna(row[col]):
                internal_data[col] = row[col]
        
        try:
            result = evaluator.evaluate(
                name=name,
                credit_code=credit_code,
                industry=industry,
                internal_data=internal_data if internal_data else None,
                save=False  # 批量评估后统一保存
            )
            results.append(result)
            
            # 保存到数据库
            if credit_code:
                client = get_client_by_credit_code(credit_code)
                if not client:
                    client_id = add_client(name=name, credit_code=credit_code, industry=industry)
                else:
                    client_id = client['id']
                save_evaluation(client_id, result['raw_data'], result)
        
        except Exception as e:
            print(f"  ❌ 评估失败: {e}")
            results.append({'client_name': name, 'error': str(e)})
    
    return results


def export_results_to_excel(results: List[Dict[str, Any]], output_path: str):
    """导出评估结果到 Excel"""
    rows = []
    for r in results:
        if 'error' in r:
            rows.append({
                '客户名称': r['client_name'],
                '评估状态': '失败',
                '错误信息': r['error']
            })
        else:
            rows.append({
                '客户名称': r['client_name'],
                '统一社会信用代码': r.get('credit_code', ''),
                '综合评分': r['total_score'],
                '风险等级': r['risk_grade'],
                '建议账期(天)': r['suggested_days'],
                '建议授信(元)': r['suggested_credit'],
                '预付款比例': f"{r['advance_ratio']*100:.0f}%",
                '复核周期': r['review_cycle'],
                '基础信用得分': r['dimension_scores'].get('basic_credit'),
                '财务健康得分': r['dimension_scores'].get('financial_health'),
                '履约行为得分': r['dimension_scores'].get('payment_behavior'),
                '外部风险得分': r['dimension_scores'].get('external_risk'),
                '预警数量': len(r.get('warnings', [])),
                '评估时间': r['evaluation_date']
            })
    
    df = pd.DataFrame(rows)
    df.to_excel(output_path, index=False)
    print(f"\n📄 结果已导出: {output_path}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='批量客户信用评估')
    parser.add_argument('--input', required=True, help='输入Excel文件路径')
    parser.add_argument('--output', default='reports/batch_evaluation_result.xlsx', help='输出结果路径')
    parser.add_argument('--opencli', action='store_true', default=True, help='使用 OpenCLI Browser 模式（默认开启）')
    parser.add_argument('--no-opencli', action='store_true', help='禁用 OpenCLI Browser')
    parser.add_argument('--browser', action='store_true', help='使用 Playwright CDP 浏览器模式')
    parser.add_argument('--no-headless', action='store_true', help='浏览器可视化模式')
    
    args = parser.parse_args()
    
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    evaluator = ClientEvaluator(use_opencli=not args.no_opencli, use_browser=args.browser, headless=not args.no_headless)
    results = batch_evaluate_from_excel(args.input, evaluator)
    
    # 统计
    success = [r for r in results if 'error' not in r]
    failed = [r for r in results if 'error' in r]
    
    print(f"\n{'='*60}")
    print("批量评估完成")
    print(f"{'='*60}")
    print(f"总计: {len(results)} 个客户")
    print(f"成功: {len(success)} 个")
    print(f"失败: {len(failed)} 个")
    
    if success:
        grade_dist = {}
        for r in success:
            g = r['risk_grade']
            grade_dist[g] = grade_dist.get(g, 0) + 1
        print(f"\n风险等级分布:")
        for g in ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C']:
            if g in grade_dist:
                print(f"  {g}: {grade_dist[g]} 个")
    
    export_results_to_excel(results, args.output)
