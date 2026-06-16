#!/usr/bin/env python3
import sys
import re
import asyncio
sys.path.insert(0, "/Users/yuxuanyu/credit-risk-system")

async def main():
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        
        # 打开名创优品详情页
        await page.goto("https://www.tianyancha.com/search?key=名创优品", wait_until="networkidle")
        await asyncio.sleep(2)
        
        first_result = await page.query_selector(".search-item .name a")
        if first_result:
            href = await first_result.get_attribute('href')
            if href:
                await page.goto(f"https://www.tianyancha.com{href}", wait_until="networkidle")
                await asyncio.sleep(3)
        
        # 打印页面文本前3000字符，看包含哪些信息
        text = await page.evaluate("() => document.body.innerText")
        print("=== 页面文本片段（前3000字）===")
        print(text[:3000])
        print("\n=== 关键词搜索 ===")
        
        keywords = ['实缴资本', '参保人数', '天眼评分', '评分', '人员规模', '工商信息']
        for kw in keywords:
            idx = text.find(kw)
            if idx >= 0:
                snippet = text[max(0, idx-50):idx+100]
                print(f"\n'{kw}' 找到，上下文: ...{snippet}...")
            else:
                print(f"'{kw}' 未找到")
        
        # 尝试滚动页面加载更多内容
        print("\n=== 滚动页面后 ===")
        await page.evaluate("window.scrollTo(0, 1000)")
        await asyncio.sleep(2)
        text2 = await page.evaluate("() => document.body.innerText")
        for kw in ['实缴资本', '参保人数', '天眼评分']:
            idx = text2.find(kw)
            if idx >= 0:
                snippet = text2[max(0, idx-50):idx+100]
                print(f"'{kw}' 找到: ...{snippet}...")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
