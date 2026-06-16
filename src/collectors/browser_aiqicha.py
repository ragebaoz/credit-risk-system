"""
爱企查浏览器数据抓取器

基于 Playwright + 用户已登录 Chrome 复用 SVIP 会话
自动抓取企业工商信息、经营状况、司法风险等数据

使用方式：
    collector = AiQichaBrowserCollector()
    data = collector.collect("北京某科技有限公司", "91110108MA005K8N5X")
"""
import re
import time
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

# Playwright 导入在需要时动态处理，允许未安装时回退到 mock
try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class AiQichaConfig:
    """爱企查抓取配置"""
    headless: bool = True           # 是否无头模式
    slow_mo: int = 500              # 操作间隔(ms)
    timeout: int = 15000            # 页面加载超时(ms)
    chrome_user_data_dir: Optional[str] = None  # Chrome profile 路径
    chrome_executable_path: Optional[str] = None  # Chrome 可执行文件路径
    
    def __post_init__(self):
        if self.chrome_user_data_dir is None:
            # macOS 默认 Chrome profile
            home = os.path.expanduser("~")
            default = os.path.join(home, "Library/Application Support/Google/Chrome")
            if os.path.exists(default):
                self.chrome_user_data_dir = default


class AiQichaBrowserCollector:
    """
    爱企查浏览器数据收集器
    
    通过复用用户已登录的 Chrome profile，自动抓取企业多维数据
    """
    
    BASE_URL = "https://aiqicha.baidu.com"
    
    def __init__(self, config: Optional[AiQichaConfig] = None):
        self.config = config or AiQichaConfig()
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None
    
    def _init_browser(self):
        """初始化浏览器（复用系统 Chrome）"""
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright 未安装，请运行: pip install playwright")
        
        p = sync_playwright().start()
        
        launch_args = {
            "headless": self.config.headless,
            "slow_mo": self.config.slow_mo,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        }
        
        # 优先使用系统 Chrome（channel 方式）
        try:
            self._browser = p.chromium.launch(channel="chrome", **launch_args)
        except Exception:
            # 回退：尝试直接指定 Chrome 路径
            if self.config.chrome_executable_path:
                launch_args["executable_path"] = self.config.chrome_executable_path
            if self.config.chrome_user_data_dir:
                launch_args["args"].append(f"--user-data-dir={self.config.chrome_user_data_dir}")
            self._browser = p.chromium.launch(**launch_args)
        
        context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        self._page = context.new_page()
        self._page.set_default_timeout(self.config.timeout)
    
    def _close_browser(self):
        """关闭浏览器"""
        if self._browser:
            self._browser.close()
            self._browser = None
            self._page = None
    
    def collect(self, company_name: str, credit_code: Optional[str] = None) -> Dict[str, Any]:
        """
        抓取企业数据
        
        :param company_name: 企业全称或关键词
        :param credit_code: 统一社会信用代码（可选，用于精确匹配）
        :return: 标准化评估数据字典
        """
        try:
            self._init_browser()
            
            print(f"[爱企查] 正在搜索: {company_name}")
            detail_url = self._search_company(company_name, credit_code)
            
            if not detail_url:
                print(f"[爱企查] 未找到企业: {company_name}")
                return {}
            
            print(f"[爱企查] 进入详情页: {detail_url}")
            raw = self._extract_detail(detail_url)
            
            # 标准化为评分系统所需格式
            return self._normalize(raw)
        
        except Exception as e:
            print(f"[爱企查] 抓取失败: {e}")
            return {}
        
        finally:
            self._close_browser()
    
    def _search_company(self, company_name: str, credit_code: Optional[str] = None) -> Optional[str]:
        """
        搜索企业并返回详情页 URL
        """
        page = self._page
        search_url = f"{self.BASE_URL}/s?q={company_name}"
        page.goto(search_url)
        
        # 等待结果加载
        try:
            page.wait_for_selector(".result-list, .aqc-search-result, [class*='result']", timeout=10000)
        except:
            # 可能直接跳转到详情页（精确匹配）
            if "company_detail" in page.url or "detail" in page.url:
                return page.url
            return None
        
        time.sleep(1.5)  # 等待动态渲染
        
        # 尝试找到第一个企业链接
        selectors = [
            '.result-list .title a',
            '.aqc-search-result a[href*="company_detail"]',
            'a[href*="company_detail"]',
            '.search-result-item a',
        ]
        
        for sel in selectors:
            links = page.query_selector_all(sel)
            for link in links:
                href = link.get_attribute("href") or ""
                text = (link.inner_text() or "").strip()
                
                if "company_detail" in href:
                    # 如果有信用代码，校验匹配度
                    if credit_code:
                        # 简单校验：企业名包含搜索词
                        if company_name[:4] in text or text[:4] in company_name:
                            return href if href.startswith("http") else self.BASE_URL + href
                    else:
                        return href if href.startswith("http") else self.BASE_URL + href
        
        # 兜底：取页面中第一个 company_detail 链接
        all_links = page.query_selector_all('a[href*="company_detail"]')
        if all_links:
            href = all_links[0].get_attribute("href") or ""
            return href if href.startswith("http") else self.BASE_URL + href
        
        return None
    
    def _extract_detail(self, detail_url: str) -> Dict[str, Any]:
        """
        从详情页提取原始数据
        """
        page = self._page
        page.goto(detail_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        
        raw = {}
        
        # ===== 1. 基础信息（企业信息标签页或页面顶部） =====
        raw['company_name'] = self._extract_text_by_patterns(page, [
            'h1.company-name',
            '.company-name',
            '[class*="companyName"]',
            'h1',
        ])
        
        raw['status'] = self._extract_text_by_label(page, ["经营状态", "企业状态", "登记状态"])
        raw['established_date'] = self._extract_text_by_label(page, ["成立日期", "成立时间"])
        raw['registered_capital'] = self._extract_text_by_label(page, ["注册资本", "注册资金"])
        raw['paid_in_capital'] = self._extract_text_by_label(page, ["实缴资本", "实缴资金"])
        
        # ===== 2. 经营状况（尝试点击"经营状况"或"风险信息"标签） =====
        raw['abnormal_count'] = self._extract_count_by_label(page, ["经营异常", "列入经营异常"])
        raw['penalty_count'] = self._extract_count_by_label(page, ["行政处罚", "处罚记录"])
        
        # 尝试访问经营状况标签
        self._try_click_tab(page, ["经营状况", "经营风险", "风险信息"])
        raw['abnormal_count'] = self._extract_count_by_label(page, ["经营异常"]) or raw.get('abnormal_count')
        raw['penalty_count'] = self._extract_count_by_label(page, ["行政处罚"]) or raw.get('penalty_count')
        
        # ===== 3. 司法风险 =====
        self._try_click_tab(page, ["司法风险", "司法解析", "法律诉讼"])
        raw['lawsuit_count'] = self._extract_count_by_label(page, ["司法案件", "法律诉讼", "涉诉关系"])
        raw['dishonest_count'] = self._extract_count_by_label(page, ["失信信息", "失信被执行人", "老赖"])
        raw['pledge_count'] = self._extract_count_by_label(page, ["股权冻结", "股权出质", "股权质押"])
        
        # ===== 4. 通过页面全局文本匹配兜底 =====
        page_text = page.inner_text("body") or ""
        
        if not raw.get('abnormal_count'):
            raw['abnormal_count'] = self._extract_number_from_text(page_text, r"经营异常\s*[:：]\s*(\d+)")
        if not raw.get('penalty_count'):
            raw['penalty_count'] = self._extract_number_from_text(page_text, r"行政处罚\s*[:：]\s*(\d+)")
        if not raw.get('lawsuit_count'):
            raw['lawsuit_count'] = self._extract_number_from_text(page_text, r"司法案件|法律诉讼.*?[:：]\s*(\d+)")
        if not raw.get('dishonest_count'):
            raw['dishonest_count'] = self._extract_number_from_text(page_text, r"失信信息|失信被执行人.*?[:：]\s*(\d+)")
        
        return raw
    
    def _normalize(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        将爱企查原始数据标准化为评分系统格式
        """
        result = {}
        
        # 成立年限
        est_date_str = raw.get('established_date', '')
        result['established_years'] = self._parse_established_years(est_date_str)
        
        # 注册资本
        result['registered_capital'] = self._parse_capital(raw.get('registered_capital', ''))
        
        # 实缴比例
        paid = self._parse_capital(raw.get('paid_in_capital', ''))
        reg = result['registered_capital']
        result['paid_in_capital_ratio'] = round(paid / reg, 2) if reg > 0 else 0
        
        # 经营异常 / 行政处罚
        result['abnormal_records'] = self._safe_int(raw.get('abnormal_count'))
        result['penalty_records'] = self._safe_int(raw.get('penalty_count'))
        
        # 司法风险
        result['lawsuit_count'] = self._safe_int(raw.get('lawsuit_count'))
        result['dishonest_records'] = self._safe_int(raw.get('dishonest_count'))
        result['pledge_freeze'] = self._safe_float(raw.get('pledge_count'))  # 简化为数值
        
        # 工商存续状态
        status = raw.get('status', '')
        result['company_status'] = status if status else ''
        
        # 负面舆情（爱企查无此数据，留空）
        result['negative_news'] = 0
        
        # 标记数据来源
        result['_source'] = 'aiqicha_browser'
        result['_raw'] = raw
        
        return result
    
    # ===== 辅助提取方法 =====
    
    def _extract_text_by_patterns(self, page: Page, selectors: list) -> str:
        """按选择器列表顺序尝试提取文本"""
        for sel in selectors:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text() or ""
                if text.strip():
                    return text.strip()
        return ""
    
    def _extract_text_by_label(self, page: Page, labels: list) -> str:
        """通过标签文本定位相邻值"""
        for label in labels:
            # 方式1: label + value 相邻结构
            sel = f"""
                //*[contains(text(), '{label}')]/following-sibling::*[1]
                | //*[contains(text(), '{label}')]/parent::*/following-sibling::*[1]
                | //dt[contains(text(), '{label}')]/following-sibling::dd[1]
                | //span[contains(text(), '{label}')]/following-sibling::span[1]
            """
            try:
                els = page.query_selector_all(f"text={label}")
                for el in els:
                    # 尝试找相邻兄弟或父级的下一个元素
                    parent = el.evaluate("e => e.parentElement")
                    if parent:
                        val_el = page.evaluate(
                            "(parent, label) => {\n"
                            "  const children = Array.from(parent.children);\n"
                            "  const idx = children.findIndex(c => c.innerText.includes(label));\n"
                            "  return idx >= 0 ? children[idx + 1]?.innerText?.trim() : '';\n"
                            "}", parent, label
                        )
                        if val_el:
                            return str(val_el)
            except:
                pass
        
        # 方式2: 页面全局文本正则
        page_text = page.inner_text("body") or ""
        for label in labels:
            patterns = [
                rf"{label}\s*[:：]\s*([^\n]+)",
                rf"{label}\s+([^\n{label}]+)",
            ]
            for pat in patterns:
                m = re.search(pat, page_text)
                if m:
                    return m.group(1).strip()
        return ""
    
    def _extract_count_by_label(self, page: Page, labels: list) -> Optional[int]:
        """提取带数字的统计标签，如 '经营异常 3'"""
        page_text = page.inner_text("body") or ""
        for label in labels:
            # 模式: 标签后面紧跟数字，可能在括号内
            patterns = [
                rf"{label}\s*[（(]\s*(\d+)\s*[)）]",
                rf"{label}\s*[:：]?\s*(\d+)",
                rf"{label}.*?(\d+)\s*条",
            ]
            for pat in patterns:
                m = re.search(pat, page_text)
                if m:
                    return int(m.group(1))
        
        # 尝试通过 selector 找 badge/number
        for label in labels:
            sel = f"text={label}"
            try:
                els = page.query_selector_all(sel)
                for el in els:
                    text = el.inner_text() or ""
                    nums = re.findall(r"\d+", text)
                    if nums:
                        return int(nums[-1])
            except:
                pass
        return None
    
    def _try_click_tab(self, page: Page, tab_names: list):
        """尝试点击标签页"""
        for name in tab_names:
            selectors = [
                f'text="{name}"',
                f'button:has-text("{name}")',
                f'a:has-text("{name}")',
                f'[role="tab"]:has-text("{name}")',
            ]
            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        time.sleep(1.5)
                        return
                except:
                    pass
    
    def _extract_number_from_text(self, text: str, pattern: str) -> Optional[int]:
        """从文本中用正则提取数字"""
        m = re.search(pattern, text)
        if m:
            try:
                return int(m.group(1))
            except:
                pass
        return None
    
    def _parse_established_years(self, date_str: str) -> float:
        """解析成立日期为年限"""
        if not date_str:
            return 0
        from datetime import datetime
        # 尝试多种格式
        for fmt in ("%Y-%m-%d", "%Y年%m月%d日", "%Y/%m/%d", "%Y-%m", "%Y年%m月"):
            try:
                dt = datetime.strptime(date_str[:len(fmt)], fmt)
                return round((datetime.now() - dt).days / 365.25, 1)
            except:
                continue
        # 仅年份
        m = re.search(r"(\d{4})", date_str)
        if m:
            try:
                dt = datetime(int(m.group(1)), 1, 1)
                return round((datetime.now() - dt).days / 365.25, 1)
            except:
                pass
        return 0
    
    def _parse_capital(self, capital_str: str) -> float:
        """解析资本金额"""
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
    
    def _safe_int(self, val) -> int:
        try:
            return int(val) if val is not None else 0
        except:
            return 0
    
    def _safe_float(self, val) -> float:
        try:
            return float(val) if val is not None else 0
        except:
            return 0


# ===== 集成到现有 Collector 框架 =====

class AiQichaEnterpriseCollector:
    """
    适配现有评估系统的爱企查浏览器收集器
    """
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self._inner = None
    
    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        """兼容 BaseCollector 接口"""
        if not PLAYWRIGHT_AVAILABLE:
            print("[警告] Playwright 未安装，回退到模拟数据")
            from .base import MockDataMixin
            return MockDataMixin.mock_basic_info(MockDataMixin(), credit_code)
        
        config = AiQichaConfig(headless=self.headless)
        self._inner = AiQichaBrowserCollector(config)
        
        # 抓取基础信用 + 司法风险数据
        result = self._inner.collect(company_name, credit_code)
        
        if not result:
            print("[爱企查] 浏览器抓取失败，回退到模拟数据")
            from .base import MockDataMixin
            return MockDataMixin.mock_basic_info(MockDataMixin(), credit_code)
        
        return result


if __name__ == "__main__":
    # 本地测试
    collector = AiQichaBrowserCollector(
        AiQichaConfig(headless=False, slow_mo=800)
    )
    # data = collector.collect("百度在线网络技术（北京）有限公司")
    # print(data)
    print("请通过评估系统调用此模块")
