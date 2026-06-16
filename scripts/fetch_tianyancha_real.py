#!/usr/bin/env python3
import sys
import json
import re
import asyncio
sys.path.insert(0, "/Users/yuxuanyu/credit-risk-system")

async def main():
    from playwright.async_api import async_playwright
    
    # 企业名称 -> 天眼查company_id
    companies = {
        "名创优品": "3111962218",
        "潮品挚尚": None,  # 需要搜索获取
        "力达动漫": None,
    }
    
    results = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        
        for name, cid in companies.items():
            print(f"\n{'='*50}")
            print(f"抓取: {name}")
            print(f"{'='*50}")
            
            try:
                # 如果没有company_id，先搜索
                if not cid:
                    await page.goto(f"https://www.tianyancha.com/search?key={name}", wait_until="networkidle")
                    await asyncio.sleep(2)
                    
                    # 从页面脚本中提取第一个企业的id
                    html = await page.content()
                    m = re.search(r'"id":(\d+),"name":"[^"]*' + name, html)
                    if m:
                        cid = m.group(1)
                        print(f"  找到ID: {cid}")
                    else:
                        print(f"  未找到ID，跳过")
                        continue
                
                # 直接访问详情页
                await page.goto(f"https://www.tianyancha.com/company/{cid}", wait_until="networkidle")
                await asyncio.sleep(4)
                
                text = await page.evaluate("() => document.body.innerText")
                
                data = {}
                
                # 注册资本
                m = re.search(r'注册资本[:：\s]*([\d,.]+万?[^\n]*)', text)
                data['registered_capital'] = m.group(1).strip() if m else None
                
                # 实缴资本
                m = re.search(r'实缴资本[:：\s]*([\d,.]+万?[^\n]*)', text)
                data['paid_in_capital'] = m.group(1).strip() if m else None
                
                # 成立日期
                m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
                data['established_date'] = m.group(1) if m else None
                
                # 参保人数
                m = re.search(r'参保人数[:：\s]*(\d+)', text)
                data['insured_count'] = int(m.group(1)) if m else None
                
                # 天眼评分
                m = re.search(r'天眼评分[:：\s]*(\d+)', text)
                data['tianyancha_score'] = int(m.group(1)) if m else None
                
                # 经营异常
                m = re.search(r'经营异常[:：\s]*(\d+)', text)
                data['abnormal_count'] = int(m.group(1)) if m else 0
                
                # 行政处罚
                m = re.search(r'行政处罚[:：\s]*(\d+)', text)
                data['penalty_count'] = int(m.group(1)) if m else 0
                
                # 司法案件
                m = re.search(r'司法案件[:：\s]*(\d+)', text)
                data['lawsuit_count'] = int(m.group(1)) if m else 0
                
                # 被执行人
                m = re.search(r'被执行人[:：\s]*(\d+)', text)
                data['executed_count'] = int(m.group(1)) if m else 0
                
                # 失信信息
                m = re.search(r'失信信息[:：\s]*(\d+)', text)
                data['dishonest_count'] = int(m.group(1)) if m else 0
                
                # 自身风险
                m = re.search(r'自身风险[:：\s]*(\d+)', text)
                data['self_risk_count'] = int(m.group(1)) if m else 0
                
                # 周边风险
                m = re.search(r'周边风险[:：\s]*(\d+)', text)
                data['around_risk_count'] = int(m.group(1)) if m else 0
                
                results[name] = data
                for k, v in data.items():
                    print(f"  {k}: {v}")
                    
            except Exception as e:
                print(f"  抓取失败: {e}")
                import traceback
                traceback.print_exc()
        
        await browser.close()
    
    with open('/tmp/tianyancha_real_data.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\n✅ 数据已保存到 /tmp/tianyancha_real_data.json")

if __name__ == "__main__":
    asyncio.run(main())
