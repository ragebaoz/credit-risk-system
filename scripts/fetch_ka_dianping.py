#!/usr/bin/env python3
"""独立进程：CDP 大众点评门店抓取"""
import sys
import os
import json
import re
import urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

DP_KEYWORDS = {
    "KA凯知乐":       {"凯知乐": "凯知乐"},
    "KA玩具反斗城":   {"反斗城": "玩具反斗城"},
    "KA浙江凯蓝":     {"TGP": "The Green Party", "伶俐": "伶俐"},
    "KA万辰集团":     {"万辰": "万辰零食", "老婆大人": "老婆大人"},
    "KA上海寰越":     {"A2": "A2"},
}
CORE_CITIES = {"上海": 1, "杭州": 3}

p = sync_playwright().start()
browser = p.chromium.connect_over_cdp("http://localhost:9222")
context = browser.contexts[0] if browser.contexts else browser.new_context()
page = context.new_page()
print("新tab已创建，请在Chrome中查看", flush=True)

dp_results = {}

for ka_name, brands in DP_KEYWORDS.items():
    total_stores = 0
    city_breakdown = {}
    for brand, keyword in brands.items():
        print(f"[{ka_name}] 搜索 {brand}: {keyword}", flush=True)
        for city_name, city_id in CORE_CITIES.items():
            try:
                encoded = urllib.parse.quote(keyword)
                url = f"https://www.dianping.com/search/keyword/{city_id}/0_{encoded}"
                page.goto(url, wait_until="domcontentloaded")
                import time
                time.sleep(4)
                text = page.inner_text("body") or ""
                match = re.search(r'找到\s*([\d,]+)\s*家', text)
                if not match:
                    match = re.search(r'共为您找到\s*([\d,]+)\s*个', text)
                if match:
                    count = int(match.group(1).replace(',', ''))
                    total_stores += count
                    city_breakdown[f"{brand}-{city_name}"] = count
                    print(f"  {city_name}: {count}家", flush=True)
                else:
                    print(f"  {city_name}: 0家", flush=True)
            except Exception as e:
                print(f"  {city_name} ERR: {e}", flush=True)
    dp_results[ka_name] = {
        'total_store_count': total_stores,
        'total_paused_count': 0,
        'city_breakdown': city_breakdown,
    }
    print(f"{ka_name}: {total_stores}家", flush=True)

with open("/tmp/ka_dianping.json", "w") as f:
    json.dump(dp_results, f, ensure_ascii=False, indent=2)
print("SAVED /tmp/ka_dianping.json")
