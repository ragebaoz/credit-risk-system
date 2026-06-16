#!/usr/bin/env python3
"""独立进程：CDP 天眼查抓取"""
import sys
import os
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.collectors.opencli_tianyancha import CDPTianYanChaCollector

ENTITIES = [
    {"ka": "KA凯知乐",       "brand": "凯知乐",   "company": "凯知乐贸易（天津）有限公司"},
    {"ka": "KA玩具反斗城",   "brand": "反斗城",   "company": "玩具反斗城（中国）商贸有限公司"},
    {"ka": "KA浙江凯蓝",     "brand": "TGP",      "company": "浙江凯畔商贸有限公司"},
    {"ka": "KA浙江凯蓝",     "brand": "伶俐",     "company": "浙江凯畔商贸有限公司"},
    {"ka": "KA浙江凯蓝",     "brand": "伶俐",     "company": "浙江盛伶商贸有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "南京万兴商业管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "南京万好供应链管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "南京万优供应链管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "南京万昌供应链管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "南京万灿供应链管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "泰州万拓供应链管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "万辰",     "company": "南京万权商业管理有限公司"},
    {"ka": "KA万辰集团",     "brand": "老婆大人", "company": "宁波巨库商贸有限公司"},
    {"ka": "KA上海寰越",     "brand": "A2",       "company": "上海寰越电子商务有限公司"},
]

results = []
collector = CDPTianYanChaCollector()
for item in ENTITIES:
    print(f"[{item['ka']}] {item['company']}", flush=True)
    try:
        data = collector.collect(item['company'])
        results.append({"ka": item['ka'], "brand": item['brand'], "company": item['company'], "data": data})
        print(f"  OK", flush=True)
    except Exception as e:
        print(f"  ERR: {e}", flush=True)
        results.append({"ka": item['ka'], "brand": item['brand'], "company": item['company'], "data": {}})

with open("/tmp/ka_tianyancha.json", "w") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("SAVED /tmp/ka_tianyancha.json")
