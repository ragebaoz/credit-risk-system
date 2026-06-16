"""
天眼查收集器 — OpenCLI Browser 方案
直接调用 OpenCLI Browser CLI，复用用户已有 Chrome 的登录态和扩展。
"""
from typing import Dict, Any, Optional
from .opencli_browser import OpenCLIBrowser
from .base import MockDataMixin


class OpenCLITianYanChaCollector:
    """基于 OpenCLI Browser 的天眼查企业信息收集器"""

    def __init__(self, workspace: str = "default"):
        self.browser = OpenCLIBrowser(workspace=workspace)

    def collect(self, credit_code: Optional[str], company_name: str) -> Dict[str, Any]:
        """
        收集企业工商信息
        参数顺序兼容 enterprise_collector 接口: collect(credit_code, company_name)
        原则：绝不使用模拟数据，采集失败返回空 dict，评分卡给缺省分
        """
        try:
            result = self.browser.tianyancha_search(company_name)
            if not result or not result.get("company_name"):
                raise RuntimeError("天眼查搜索无结果")
            # 如果被反爬拦截，返回空数据
            if result.get("_error") == "blocked_by_antibot":
                print(f"[OpenCLI-天眼查] ⚠️ {company_name} 被反爬拦截，返回空数据")
                return {"company_name": company_name}
            return result
        except Exception as e:
            print(f"[OpenCLI-天眼查] ⚠️ {company_name} 采集失败: {e}，返回空数据（评分卡给缺省分）")
            return {"company_name": company_name}


# 兼容旧接口
class TianYanChaEnterpriseCollector:
    """兼容旧接口的封装，默认使用 OpenCLI Browser"""

    def __init__(self, headless: bool = True, workspace: str = "default"):
        self._inner = OpenCLITianYanChaCollector(workspace=workspace)

    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        return self._inner.collect(credit_code, company_name)
