"""
OpenCLI Browser 封装层
调用 opencli browser CLI 命令进行浏览器自动化操作。
利用 OpenCLI 的 Chrome Extension 模式复用用户日常浏览器， stealth 更强。

用法:
    from src.collectors.opencli_browser import OpenCLIBrowser
    
    browser = OpenCLIBrowser()
    browser.goto("https://www.dianping.com")
    data = browser.eval("document.title")
    browser.close()
"""

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from src.utils.opencli_path import get_opencli_path


# ------------------------------------------------------------------
# 品牌别名映射表（大众点评关键词修正）
# ------------------------------------------------------------------
_DIANPING_BRAND_MAP: Dict[str, str] = {}
_DIANPING_BRAND_MAP_PATH: Optional[str] = None


def _load_brand_map() -> Dict[str, str]:
    """加载品牌别名映射表。如果文件有更新则重新加载。"""
    global _DIANPING_BRAND_MAP, _DIANPING_BRAND_MAP_PATH

    # 可能的配置路径（按优先级）
    candidate_paths = [
        os.path.join(os.path.dirname(__file__), "dianping_brand_map.json"),
        os.path.join(os.path.dirname(__file__), "../../skills/ka-credit-evaluation/references/dianping_brand_map.json"),
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            try:
                mtime = os.path.getmtime(path)
                if _DIANPING_BRAND_MAP_PATH == path and hasattr(_load_brand_map, "_mtime") and _load_brand_map._mtime == mtime:
                    return _DIANPING_BRAND_MAP
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                _DIANPING_BRAND_MAP = {k: v for k, v in data.items() if not k.startswith("_")}
                _DIANPING_BRAND_MAP_PATH = path
                _load_brand_map._mtime = mtime
                return _DIANPING_BRAND_MAP
            except Exception:
                continue
    return {}


def _resolve_brand_alias(simplified: str) -> str:
    """根据品牌别名映射表，将简化后的关键词映射为大众点评搜索词。"""
    brand_map = _load_brand_map()
    return brand_map.get(simplified, simplified)


class OpenCLIBrowser:
    """OpenCLI Browser 封装，通过 CLI 调用实现浏览器自动化。"""

    OPENCLI_BIN = "node"

    def __init__(self, workspace: str = "default"):
        self.workspace = workspace
        self._page_url: Optional[str] = None

    # ------------------------------------------------------------------
    # 内部 helpers
    # ------------------------------------------------------------------
    def _run(self, *args: str, timeout: int = 30) -> str:
        """执行 opencli browser 子命令，返回 stdout。"""
        cmd = [
            self.OPENCLI_BIN,
            get_opencli_path(),
            "browser",
            "--workspace",
            self.workspace,
            *args,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        # OpenCLI 把进度/提示写到 stderr，真正的结果在 stdout
        return result.stdout.strip()

    def _run_json(self, *args: str, timeout: int = 30) -> Any:
        """执行命令并尝试把 stdout 当 JSON 解析。"""
        raw = self._run(*args, timeout=timeout)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw

    # ------------------------------------------------------------------
    # 导航 & 页面操作
    # ------------------------------------------------------------------
    def goto(self, url: str, settle_ms: int = 3000) -> None:
        """导航到指定 URL（用 eval 改 location，比 open 更稳定）。"""
        js = f"window.location.href = '{url}'"
        self.eval(js)
        time.sleep(settle_ms / 1000)
        self._page_url = url

    def back(self) -> None:
        """浏览器后退。"""
        self._run("back")

    def reload(self) -> None:
        """刷新页面。"""
        self.eval("window.location.reload()")
        time.sleep(2)

    # ------------------------------------------------------------------
    # 元素交互
    # ------------------------------------------------------------------
    def click(self, target: str) -> Dict[str, Any]:
        """点击元素，target 可以是 CSS selector 或 OpenCLI 的 ref 索引。"""
        return self._run_json("click", target)  # type: ignore[return-value]

    def type_text(self, target: str, text: str, submit: bool = False) -> Dict[str, Any]:
        """在元素中输入文本。"""
        args = ["type", target, text]
        if submit:
            args.append("--submit")
        return self._run_json(*args)  # type: ignore[return-value]

    def press_key(self, key: str) -> None:
        """按下键盘按键。"""
        self._run("keys", key)

    def scroll(self, direction: str = "down", amount: int = 500) -> None:
        """滚动页面。"""
        self._run("scroll", direction, str(amount))

    def auto_scroll(self, times: int = 3, delay_ms: int = 2000) -> None:
        """自动滚动页面多次（模拟真人浏览）。"""
        self.eval(
            f"""
            (async () => {{
                for (let i = 0; i < {times}; i++) {{
                    window.scrollBy(0, {amount});
                    await new Promise(r => setTimeout(r, {delay_ms}));
                }}
            }})()
            """
        )

    # ------------------------------------------------------------------
    # 数据提取
    # ------------------------------------------------------------------
    def eval(self, js: str, timeout: int = 30) -> Any:
        """在页面执行 JS 并返回结果。"""
        # OpenCLI 的 eval 命令接收 JS 字符串
        # 需要把 JS 包成一行避免换行问题
        single_line = " ".join(js.splitlines())
        return self._run_json("eval", single_line, timeout=timeout)

    def extract(self) -> str:
        """提取页面内容为 markdown（OpenCLI 内置提取）。"""
        return self._run("extract")  # type: ignore[return-value]

    def state(self) -> str:
        """获取页面状态快照。"""
        return self._run("state")

    def get_text(self) -> str:
        """获取页面纯文本内容。"""
        result = self.eval("document.body.innerText")
        return result if isinstance(result, str) else ""

    def get_html(self) -> str:
        """获取页面 HTML。"""
        result = self.eval("document.documentElement.outerHTML")
        return result if isinstance(result, str) else ""

    def screenshot(self, path: Optional[str] = None) -> str:
        """截图，返回 base64 或保存到文件。"""
        args = ["screenshot"]
        if path:
            args.append(path)
        return self._run(*args)

    # ------------------------------------------------------------------
    # 网络 & Cookie
    # ------------------------------------------------------------------
    def start_network_capture(self, pattern: str = "") -> bool:
        """开始捕获网络请求。"""
        result = self._run("network", "start", pattern)
        return "true" in result.lower() or "started" in result.lower()

    def read_network_capture(self) -> List[Dict[str, Any]]:
        """读取捕获的网络请求。"""
        result = self._run_json("network", "read")
        if isinstance(result, list):
            return result
        return []

    def get_cookies(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取当前页面的 cookies。"""
        args = ["get"]
        if domain:
            args.extend(["--domain", domain])
        return self._run_json(*args)  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # 天眼查专用方法
    # ------------------------------------------------------------------
    def tianyancha_search(self, company_name: str) -> Dict[str, Any]:
        """
        在天眼查搜索企业，返回结构化数据。
        1. 先在搜索结果页获取基本信息
        2. 点击第一个结果进入详情页，获取更多字段
        增加：反爬检测、验证码检测、失败重试
        """
        import urllib.parse
        import time
        import random

        encoded = urllib.parse.quote(company_name)
        search_url = f"https://www.tianyancha.com/search?key={encoded}"

        # 随机延迟 2-5 秒，降低反爬概率
        time.sleep(random.uniform(2, 5))

        self.goto(search_url, settle_ms=4000)

        # 检测是否被拦截（验证码/反爬页）
        current_url = self._get_current_url()
        page_text = self.get_text()

        anti_patterns = [
            "antirobot.tianyancha.com",
            "请输入验证码",
            "系统检测到您操作频繁",
            "访问受限",
            "验证码",
            "登录",
        ]
        is_blocked = any(p in current_url or p in page_text for p in anti_patterns)

        if is_blocked:
            print(f"[天眼查] ⚠️ 触发反爬/验证码，等待 15 秒后重试...")
            time.sleep(15)
            # 重试一次
            self.goto(search_url, settle_ms=5000)
            page_text = self.get_text()
            current_url = self._get_current_url()
            is_blocked = any(p in current_url or p in page_text for p in anti_patterns)
            if is_blocked:
                print(f"[天眼查] ❌ 重试后仍被拦截，跳过 {company_name}")
                return {"_error": "blocked_by_antibot", "company_name": company_name}

        # 先获取搜索结果页文本（作为 fallback）
        search_text = page_text
        search_html = self.get_html()

        # 尝试点击第一个结果进入详情页
        detail_text = ""
        try:
            first_link = self.eval("document.querySelector('a[href*=\"/company/\"]')?.href")
            if first_link and isinstance(first_link, str):
                self.goto(first_link, settle_ms=4000)
                detail_text = self.get_text()
        except Exception as e:
            print(f"[天眼查] 进入详情页失败: {e}，使用搜索结果页数据")

        # 合并搜索结果页和详情页的文本进行解析
        combined_text = detail_text + "\n" + search_text if detail_text else search_text
        combined_html = self.get_html() if detail_text else search_html

        return self._parse_tianyancha(combined_text, combined_html, company_name)

    def _parse_tianyancha(self, text: str, html: str, company_name: str) -> Dict[str, Any]:
        """从天眼查页面文本中解析关键数据。"""
        import re
        result = {
            "company_name": company_name,
            "established_years": None,
            "registered_capital": None,
            "paid_in_capital": None,
            "paid_in_capital_ratio": None,
            "abnormal_records": 0,
            "penalty_records": 0,
            "company_status": None,
            "insured_count": None,
            "tianyancha_score": None,
            "self_risk_count": None,
            "around_risk_count": None,
            "lawsuit_count": None,
            "contract_dispute_count": None,
            "dishonest_records": None,
            "executed_count": None,
            "restriction_count": None,
            "pledge_freeze": None,
            "pledge_freeze_count": None,
            "negative_news": None,
            "_source": "tianyancha_opencli",
        }

        # 成立日期
        m = re.search(r'成立日期\s*[:：\t]\s*([^\n]+)', text)
        if m:
            date_str = m.group(1).strip()
            from datetime import datetime
            for fmt in ("%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    result["established_years"] = round((datetime.now() - dt).days / 365.25, 1)
                    break
                except ValueError:
                    continue

        # 注册资本
        m = re.search(r'注册资本\s*[:：\t]\s*([^\n]+)', text)
        if m:
            result["registered_capital"] = self._parse_capital(m.group(1))

        # 实缴资本
        m = re.search(r'实缴资本\s*[:：\t]\s*([^\n]+)', text)
        if m:
            val = m.group(1).strip()
            if val not in ('-', '—', ''):
                result["paid_in_capital"] = self._parse_capital(val)

        if result["registered_capital"] and result["paid_in_capital"]:
            result["paid_in_capital_ratio"] = round(
                result["paid_in_capital"] / result["registered_capital"], 2
            )

        # 工商状态
        m = re.search(r'登记状态\s*[:：\t]\s*([^\n]+)', text)
        if not m:
            m = re.search(r'(存续|在营|开业|注销|吊销)', text)
        if m:
            result["company_status"] = m.group(1).strip()

        # 参保人数
        m = re.search(r'参保人数\s*[:：\t]\s*(\d+)', text)
        if m:
            result["insured_count"] = int(m.group(1))

        # 天眼查评分（旧版叫天眼评分，新版叫科创分）
        m = re.search(r'天眼评分\s*[:：\s]*([\d]+)', text)
        if not m:
            m = re.search(r'科创分\s*[:：\s]*(\d+)', text)
        if m:
            result["tianyancha_score"] = int(m.group(1))

        # 员工人数（详情页）
        m = re.search(r'员工人数\s*[:：\s]*(\d+)', text)
        if m:
            result["insured_count"] = int(m.group(1))

        # 风险统计（从页面文本提取，支持详情页格式）
        patterns = {
            "self_risk_count": r'自身风险\s*(\d+)',
            "around_risk_count": r'周边风险\s*(\d+)',
            "lawsuit_count": r'(?:司法案件|涉及案件)\s*(\d+)',
            "dishonest_records": r'失信被执行人\s*(\d+)',
            "executed_count": r'(?:历史)?被执行人\s*(\d+)',
            "restriction_count": r'限制高消费\s*(\d+)',
            "pledge_freeze_count": r'股权冻结\s*(\d+)',
            "abnormal_records": r'经营异常\s*(\d+)',
            "penalty_records": r'行政处罚\s*(\d+)',
            "negative_news": r'(?:新闻舆情|热点新闻)\s*(\d+)',
        }
        for key, pattern in patterns.items():
            m = re.search(pattern, text)
            if m:
                try:
                    result[key] = int(m.group(1))
                except ValueError:
                    pass

        # 买卖合同纠纷（从页面全文统计关键词出现次数）
        result["contract_dispute_count"] = text.count("买卖合同纠纷")

        # 股权质押比例（简化：取股权冻结/质押数值）
        if result["pledge_freeze_count"]:
            result["pledge_freeze"] = 0.0

        return result

    @staticmethod
    def _parse_capital(capital_str: str) -> float:
        if not capital_str:
            return 0.0
        text = str(capital_str).replace(",", "").replace("，", "")
        nums = re.findall(r"[\d.]+", text)
        if not nums:
            return 0.0
        val = float(nums[0])
        if "万" in text:
            val *= 10000
        if "亿" in text:
            val *= 100000000
        return val

    # ------------------------------------------------------------------
    # 大众点评关键词简化
    # ------------------------------------------------------------------
    @staticmethod
    def _simplify_dianping_keyword(keyword: str) -> str:
        """简化大众点评搜索关键词，去掉公司后缀、地域前缀、业务词，保留品牌名。"""
        import re
        k = keyword.strip().strip('"').strip("'")
        # 去掉常见公司后缀（从长到短）
        suffixes = [
            "供应链管理有限公司", "商业管理有限公司", "商业连锁股份有限公司",
            "企业管理有限公司", "电子商务有限公司", "网络科技有限公司",
            "文化发展有限公司", "文化创意有限公司", "潮流百货有限公司",
            "文体用品有限公司", "儿童用品有限公司", "服饰有限公司",
            "贸易有限公司", "科技有限公司", "百货有限公司",
            "超市连锁经营有限公司", "新零售网络科技有限公司",
            "食品集团股份有限公司", "食品（上海）股份有限公司",
            "商业集团有限公司", "投资股份有限公司", "控股上海有限公司",
            "石油分公司", "南京分公司", "有限公司", "股份有限公司", "股份公司",
        ]
        for suffix in suffixes:
            if k.endswith(suffix):
                k = k[:-len(suffix)].strip()
                break
        # 去掉地域括号
        k = re.sub(r'[（(].*?[）)]', '', k).strip()
        # 去掉完整的地域前缀（包含"市/省/区/县"后缀）
        provinces_full = [
            "上海市","北京市","天津市","重庆市","河北省","山西省","辽宁省","吉林省","黑龙江省",
            "江苏省","浙江省","安徽省","福建省","江西省","山东省","河南省","湖北省","湖南省",
            "广东省","海南省","四川省","贵州省","云南省","陕西省","甘肃省","青海省","台湾省",
            "内蒙古自治区","广西壮族自治区","西藏自治区","宁夏回族自治区","新疆维吾尔自治区",
            "香港特别行政区","澳门特别行政区",
        ]
        cities_full = [
            "深圳市","广州市","杭州市","南京市","苏州市","成都市","武汉市","西安市","郑州市","长沙市",
            "青岛市","大连市","宁波市","厦门市","无锡市","福州市","济南市","合肥市","昆明市","哈尔滨市",
            "长春市","沈阳市","石家庄市","太原市","南昌市","贵阳市","南宁市","兰州市","海口市",
            "乌鲁木齐市","呼和浩特市","银川市","西宁市","拉萨市","东莞市","佛山市","温州市","嘉兴市",
            "烟台市","威海市","潍坊市","淄博市","泰安市","临沂市","徐州市","南通市","常州市",
            "绍兴市","金华市","台州市","惠州市","中山市","珠海市","汕头市","江门市","湛江市",
            "茂名市","肇庆市","清远市","潮州市","揭阳市","云浮市","韶关市","河源市","梅州市",
            "阳江市","汕尾市","东阳市","义乌市","诸暨市","慈溪市","余姚市","瑞安市","乐清市",
            "温岭市","临海市","永康市","兰溪市","海宁市","平湖市","桐乡市",
        ]
        for prefix in provinces_full + cities_full:
            if k.startswith(prefix):
                k = k[len(prefix):].strip()
                break
        else:
            # 如果没有匹配到带后缀的，再尝试不带后缀的
            provinces_short = [
                "上海","北京","天津","重庆","河北","山西","辽宁","吉林","黑龙江",
                "江苏","浙江","安徽","福建","江西","山东","河南","湖北","湖南",
                "广东","海南","四川","贵州","云南","陕西","甘肃","青海","台湾",
                "内蒙古","广西","西藏","宁夏","新疆","香港","澳门",
            ]
            cities_short = [
                "深圳","广州","杭州","南京","苏州","成都","武汉","西安","郑州","长沙",
                "青岛","大连","宁波","厦门","无锡","福州","济南","合肥","昆明","哈尔滨",
                "长春","沈阳","石家庄","太原","南昌","贵阳","南宁","兰州","海口",
                "乌鲁木齐","呼和浩特","银川","西宁","拉萨","东莞","佛山","温州","嘉兴",
                "烟台","威海","潍坊","淄博","泰安","临沂","徐州","南通","常州",
                "绍兴","金华","台州","惠州","中山","珠海","汕头","江门","湛江",
                "茂名","肇庆","清远","潮州","揭阳","云浮","韶关","河源","梅州",
                "阳江","汕尾","东阳","义乌","诸暨","慈溪","余姚","瑞安","乐清",
                "温岭","临海","永康","兰溪","海宁","平湖","桐乡",
            ]
            for prefix in provinces_short + cities_short:
                if k.startswith(prefix):
                    k = k[len(prefix):].strip()
                    break

        # 去掉残留的"市/省/区/县"单字前缀
        if k.startswith("市") or k.startswith("省") or k.startswith("区") or k.startswith("县"):
            k = k[1:].strip()

        # 去掉尾部业务词（保留"零售"，因为"新零售"等可能是品牌名的一部分）
        biz = ["商贸","贸易","投资","控股","供应链","管理","企业","文化","科技",
               "百货","超市","食品","服饰","文具","文体","儿童","潮流","创意",
               "发展","网络","电子","商业","连锁","石油","销售","经营",
               "集团","股份","便利","用品"]
        for word in biz:
            if k.endswith(word):
                remainder = k[:-len(word)].strip()
                if remainder and len(remainder) >= 2:
                    k = remainder
                    break
        # 如果结果为空，回退到原关键词
        if not k:
            k = keyword

        # 查询品牌别名映射表（支持热更新，按文件 mtime 缓存）
        mapped = _resolve_brand_alias(k)
        if mapped and mapped != k:
            print(f"[大众点评] 品牌映射: {k} → {mapped}")
            k = mapped

        return k

    # ------------------------------------------------------------------
    # 大众点评专用方法
    # ------------------------------------------------------------------
    # 卡游核心8城配置
    CITY_CONFIG = {
        "上海": 1,
        "北京": 2,
        "杭州": 3,
        "广州": 4,
        "苏州": 6,
        "深圳": 7,
        "武汉": 16,
        "成都": 8,
    }

    def dianping_search_multi_cities(
        self, keyword: str, cities: Optional[Dict[str, int]] = None
    ) -> Dict[str, Any]:
        """
        智能多城市搜索大众点评门店。
        策略：先搜上海，有结果就停；否则依次搜北京、广州、深圳，避免触发验证码。
        关键词会自动简化（去掉公司后缀）。
        """
        simplified = self._simplify_dianping_keyword(keyword)
        if simplified != keyword:
            print(f"[大众点评] 关键词简化: {keyword} → {simplified}")
            keyword = simplified

        # 智能城市顺序：上海优先，然后北上深广
        city_order = cities or {"上海": 1, "北京": 2, "广州": 4, "深圳": 7}
        city_breakdown = {}
        total_stores = 0
        total_paused = 0

        for city_name, city_id in city_order.items():
            print(f"[大众点评] 搜索 {keyword} @ {city_name} (city_id={city_id})")
            result = self.dianping_search(keyword, city_id)
            city_breakdown[city_name] = result

            sc = result.get("store_count") or 0
            pc = result.get("paused_count") or 0
            total_stores += sc
            total_paused += pc

            # 如果当前城市有结果，停止搜索（避免验证码）
            if sc > 0:
                print(f"[大众点评] {city_name} 找到 {sc} 家，停止搜索")
                break

            # 城市间休息，避免触发风控
            time.sleep(2.5)

        return {
            "total_store_count": total_stores,
            "total_paused_count": total_paused,
            "pause_ratio": round(total_paused / total_stores, 4) if total_stores > 0 else 0.0,
            "city_breakdown": city_breakdown,
            "avg_rating_across_cities": None,
        }


    def dianping_search(self, keyword: str, city_id: int = 7) -> Dict[str, Any]:
        """
        大众点评搜索门店。
        先导航到首页（带登录态），再 eval 改 URL 到搜索结果页。
        返回: {"store_count", "paused_count", "avg_rating", "total_reviews", "avg_price"}
        """
        import urllib.parse

        # 1. 先到首页（确保登录态和 cookie 刷新）
        self.goto("https://www.dianping.com", settle_ms=2000)

        # 2. 构造搜索 URL 并导航
        encoded_kw = urllib.parse.quote(keyword)
        search_url = f"https://www.dianping.com/search/keyword/{city_id}/0_{encoded_kw}"
        self.goto(search_url, settle_ms=4000)

        # 3. 检查是否被拦截（验证码页）
        current_url = self._get_current_url()
        if "verify.meituan.com" in current_url:
            return {
                "error": "captcha_required",
                "message": "触发滑块验证码，需要手动完成验证",
                "captcha_url": current_url,
                "store_count": None,
                "paused_count": 0,
            }

        # 4. 提取搜索结果数据
        result = self.eval(self._dianping_extract_js())
        return result if isinstance(result, dict) else {}

    def _get_current_url(self) -> str:
        """获取当前 URL。"""
        try:
            url = self.eval("window.location.href")
            return url if isinstance(url, str) else ""
        except Exception:
            return ""

    @staticmethod
    def _dianping_extract_js() -> str:
        """返回在大众点评搜索结果页提取门店数的 JS。
        策略：优先从单个 DOM 元素精确匹配，避免全页面文本误抓；
              限制数字位数 1-6 位；异常值 >10万 视为误匹配。"""
        return r"""(()=>{
            const d={store_count:null,paused_count:0};
            // 策略1: 从单个 DOM 元素精确匹配（避免全页面文本干扰）
            for(const el of document.querySelectorAll('span,div,p,h4')){
                const t=(el.textContent||'').trim();
                const m=t.match(/共为您找到\s*(\d{1,6})\s*(?:个|家)/);
                if(m){d.store_count=parseInt(m[1]);break;}
            }
            // 策略2: fallback 到 body 文本
            if(!d.store_count){
                const h=document.body.innerText;
                let m=h.match(/共为您找到\s*(\d{1,6})\s*个/);
                if(!m)m=h.match(/找到\s*(\d{1,6})\s*家/);
                if(m)d.store_count=parseInt(m[1]);
            }
            // 暂停营业数
            for(const el of document.querySelectorAll('span,div,em')){
                const t=(el.textContent||'').trim();
                const m=t.match(/暂停营业\s*(\d{1,5})/);
                if(m){d.paused_count=parseInt(m[1]);break;}
            }
            // 异常值保护
            if(d.store_count>100000)d.store_count=null;
            return d;
        })()"""

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def close(self) -> None:
        """关闭 automation window。"""
        try:
            self._run("close")
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
