"""
天眼查浏览器数据抓取器

基于 Playwright + CDP 连接用户已运行 Chrome
反爬机制相对宽松，可稳定抓取企业工商、司法、经营风险数据
"""
import re
import time
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class TianYanChaConfig:
    """天眼查抓取配置"""
    headless: bool = True
    slow_mo: int = 300
    timeout: int = 20000
    cdp_endpoint: str = "http://localhost:9222"  # CDP 连接地址


class TianYanChaBrowserCollector:
    """
    天眼查浏览器数据收集器
    
    通过 CDP 连接用户已运行的 Chrome（需提前启动带 --remote-debugging-port=9222）
    或启动新的 Chrome 实例
    """
    
    BASE_URL = "https://www.tianyancha.com"
    
    def __init__(self, config: Optional[TianYanChaConfig] = None):
        self.config = config or TianYanChaConfig()
        self._browser = None
        self._page = None
    
    def _init_browser(self):
        """初始化浏览器连接"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装")
        
        p = sync_playwright().start()
        
        # 优先尝试 CDP 连接已运行的 Chrome
        try:
            self._browser = p.chromium.connect_over_cdp(self.config.cdp_endpoint)
            context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
            self._page = context.pages[0] if context.pages else context.new_page()
            print(f"[天眼查] 已通过 CDP 连接到 Chrome")
            return
        except Exception as e:
            print(f"[天眼查] CDP 连接失败: {e}，尝试启动新 Chrome...")
        
        # 回退：启动新 Chrome
        launch_args = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo,
            "args": ["--disable-blink-features=AutomationControlled"]
        }
        
        try:
            self._browser = p.chromium.launch(channel="chrome", **launch_args)
        except:
            self._browser = p.chromium.launch(**launch_args)
        
        context = self._browser.new_context(viewport={"width": 1440, "height": 900})
        self._page = context.new_page()
    
    def _close_browser(self):
        if self._browser:
            # CDP 连接时不关闭浏览器，只关闭 page
            if hasattr(self._browser, '_cdp_endpoint'):
                pass
            else:
                self._browser.close()
            self._browser = None
            self._page = None
    
    def collect(self, company_name: str, credit_code: Optional[str] = None) -> Dict[str, Any]:
        """
        抓取企业数据
        
        :param company_name: 企业名称
        :param credit_code: 统一社会信用代码（用于精确匹配）
        :return: 标准化评估数据字典
        """
        try:
            self._init_browser()
            
            print(f"[天眼查] 正在搜索: {company_name}")
            company_id = self._search_company(company_name, credit_code)
            
            if not company_id:
                print(f"[天眼查] 未找到企业: {company_name}")
                return {}
            
            print(f"[天眼查] 进入详情页 (ID: {company_id})")
            raw = self._extract_detail(company_id)
            
            if not raw:
                return {}
            
            return self._normalize(raw)
        
        except Exception as e:
            print(f"[天眼查] 抓取失败: {e}")
            return {}
        
        finally:
            self._close_browser()
    
    def _search_company(self, company_name: str, credit_code: Optional[str] = None) -> Optional[str]:
        """
        搜索企业并返回天眼查 company_id
        """
        page = self._page
        search_url = f"{self.BASE_URL}/search?key={company_name}"
        page.goto(search_url, wait_until="domcontentloaded")
        
        try:
            page.wait_for_selector(".search-item, .result-list, [class*='search']", timeout=10000)
        except:
            pass
        
        time.sleep(2)
        
        # 尝试提取第一个企业链接中的 company_id
        html = page.content()
        
        # 匹配 /company/2962451379 这样的链接
        pattern = r'/company/(\d+)'
        matches = re.findall(pattern, html)
        
        if matches:
            return matches[0]
        
        # 尝试通过选择器找链接
        selectors = [
            'a[href*="/company/"]',
            '.search-item a',
            '.result-list a',
        ]
        
        for sel in selectors:
            links = page.query_selector_all(sel)
            for link in links:
                href = link.get_attribute("href") or ""
                company_id_match = re.search(r'/company/(\d+)', href)
                if company_id_match:
                    return company_id_match.group(1)
        
        return None
    
    def _extract_detail(self, company_id: str) -> Dict[str, Any]:
        """
        从详情页提取原始数据
        """
        page = self._page
        detail_url = f"{self.BASE_URL}/company/{company_id}"
        page.goto(detail_url, wait_until="domcontentloaded")
        
        time.sleep(3)
        
        # 滚动页面加载动态内容
        for _ in range(5):
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(0.5)
        
        raw = {}
        full_text = page.inner_text("body") or ""
        html = page.content()
        
        # ===== 1. 基础信息 =====
        raw['company_name'] = self._extract_by_patterns(full_text, [
            r'企业名称\s*[:：]\s*([^\n]+)',
        ]) or self._extract_by_patterns(full_text, [
            r'([\u4e00-\u9fa5]+有限公司)',
        ]) or company_id
        
        raw['status'] = self._extract_by_patterns(full_text, [
            r'登记状态\s*[:：]\s*([^\n]+)',
            r'经营状态\s*[:：]\s*([^\n]+)',
            r'(存续|在营|开业|注销|吊销)',
        ])
        
        raw['established_date'] = self._extract_by_patterns(full_text, [
            r'成立日期\s*[:：]\s*([^\n]+)',
        ])
        
        raw['registered_capital'] = self._extract_by_patterns(full_text, [
            r'注册资本\s*[:：]\s*([^\n]+)',
        ])
        
        # 实缴资本：天眼查未公示时显示为 "-"，需识别
        paid_in = self._extract_by_patterns(full_text, [
            r'实缴资本\s*[:：\t]\s*([^\n]+)',
        ])
        if paid_in and paid_in.strip() in ('-', '—', ''):
            paid_in = ''
        raw['paid_in_capital'] = paid_in
        
        # 参保人数
        # 参保人数：天眼查页面可能是 "参保人数：20" 或 "参保人数\t20" 格式
        raw['insured_count'] = self._extract_by_patterns(full_text, [
            r'参保人数\s*[:：\t]\s*(\d+)',
        ])
        
        # ===== 2. 风险信息（通过文本全局匹配） =====
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
        
        # ===== 3. 诉讼类型统计（买卖合同纠纷） =====
        # 从页面文本中统计"买卖合同纠纷"出现次数
        raw['contract_dispute_count'] = self._count_keyword_occurrences(full_text, "买卖合同纠纷")
        
        # 提取风险等级描述 — 天眼评分可能和分数分行显示
        risk_level = self._extract_by_patterns(full_text, [
            r'天眼评分\s*[:：]\s*([^\n]+)',
        ])
        # 如果上面没匹配到，尝试匹配"天眼评分"后面紧跟的分数行
        if not risk_level:
            m = re.search(r'天眼评分[\s\n]*([^\n\s]{1,10}分)', full_text)
            if m:
                risk_level = m.group(1).strip()
        raw['risk_level'] = risk_level
        
        # 保存原始页面用于调试
        raw['_html'] = html[:50000]
        raw['_text'] = full_text[:10000]
        
        return raw
    
    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """标准化为评分系统格式"""
        result = {}
        
        # 成立年限
        est_date_str = raw.get('established_date', '')
        result['established_years'] = self._parse_established_years(est_date_str)
        
        # 注册资本（天眼查网页直接显示）
        result['registered_capital'] = self._parse_capital(raw.get('registered_capital', ''))
        
        # 实缴资本（天眼查网页直接显示，不用自己算比例）
        result['paid_in_capital'] = self._parse_capital(raw.get('paid_in_capital', ''))
        
        # 实缴比例（保留作为参考）
        reg = result['registered_capital']
        paid = result['paid_in_capital']
        result['paid_in_capital_ratio'] = round(paid / reg, 2) if reg > 0 and paid > 0 else 0.0
        
        # 经营异常 / 行政处罚
        result['abnormal_records'] = self._safe_int(raw.get('abnormal_count'))
        result['penalty_records'] = self._safe_int(raw.get('penalty_count'))
        
        # 司法风险
        result['lawsuit_count'] = self._safe_int(raw.get('lawsuit_count'))
        result['contract_dispute_count'] = self._safe_int(raw.get('contract_dispute_count'))
        result['dishonest_records'] = self._safe_int(raw.get('dishonest_count'))
        result['executed_count'] = self._safe_int(raw.get('executed_count'))
        result['restriction_count'] = self._safe_int(raw.get('restriction_count'))
        result['pledge_freeze'] = self._safe_float(raw.get('pledge_freeze_count'))
        result['pledge_freeze_count'] = self._safe_int(raw.get('pledge_freeze_count'))
        
        # 负面舆情
        result['negative_news'] = self._safe_int(raw.get('negative_news_count'))
        
        # 公司规模相关（新增）
        result['insured_count'] = self._safe_int(raw.get('insured_count'))
        result['tianyancha_score'] = self._parse_tianyancha_score(raw.get('risk_level', ''))
        result['self_risk_count'] = self._safe_int(raw.get('self_risk_count'))
        result['around_risk_count'] = self._safe_int(raw.get('around_risk_count'))
        
        # 数据来源标记
        result['_source'] = 'tianyancha_browser'
        result['_raw'] = {k: v for k, v in raw.items() if not k.startswith('_')}
        
        return result
    
    # ===== 辅助方法 =====
    
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
        """统计关键词在文本中出现的次数"""
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
        text = str(capital_str).replace(",", "").replace(",", "")
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
        """从天眼评分文本中提取数字分数，如'评分78' -> 78"""
        if not risk_level_str:
            return None
        text = str(risk_level_str)
        # 匹配常见的评分格式：78分、评分78、78
        nums = re.findall(r"(\d{2,3})", text)
        if nums:
            score = int(nums[0])
            # 天眼评分通常在0-100之间
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


class TianYanChaEnterpriseCollector:
    """适配现有评估系统的天眼查浏览器收集器"""
    
    def __init__(self, headless: bool = True, cdp_endpoint: str = "http://localhost:9222"):
        self.headless = headless
        self.cdp_endpoint = cdp_endpoint
        self._inner = None
    
    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        """兼容 BaseCollector 接口"""
        if not PLAYWRIGHT_AVAILABLE:
            print("[警告] Playwright 未安装，回退到模拟数据")
            from .base import MockDataMixin
            return MockDataMixin.mock_basic_info(MockDataMixin(), credit_code)
        
        config = TianYanChaConfig(
            headless=self.headless,
            cdp_endpoint=self.cdp_endpoint
        )
        self._inner = TianYanChaBrowserCollector(config)
        
        result = self._inner.collect(company_name, credit_code)
        
        if not result:
            print("[天眼查] 浏览器抓取失败，回退到模拟数据")
            from .base import MockDataMixin
            return MockDataMixin.mock_basic_info(MockDataMixin(), credit_code)
        
        return result


if __name__ == "__main__":
    collector = TianYanChaBrowserCollector()
    data = collector.collect("深圳市力达动漫有限公司")
    import json
    print(json.dumps(data, ensure_ascii=False, indent=2))
