#!/usr/bin/env python3
"""
大众点评门店抓取脚本（OpenCLI 版本）
利用 OpenCLI 的 Chrome Extension 模式复用用户日常浏览器，stealth 更强。

用法:
    python scripts/dianping_search.py "名创优品"
    python scripts/dianping_search.py "潮品挚尚"
"""

import json
import random
import sys
import time
from typing import Any, Dict, List, Optional

# 把项目根目录加入路径
sys.path.insert(0, "/Users/yuxuanyu/credit-risk-system")

from src.collectors.opencli_browser import OpenCLIBrowser

# ------------------------------------------------------------------
# 35 个重点城市
# ------------------------------------------------------------------
DIANPING_CITIES = {
    1: "上海", 2: "北京", 3: "杭州", 4: "广州", 5: "南京",
    7: "深圳", 8: "成都", 9: "重庆", 10: "天津", 11: "宁波",
    13: "无锡", 15: "厦门", 16: "武汉", 17: "西安", 19: "大连",
    21: "青岛", 22: "济南", 23: "海口", 24: "石家庄", 35: "太原",
    46: "呼和浩特", 70: "长春", 79: "哈尔滨", 92: "徐州",
    93: "常州", 94: "南通", 101: "温州", 102: "嘉兴",
    104: "绍兴", 105: "金华", 108: "台州", 110: "合肥",
    129: "泉州", 130: "中山", 134: "南昌", 135: "珠海",
    145: "淄博", 148: "烟台", 149: "潍坊", 152: "沈阳",
    160: "郑州", 162: "阳泉", 167: "南宁",
}

# 新城市可以通过命令行参数传入: {"44": "福州", "107": "贵阳"}


def _url_encode(text: str) -> str:
    import urllib.parse
    return urllib.parse.quote(text)


def _extract_js() -> str:
    """在大众点评搜索结果页提取数据的 JS。"""
    return """
(() => {
    const data = {
        store_count: null,
        paused_count: 0,
        avg_rating: null,
        total_reviews: null,
        avg_price: null,
        high_end_ratio: null,
        stores: [],
    };
    const html = document.body.innerText;

    // 1. 总门店数
    const totalMatch = html.match(/找到\\s*([\\d,]+)\\s*家/);
    if (totalMatch) {
        data.store_count = parseInt(totalMatch[1].replace(/,/g, ''));
    }

    // 2. 暂停营业数
    const pausedMatch = html.match(/暂停营业\\s*([\\d,]+)/);
    if (pausedMatch) {
        data.paused_count = parseInt(pausedMatch[1].replace(/,/g, ''));
    }

    // 3. 从列表项提取评分/评论数/人均
    const items = document.querySelectorAll('[class*="shop-list"] > div, .shop-list > div, [class*="shop"]');
    let ratingSum = 0, ratingCount = 0;
    let reviewSum = 0, reviewCount = 0;
    let priceSum = 0, priceCount = 0;
    let highEndCount = 0;

    items.forEach(item => {
        const text = item.innerText || '';

        const ratingMatch = text.match(/([\\d.]+)\\s*分?/);
        if (ratingMatch) {
            const r = parseFloat(ratingMatch[1]);
            if (r >= 1 && r <= 5) {
                ratingSum += r; ratingCount++;
            }
        }

        const reviewMatch = text.match(/([\\d,]+)\\s*条评价/);
        if (reviewMatch) {
            const n = parseInt(reviewMatch[1].replace(/,/g, ''));
            reviewSum += n; reviewCount++;
        }

        const priceMatch = text.match(/人均\\s*¥?\\s*([\\d,]+)/);
        if (priceMatch) {
            const p = parseInt(priceMatch[1].replace(/,/g, ''));
            priceSum += p; priceCount++;
            if (p >= 100) highEndCount++;
        }
    });

    if (ratingCount > 0) data.avg_rating = parseFloat((ratingSum / ratingCount).toFixed(2));
    if (reviewCount > 0) data.total_reviews = Math.round(reviewSum / reviewCount);
    if (priceCount > 0) {
        data.avg_price = Math.round(priceSum / priceCount);
        data.high_end_ratio = parseFloat((highEndCount / priceCount).toFixed(2));
    }

    return data;
})()
    """.strip()


def search_company(keyword: str, city_id: int, browser: OpenCLIBrowser) -> Dict[str, Any]:
    """
    按城市搜索门店，返回门店数据。
    使用已初始化的 browser 实例（复用同一个浏览器 session）。
    """
    city_name = DIANPING_CITIES.get(city_id, f"city_{city_id}")
    print(f"  [{city_name}] 搜索中...", end=" ", flush=True)

    # 1. 先到首页（刷新 cookie / 登录态）
    browser.goto("https://www.dianping.com", settle_ms=2000)

    # 2. 随机滚动一下（模拟真人浏览首页）
    browser.scroll("down", random.randint(300, 800))
    time.sleep(random.uniform(0.5, 1.5))

    # 3. 导航到搜索结果页
    encoded_kw = _url_encode(keyword)
    search_url = f"https://www.dianping.com/search/keyword/{city_id}/0_{encoded_kw}"
    browser.goto(search_url, settle_ms=4000)

    # 4. 检查是否被拦截
    current_url = browser.eval("window.location.href")
    if isinstance(current_url, str) and "verify.meituan.com" in current_url:
        print("❌ 触发验证码")
        return {
            "city_id": city_id,
            "city_name": city_name,
            "error": "captcha_required",
            "captcha_url": current_url,
            "store_count": None,
            "paused_count": 0,
        }

    # 5. 随机滚动搜索结果页（模拟浏览）
    browser.scroll("down", random.randint(500, 1000))
    time.sleep(random.uniform(1.0, 2.0))

    # 6. 提取数据
    result = browser.eval(_extract_js())
    if not isinstance(result, dict):
        result = {}

    result["city_id"] = city_id
    result["city_name"] = city_name

    store_count = result.get("store_count")
    if store_count is not None:
        print(f"✅ 找到 {store_count} 家")
    else:
        print("⚠️ 未找到数量")

    return result


def search_all_cities(keyword: str, city_ids: Optional[List[int]] = None) -> Dict[str, Any]:
    """
    遍历多个城市搜索门店，汇总数据。
    返回 {"total_store_count", "total_paused_count", "city_results", ...}
    """
    if city_ids is None:
        city_ids = list(DIANPING_CITIES.keys())

    results = []
    total_store_count = 0
    total_paused_count = 0
    captcha_hits = 0

    print(f"\n🔍 搜索「{keyword}」，共 {len(city_ids)} 个城市\n")

    with OpenCLIBrowser() as browser:
        for i, city_id in enumerate(city_ids):
            # 城市间随机延迟（模拟真人不会连续搜索）
            if i > 0:
                delay = random.uniform(3.0, 8.0)
                print(f"  ⏳ 等待 {delay:.1f}s...")
                time.sleep(delay)

            try:
                data = search_company(keyword, city_id, browser)
            except Exception as e:
                print(f"❌ 异常: {e}")
                data = {
                    "city_id": city_id,
                    "city_name": DIANPING_CITIES.get(city_id, f"city_{city_id}"),
                    "error": str(e),
                    "store_count": None,
                    "paused_count": 0,
                }

            results.append(data)

            if data.get("error") == "captcha_required":
                captcha_hits += 1
                if captcha_hits >= 2:
                    print("\n⚠️ 多次触发验证码，停止搜索。建议：")
                    print("   1. 在浏览器中手动完成滑块验证")
                    print("   2. 等待 2-4 小时后重试")
                    print("   3. 使用代理 IP")
                    break
                continue

            store_count = data.get("store_count") or 0
            paused_count = data.get("paused_count") or 0
            total_store_count += store_count
            total_paused_count += paused_count

    # 汇总
    summary = {
        "keyword": keyword,
        "total_store_count": total_store_count,
        "total_paused_count": total_paused_count,
        "cities_searched": len(results),
        "captcha_hits": captcha_hits,
        "city_results": results,
    }

    # 计算平均质量指标（跨所有有数据的城市）
    ratings = [r.get("avg_rating") for r in results if r.get("avg_rating")]
    reviews = [r.get("total_reviews") for r in results if r.get("total_reviews")]
    prices = [r.get("avg_price") for r in results if r.get("avg_price")]
    high_ends = [r.get("high_end_ratio") for r in results if r.get("high_end_ratio")]

    if ratings:
        summary["avg_rating"] = round(sum(ratings) / len(ratings), 2)
    if reviews:
        summary["avg_total_reviews"] = round(sum(reviews) / len(reviews))
    if prices:
        summary["avg_price"] = round(sum(prices) / len(prices))
    if high_ends:
        summary["high_end_ratio"] = round(sum(high_ends) / len(high_ends), 2)

    return summary


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/dianping_search.py <关键词> [城市ID列表]")
        print("示例: python scripts/dianping_search.py '名创优品'")
        print("示例: python scripts/dianping_search.py '潮品挚尚' '1,2,7,8'")
        sys.exit(1)

    keyword = sys.argv[1]

    # 可选：指定城市 ID 列表
    if len(sys.argv) >= 3:
        city_ids = [int(x.strip()) for x in sys.argv[2].split(",")]
    else:
        city_ids = None

    result = search_all_cities(keyword, city_ids)

    print("\n" + "=" * 60)
    print(f"📊 「{keyword}」搜索结果汇总")
    print("=" * 60)
    print(f"   总门店数: {result['total_store_count']}")
    print(f"   暂停营业: {result['total_paused_count']}")
    if result.get("avg_rating"):
        print(f"   平均评分: {result['avg_rating']}")
    if result.get("avg_total_reviews"):
        print(f"   平均评论: {result['avg_total_reviews']}")
    if result.get("avg_price"):
        print(f"   平均客单: ¥{result['avg_price']}")
    print(f"   搜索城市: {result['cities_searched']}")
    print(f"   验证码次数: {result['captcha_hits']}")
    print("=" * 60)

    # 保存结果
    output_path = f"/tmp/dianping_{keyword.replace(' ', '_')}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 结果已保存: {output_path}")


if __name__ == "__main__":
    main()
