"""
天眼查收集器 — CDP 直连用户 Chrome 方案

绑定用户本地 Chrome（localhost:9222），
在用户实际页面上操作（goto/eval/scroll），用户能看到动作。
"""
import re
import time
from typing import Dict, Any, Optional

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


class CDPTianYanChaCollector:
    """基于 CDP 直连用户 Chrome 的天眼查收集器"""

    BASE_URL = "https://www.tianyancha.com"
    CDP_ENDPOINT = "http://localhost:9222"

    def __init__(self):
        self._browser = None
        self._page = None

    def _init(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装")
        p = sync_playwright().start()
        self._browser = p.chromium.connect_over_cdp(self.CDP_ENDPOINT)
        context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        self._page = context.pages[0] if context.pages else context.new_page()
        print(f"[天眼查-CDP] 已绑定到你的 Chrome: {self._page.url}")

    def collect(self, company_name: str, credit_code: Optional[str] = None) -> Dict[str, Any]:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装")
        p = sync_playwright().start()
        try:
            self._browser = p.chromium.connect_over_cdp(self.CDP_ENDPOINT)
            context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            self._page = context.pages[0] if context.pages else context.new_page()
            print(f"[天眼查-CDP] 已绑定到你的 Chrome: {self._page.url}")
            print(f"[天眼查-CDP] 正在你的页面上搜索: {company_name}")
            company_id = self._search_company(company_name, credit_code)
            if not company_id:
                print(f"[天眼查-CDP] 未找到企业: {company_name}")
                return {}
            print(f"[天眼查-CDP] 进入详情页 (ID: {company_id})")
            raw = self._extract_detail(company_id)
            if not raw:
                return {}
            return self._normalize(raw)
        finally:
            p.stop()
            self._browser = None
            self._page = None

    def _search_company(self, company_name: str, credit_code: Optional[str] = None) -> Optional[str]:
        page = self._page
        search_url = f"{self.BASE_URL}/search?key={company_name}"
        print(f"[天眼查-CDP] 导航到: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded")
        time.sleep(3)

        html = page.content()
        matches = re.findall(r'/company/(\d+)', html)
        if matches:
            return matches[0]

        text = page.inner_text("body") or ""
        matches = re.findall(r'/company/(\d+)', text)
        if matches:
            return matches[0]
        return None

    def _extract_detail(self, company_id: str) -> Dict[str, Any]:
        page = self._page
        detail_url = f"{self.BASE_URL}/company/{company_id}"
        print(f"[天眼查-CDP] 导航到详情页: {detail_url}")
        page.goto(detail_url, wait_until="domcontentloaded")
        time.sleep(3)

        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(0.5)

        raw = {}
        full_text = page.inner_text("body") or ""
        html = page.content()

        raw['company_name'] = self._extract_by_patterns(full_text, [
            r'企业名称\s*[:：\t]\s*([^\n]+)',
        ]) or self._extract_by_patterns(full_text, [
            r'([\u4e00-\u9fa5]+有限公司)',
        ]) or company_id

        raw['status'] = self._extract_by_patterns(full_text, [
            r'登记状态\s*[:：\t]\s*([^\n]+)',
            r'经营状态\s*[:：\t]\s*([^\n]+)',
            r'(存续|在营|开业|注销|吊销)',
        ])

        raw['established_date'] = self._extract_by_patterns(full_text, [
            r'成立日期\s*[:：\t]\s*([^\n]+)',
        ])

        raw['registered_capital'] = self._extract_by_patterns(full_text, [
            r'注册资本\s*[:：\t]\s*([^\n]+)',
        ])

        paid_in = self._extract_by_patterns(full_text, [
            r'实缴资本\s*[:：\t]\s*([^\n]+)',
        ])
        if paid_in and paid_in.strip() in ('-', '—', ''):
            paid_in = ''
        raw['paid_in_capital'] = paid_in

        raw['insured_count'] = self._extract_by_patterns(full_text, [
            r'参保人数\s*[:：\t]\s*(\d+)',
        ])

        risk_patterns = {
            'lawsuit_count': r'司法案件\s*(\d+)',
            'court_notice_count': r'开庭公告\s*(\d+)',
            'dishonest_count': r'失信被执行人\s*(\d+)',
            'executed_count': r'被执行人\s*(\d+)',
            'restriction_count': r'限制高消费\s*(\d+)',
            'pledge_freeze_count': r'股权冻结\s*(\d+)',
            'pledge_out_count': r'股权出质\s*(\d+)',
            'abnormal_count': r'经营异常\s*(\d+)',
            'penalty_count': r'行政处罚\s*(\d+)',
            'serious_violation_count': r'严重违法\s*(\d+)',
            'bankruptcy_count': r'破产重整\s*(\d+)',
            'negative_news_count': r'新闻舆情\s*(\d+)',
            'self_risk_count': r'自身风险\s*(\d+)',
            'around_risk_count': r'周边风险\s*(\d+)',
        }

        for key, pattern in risk_patterns.items():
            val = self._extract_number(full_text, pattern)
            if val is not None:
                raw[key] = val

        raw['contract_dispute_count'] = self._count_keyword_occurrences(full_text, "买卖合同纠纷")

        risk_level = self._extract_by_patterns(full_text, [
            r'天眼评分\s*[:：]\s*([^\n]+)',
        ])
        if not risk_level:
            m = re.search(r'天眼评分[\s\n]*([^\n\s]{1,10}分)', full_text)
            if m:
                risk_level = m.group(1).strip()
        raw['risk_level'] = risk_level

        raw['_html'] = html[:50000]
        raw['_text'] = full_text[:10000]
        return raw

    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        result = {}
        result['established_years'] = self._parse_established_years(raw.get('established_date', ''))
        result['registered_capital'] = self._parse_capital(raw.get('registered_capital', ''))
        result['paid_in_capital'] = self._parse_capital(raw.get('paid_in_capital', ''))
        reg = result['registered_capital']
        paid = result['paid_in_capital']
        result['paid_in_capital_ratio'] = round(paid / reg, 2) if reg > 0 and paid > 0 else 0.0
        result['abnormal_records'] = self._safe_int(raw.get('abnormal_count'))
        result['penalty_records'] = self._safe_int(raw.get('penalty_count'))
        result['lawsuit_count'] = self._safe_int(raw.get('lawsuit_count'))
        result['contract_dispute_count'] = self._safe_int(raw.get('contract_dispute_count'))
        result['dishonest_records'] = self._safe_int(raw.get('dishonest_count'))
        result['executed_count'] = self._safe_int(raw.get('executed_count'))
        result['restriction_count'] = self._safe_int(raw.get('restriction_count'))
        result['pledge_freeze'] = self._safe_float(raw.get('pledge_freeze_count'))
        result['pledge_freeze_count'] = self._safe_int(raw.get('pledge_freeze_count'))
        result['negative_news'] = self._safe_int(raw.get('negative_news_count'))
        result['insured_count'] = self._safe_int(raw.get('insured_count'))
        result['tianyancha_score'] = self._parse_tianyancha_score(raw.get('risk_level', ''))
        result['self_risk_count'] = self._safe_int(raw.get('self_risk_count'))
        result['around_risk_count'] = self._safe_int(raw.get('around_risk_count'))
        result['_source'] = 'tianyancha_cdp'
        result['_raw'] = {k: v for k, v in raw.items() if not k.startswith('_')}
        return result

    def _extract_by_patterns(self, text: str, patterns: list) -> str:
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                return m.group(1).strip()
        return ""

    def _extract_number(self, text: str, pattern: str) -> Optional[int]:
        m = re.search(pattern, text)
        if m:
            try:
                return int(m.group(1))
            except:
                pass
        return None

    def _count_keyword_occurrences(self, text: str, keyword: str) -> int:
        if not text or not keyword:
            return 0
        return text.count(keyword)

    def _parse_established_years(self, date_str: str) -> float:
        if not date_str:
            return 0
        from datetime import datetime
        date_str = date_str.strip()
        for fmt in ("%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d"):
            try:
                dt = datetime.strptime(date_str, fmt)
                return round((datetime.now() - dt).days / 365.25, 1)
            except:
                continue
        m = re.search(r"(\d{4})", date_str)
        if m:
            try:
                dt = datetime(int(m.group(1)), 1, 1)
                return round((datetime.now() - dt).days / 365.25, 1)
            except:
                pass
        return 0

    def _parse_capital(self, capital_str: str) -> float:
        if not capital_str:
            return 0
        text = str(capital_str).replace(",", "").replace("，", "")
        nums = re.findall(r"[\d.]+", text)
        if not nums:
            return 0
        val = float(nums[0])
        if "万" in text:
            val *= 10000
        if "亿" in text:
            val *= 100000000
        return val

    def _parse_tianyancha_score(self, risk_level_str: str) -> Optional[int]:
        if not risk_level_str:
            return None
        text = str(risk_level_str)
        nums = re.findall(r"(\d{2,3})", text)
        if nums:
            score = int(nums[0])
            if 0 <= score <= 100:
                return score
        return None

    def _safe_int(self, val) -> int:
        try:
            return int(val) if val is not None else 0
        except:
            return 0

    def _safe_float(self, val) -> float:
        try:
            return float(val) if val is not None else 0.0
        except:
            return 0.0


# 兼容旧接口
class TianYanChaEnterpriseCollector:
    def __init__(self, headless: bool = True, cdp_endpoint: str = "http://localhost:9222"):
        self._inner = None

    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        try:
            self._inner = CDPTianYanChaCollector()
            result = self._inner.collect(company_name, credit_code)
            if not result:
                from .base import MockDataMixin
                return MockDataMixin.mock_basic_info(MockDataMixin(), credit_code)
            return result
        except Exception as e:
            print(f"[天眼查-CDP] 异常: {e}，回退到模拟数据")
            from .base import MockDataMixin
            return MockDataMixin.mock_basic_info(MockDataMixin(), credit_code)
