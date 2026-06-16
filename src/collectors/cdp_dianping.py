"""
大众点评收集器 — CDP 直连用户 Chrome 方案

绑定用户本地 Chrome（localhost:9222），
新建 tab 搜索大众点评门店数量。
"""
import re
import time
import urllib.parse
from typing import Dict, Any, Optional

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class CDPDianPingCollector:
    """基于 CDP 直连用户 Chrome 的大众点评收集器"""

    CDP_ENDPOINT = "http://localhost:9222"

    # 默认搜索2个代表性城市
    DEFAULT_CITIES = {
        "上海": 1,
        "深圳": 7,
    }

    def __init__(self, cities: Optional[Dict[str, int]] = None):
        self.cities = cities or self.DEFAULT_CITIES

    def collect(self, keyword: str) -> Dict[str, Any]:
        """
        搜索大众点评门店数量。

        :param keyword: 搜索关键词（品牌名或公司名）
        :return: {
            "dp_store_count": int,      # 总门店数（各城市之和）
            "dp_city_breakdown": dict,   # 各城市明细
            "dp_error": str,             # 错误信息（如有）
        }
        """
        if not PLAYWRIGHT_AVAILABLE:
            print("[大众点评-CDP] Playwright 未安装，跳过")
            return {"dp_store_count": None, "dp_error": "playwright_not_installed"}

        p = sync_playwright().start()
        try:
            browser = p.chromium.connect_over_cdp(self.CDP_ENDPOINT)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            print(f"[大众点评-CDP] 新tab已创建，搜索: {keyword}")

            total_stores = 0
            city_breakdown = {}
            error_msg = None

            for city_name, city_id in self.cities.items():
                try:
                    encoded = urllib.parse.quote(keyword)
                    url = f"https://www.dianping.com/search/keyword/{city_id}/0_{encoded}"
                    print(f"[大众点评-CDP] 导航: {url}")
                    page.goto(url, wait_until="domcontentloaded")
                    time.sleep(4)

                    text = page.inner_text("body") or ""
                    current_url = page.url

                    # 检查是否被跳转到登录页
                    if "account.dianping.com" in current_url or "pclogin" in current_url:
                        error_msg = "未登录，请先扫码登录大众点评"
                        print(f"[大众点评-CDP] ⚠️ {error_msg}")
                        city_breakdown[city_name] = {"store_count": 0, "error": "not_logged_in"}
                        continue

                    # 检查验证码
                    if "verify.meituan.com" in current_url:
                        error_msg = "触发验证码"
                        print(f"[大众点评-CDP] ⚠️ {error_msg}")
                        city_breakdown[city_name] = {"store_count": 0, "error": "captcha"}
                        continue

                    # 提取门店数
                    count = 0
                    match = re.search(r'找到\s*([\d,]+)\s*家', text)
                    if not match:
                        match = re.search(r'共为您找到\s*([\d,]+)\s*个', text)
                    if match:
                        count = int(match.group(1).replace(',', ''))
                        total_stores += count
                        print(f"[大众点评-CDP]   {city_name}: {count}家")
                    else:
                        print(f"[大众点评-CDP]   {city_name}: 未找到门店数")

                    city_breakdown[city_name] = {"store_count": count}

                except Exception as e:
                    print(f"[大众点评-CDP]   {city_name} ERR: {e}")
                    city_breakdown[city_name] = {"store_count": 0, "error": str(e)}

            result = {
                "dp_store_count": total_stores,
                "dp_city_breakdown": city_breakdown,
            }
            if error_msg:
                result["dp_error"] = error_msg

            print(f"[大众点评-CDP] 总计: {total_stores}家")
            return result

        except Exception as e:
            print(f"[大众点评-CDP] 连接异常: {e}")
            return {"dp_store_count": None, "dp_error": str(e)}
        finally:
            p.stop()


# 兼容旧接口的 Enterprise 风格封装
class DianPingEnterpriseCollector:
    """兼容 enterprise_collector 接口的封装"""

    def __init__(self, cities: Optional[Dict[str, int]] = None):
        self._inner = CDPDianPingCollector(cities=cities)

    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        """
        按企业名称搜索大众点评门店。
        参数顺序兼容 enterprise_collector 接口。
        """
        return self._inner.collect(company_name)
