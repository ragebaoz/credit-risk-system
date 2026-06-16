#!/usr/bin/env python3
"""
爱企查可视化抓取脚本
遇到滑块验证时，请在弹出的 Chrome 窗口中手动拖动滑块
验证通过后按回车，脚本会继续自动抓取
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from playwright.sync_api import sync_playwright


def main():
    company = "深圳市力达动漫有限公司"
    pid = "18625011065870"
    
    print("=" * 60)
    print("爱企查可视化抓取")
    print("=" * 60)
    print(f"目标公司: {company}")
    print("\n即将弹出 Chrome 窗口...")
    print("如果遇到滑块验证，请手动拖动完成！")
    print("验证通过后，回到这里按回车继续...")
    print("=" * 60)
    
    with sync_playwright() as p:
        # 启动可视化 Chrome（使用你的登录态）
        browser = p.chromium.launch(
            channel='chrome',
            headless=False,
            slow_mo=500,
            args=['--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        
        # 访问爱企查详情页
        url = f"https://aiqicha.baidu.com/detail/compinfo?pid={pid}"
        print(f"\n正在打开: {url}")
        page.goto(url, wait_until='domcontentloaded')
        
        print("\n👉 请查看 Chrome 窗口")
        print("   - 如果页面正常显示，直接按回车")
        print("   - 如果遇到滑块，拖动完成后按回车")
        input("\n按回车继续...")
        
        # 等待页面稳定
        time.sleep(2)
        
        print(f"\n当前标题: {page.title()}")
        print(f"当前URL: {page.url}")
        
        # 抓取页面文本
        body_text = page.inner_text('body')
        
        if '验证' in body_text or '拖动' in body_text:
            print("\n⚠️ 仍然需要验证，请完成验证后再次按回车")
            input("按回车继续...")
            body_text = page.inner_text('body')
        
        # 保存结果
        output_path = '/tmp/aiqicha_result.txt'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"标题: {page.title()}\n")
            f.write(f"URL: {page.url}\n")
            f.write("=" * 60 + "\n")
            f.write(body_text)
        
        # 同时保存 HTML
        with open('/tmp/aiqicha_result.html', 'w', encoding='utf-8') as f:
            f.write(page.content())
        
        print(f"\n✅ 抓取完成！")
        print(f"   文本结果: {output_path}")
        print(f"   HTML结果: /tmp/aiqicha_result.html")
        print(f"\n页面内容预览（前2000字）:\n{body_text[:2000]}")
        
        browser.close()


if __name__ == "__main__":
    main()
