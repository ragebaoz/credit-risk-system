#!/usr/bin/env python3
"""
浏览器模式演示
使用爱企查 SVIP 账号通过浏览器抓取真实企业数据

前置要求：
1. 已安装 Chrome 浏览器
2. 已在 Chrome 中登录爱企查 SVIP 账号
3. Playwright 已安装: pip install playwright

使用方式：
    # 可视化模式（首次运行建议，可观察浏览器行为）
    python scripts/demo_browser.py --company "北京百度网讯科技有限公司"

    # 无头模式（后台运行）
    python scripts/demo_browser.py --company "某某公司" --headless
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.collectors.browser_aiqicha import AiQichaBrowserCollector, AiQichaConfig
from src.evaluation.client_eval import ClientEvaluator, print_report


def main():
    parser = argparse.ArgumentParser(description='爱企查浏览器抓取演示')
    parser.add_argument('--company', required=True, help='企业名称')
    parser.add_argument('--credit-code', help='统一社会信用代码')
    parser.add_argument('--headless', action='store_true', help='无头模式')
    parser.add_argument('--slow-mo', type=int, default=500, help='操作间隔毫秒')
    parser.add_argument('--evaluate', action='store_true', help='抓取后执行信用评估')
    parser.add_argument('--industry', help='行业类型')
    parser.add_argument('--internal-data', help='内部交易数据JSON字符串')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("爱企查浏览器数据抓取演示")
    print("=" * 70)
    print(f"目标企业: {args.company}")
    print(f"模式: {'无头' if args.headless else '可视化'}")
    print("-" * 70)
    
    # 1. 直接抓取原始数据
    config = AiQichaConfig(
        headless=args.headless,
        slow_mo=args.slow_mo,
        timeout=20000
    )
    
    collector = AiQichaBrowserCollector(config)
    raw_data = collector.collect(args.company, args.credit_code)
    
    if not raw_data:
        print("\n❌ 抓取失败，请检查:")
        print("   1. Chrome 中是否已登录爱企查 SVIP 账号")
        print("   2. 企业名称是否准确")
        print("   3. 网络连接是否正常")
        return
    
    print("\n✅ 抓取成功！原始数据:")
    print("-" * 70)
    for k, v in raw_data.items():
        if not k.startswith('_'):
            print(f"  {k}: {v}")
    
    # 2. 执行完整评估（可选）
    if args.evaluate:
        print("\n" + "=" * 70)
        print("执行信用评估...")
        print("=" * 70)
        
        evaluator = ClientEvaluator(use_browser=True, headless=args.headless)
        
        import json
        internal_data = None
        if args.internal_data:
            try:
                internal_data = json.loads(args.internal_data)
            except:
                pass
        
        result = evaluator.evaluate(
            name=args.company,
            credit_code=args.credit_code,
            industry=args.industry,
            internal_data=internal_data,
            save=False
        )
        
        print_report(result)


if __name__ == "__main__":
    main()
