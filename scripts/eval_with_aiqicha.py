#!/usr/bin/env python3
"""
爱企查交互式评估脚本
运行后弹出 Chrome 窗口，完成滑块验证后按回车，自动抓取并评估
"""
import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from playwright.sync_api import sync_playwright
from src.evaluation.client_eval import ClientEvaluator, print_report


def main():
    company_name = "深圳市力达动漫有限公司"
    credit_code = "91440300MA5DLEDH2K"
    
    print("=" * 70)
    print("爱企查 SVIP 自动评估")
    print("=" * 70)
    print(f"目标公司: {company_name}")
    print(f"信用代码: {credit_code}")
    print()
    print("步骤:")
    print("  1. 即将弹出 Chrome 窗口")
    print("  2. 如果看到滑块验证，请手动拖动完成")
    print("  3. 脚本会自动等待 20 秒后继续抓取")
    print("=" * 70)
    
    with sync_playwright() as p:
        # 启动可视化 Chrome
        print("\n[1/4] 启动 Chrome...")
        browser = p.chromium.launch(
            channel='chrome',
            headless=False,
            slow_mo=300,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        
        # 访问爱企查详情页（从已知 pid 直接进，减少搜索步骤）
        print("[2/4] 打开爱企查详情页...")
        url = "https://aiqicha.baidu.com/detail/compinfo?pid=18625011065870"
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(2)
        
        print(f"\n👉 当前标题: {page.title()}")
        print(f"👉 当前URL: {page.url}")
        
        body_text = page.inner_text("body")
        if "验证" in page.title() or "拖动" in body_text or "安全验证" in body_text:
            print("\n⚠️ 检测到安全验证，请在 Chrome 窗口中拖动滑块！")
            print("   脚本将在 20 秒后自动继续...")
            time.sleep(20)
        else:
            print("\n✅ 页面正常加载")
            print("   等待 5 秒确保页面稳定...")
            time.sleep(5)
        
        # 重新获取页面内容
        print("\n[3/4] 抓取页面数据...")
        page.reload(wait_until="networkidle")
        time.sleep(3)
        
        # 滚动加载全部内容
        for i in range(6):
            page.evaluate("window.scrollBy(0, 1000)")
            time.sleep(0.5)
        
        full_text = page.inner_text("body") or ""
        html = page.content()
        
        # 保存原始页面
        with open("/tmp/aiqicha_eval_page.html", "w", encoding="utf-8") as f:
            f.write(html)
        with open("/tmp/aiqicha_eval_text.txt", "w", encoding="utf-8") as f:
            f.write(full_text)
        
        print("✅ 页面已保存到 /tmp/aiqicha_eval_page.html")
        
        # 解析关键数据
        import re
        raw = {}
        
        def extract(patterns, text):
            for p in patterns:
                m = re.search(p, text)
                if m:
                    return m.group(1).strip()
            return ""
        
        def extract_num(patterns, text):
            for p in patterns:
                m = re.search(p, text)
                if m:
                    try:
                        return int(m.group(1))
                    except:
                        pass
            return 0
        
        raw["established_date"] = extract([
            r"成立日期\s*[:：]\s*([^\n]+)",
            r"成立时间\s*[:：]\s*([^\n]+)",
        ], full_text)
        
        raw["registered_capital"] = extract([
            r"注册资本\s*[:：]\s*([^\n]+)",
        ], full_text)
        
        raw["paid_in_capital"] = extract([
            r"实缴资本\s*[:：]\s*([^\n]+)",
        ], full_text)
        
        raw["status"] = extract([
            r"经营状态\s*[:：]\s*([^\n]+)",
            r"企业状态\s*[:：]\s*([^\n]+)",
            r"登记状态\s*[:：]\s*([^\n]+)",
        ], full_text)
        
        # 风险数据
        raw["abnormal_count"] = extract_num([r"经营异常\s*[:：]?\s*(\d+)"], full_text)
        raw["penalty_count"] = extract_num([r"行政处罚\s*[:：]?\s*(\d+)"], full_text)
        raw["lawsuit_count"] = extract_num([r"司法案件|法律诉讼\s*[:：]?\s*(\d+)"], full_text)
        raw["dishonest_count"] = extract_num([r"失信信息|失信被执行人\s*[:：]?\s*(\d+)"], full_text)
        raw["pledge_count"] = extract_num([r"股权冻结|股权出质|股权质押\s*[:：]?\s*(\d+)"], full_text)
        raw["negative_news"] = extract_num([r"负面舆情|舆情信息\s*[:：]?\s*(\d+)"], full_text)
        
        print("\n[4/4] 解析到的数据:")
        for k, v in raw.items():
            if v:
                print(f"  {k}: {v}")
        
        # 标准化
        def parse_years(date_str):
            if not date_str:
                return 0
            from datetime import datetime
            for fmt in ("%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return round((datetime.now() - dt).days / 365.25, 1)
                except:
                    continue
            m = re.search(r"(\d{4})", date_str)
            if m:
                dt = datetime(int(m.group(1)), 1, 1)
                return round((datetime.now() - dt).days / 365.25, 1)
            return 0
        
        def parse_capital(s):
            if not s:
                return 0
            nums = re.findall(r"[\d.]+", str(s).replace(",", ""))
            if not nums:
                return 0
            val = float(nums[0])
            if "万" in s:
                val *= 10000
            if "亿" in s:
                val *= 100000000
            return val
        
        data = {
            "established_years": parse_years(raw.get("established_date", "")),
            "registered_capital": parse_capital(raw.get("registered_capital", "")),
            "paid_in_capital_ratio": 0.0,  # 未公开或解析失败时
            "abnormal_records": raw.get("abnormal_count", 0),
            "penalty_records": raw.get("penalty_count", 0),
            "lawsuit_count": raw.get("lawsuit_count", 0),
            "dishonest_records": raw.get("dishonest_count", 0),
            "pledge_freeze": raw.get("pledge_count", 0),
            "negative_news": raw.get("negative_news", 0),
        }
        
        # 实缴比例
        paid = parse_capital(raw.get("paid_in_capital", ""))
        reg = data["registered_capital"]
        if paid > 0 and reg > 0:
            data["paid_in_capital_ratio"] = round(paid / reg, 2)
        
        browser.close()
        
        print("\n" + "=" * 70)
        print("爱企查数据抓取完成，执行评估...")
        print("=" * 70)
        
        # 执行评估（使用抓取的真实数据）
        evaluator = ClientEvaluator()
        
        # 内部交易数据需要你替换为真实值，这里用默认值演示
        internal_data = {
            "on_time_rate": 0.90,      # ← 替换为你的真实回款准时率
            "avg_overdue_days": 10,     # ← 替换为真实平均逾期天数
            "max_overdue_amount": 0.03, # ← 替换为真实最大逾期占比
            "cooperation_years": 2,     # ← 替换为真实合作年限
        }
        
        result = evaluator.evaluate(
            name=company_name,
            credit_code=credit_code,
            internal_data={**data, **internal_data},
            save=True
        )
        
        print_report(result)
        
        print("\n" + "=" * 70)
        print("评估完成！")
        print("=" * 70)
        print(f"\n📄 原始页面已保存: /tmp/aiqicha_eval_page.html")
        print("💡 提示: 如果某些字段抓取为空，可以打开 HTML 文件查看页面结构")
        print("   然后告诉我，我帮你调整解析逻辑")


if __name__ == "__main__":
    main()
