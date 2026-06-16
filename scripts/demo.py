#!/usr/bin/env python3
"""
演示脚本：快速体验系统功能
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.utils.database import init_database
from src.evaluation.client_eval import ClientEvaluator, print_report


def demo():
    """运行演示评估"""
    print("=" * 70)
    print("渠道客户信用风险评估系统 - 演示")
    print("=" * 70)
    
    # 初始化数据库
    init_database()
    
    evaluator = ClientEvaluator()
    
    # 模拟几个不同类型的客户
    test_clients = [
        {
            'name': '北京某科技有限公司',
            'credit_code': '91110108MA005K8N5X',
            'industry': 'technology',
            'internal_data': {
                'on_time_rate': 0.95,
                'avg_overdue_days': 5,
                'max_overdue_amount': 0.02,
                'cooperation_years': 5
            }
        },
        {
            'name': '上海某贸易有限公司',
            'credit_code': '91310110MA1G8J2P7B',
            'industry': 'trade',
            'internal_data': {
                'on_time_rate': 0.60,
                'avg_overdue_days': 45,
                'max_overdue_amount': 0.35,
                'cooperation_years': 1
            }
        },
        {
            'name': '深圳某建筑工程公司',
            'credit_code': '91440300MA5G8N2K3L',
            'industry': 'construction',
            'internal_data': {
                'on_time_rate': 0.40,
                'avg_overdue_days': 80,
                'max_overdue_amount': 0.55,
                'cooperation_years': 0.5
            }
        }
    ]
    
    for client in test_clients:
        result = evaluator.evaluate(
            name=client['name'],
            credit_code=client['credit_code'],
            industry=client.get('industry'),
            internal_data=client.get('internal_data'),
            save=True
        )
        print_report(result)
    
    print("\n" + "=" * 70)
    print("演示完成！")
    print("=" * 70)
    print("\n后续操作建议：")
    print("1. 启动 API 服务: python -m src.api.server")
    print("2. 执行监控检查: python -m src.monitoring.watcher --run-once")
    print("3. 生成监控报告: python -m src.monitoring.watcher --report")
    print("4. 批量评估: python -m src.evaluation.batch_eval --input data/client_list.xlsx")


if __name__ == "__main__":
    demo()
