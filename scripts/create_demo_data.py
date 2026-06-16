#!/usr/bin/env python3
"""
生成演示用的批量导入Excel文件
"""
import sys
import os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def create_demo_excel():
    data = {
        'name': [
            '杭州某电子商务有限公司',
            '广州某制造有限公司',
            '成都某物流有限公司',
            '武汉某科技有限公司',
            '南京某建筑工程有限公司',
            '西安某贸易有限公司',
            '重庆某信息技术有限公司',
            '天津某化工有限公司'
        ],
        'credit_code': [
            '91330106MA2KCD8N5X',
            '91440101MA5G8J2P7B',
            '91510100MA6C8N2K3L',
            '91420100MA5G8N2K3M',
            '91320100MA5G8N2K3N',
            '91610100MA5G8N2K3P',
            '91500100MA5G8N2K3Q',
            '91120000MA5G8N2K3R'
        ],
        'industry': [
            'retail', 'manufacturing', 'trade', 'technology', 
            'construction', 'trade', 'technology', 'manufacturing'
        ],
        'on_time_rate': [0.92, 0.78, 0.65, 0.88, 0.45, 0.70, 0.95, 0.55],
        'avg_overdue_days': [8, 25, 40, 12, 75, 35, 3, 55],
        'max_overdue_amount': [0.03, 0.15, 0.25, 0.08, 0.45, 0.20, 0.01, 0.30],
        'cooperation_years': [4, 3, 2, 5, 1, 2, 6, 1.5]
    }
    
    df = pd.DataFrame(data)
    output_path = 'data/client_list.xlsx'
    os.makedirs('data', exist_ok=True)
    df.to_excel(output_path, index=False)
    print(f"✅ 演示数据已生成: {output_path}")
    print(f"   共 {len(df)} 条客户记录")

if __name__ == "__main__":
    create_demo_excel()
