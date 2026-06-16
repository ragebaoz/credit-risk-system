"""
企业工商信息收集器
可对接天眼查/企查查 API
"""
from typing import Dict, Any
from .base import BaseCollector, MockDataMixin


class EnterpriseCollector(BaseCollector, MockDataMixin):
    """
    企业工商信息收集器
    """
    
    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        """
        收集企业工商信息
        
        生产环境建议对接：
        - 天眼查开放平台: https://open.tianyancha.com/
        - 企查查 API: https://openapi.qcc.com/
        - 国家企业信用信息公示系统
        """
        if self.api_key:
            # 真实 API 调用逻辑
            # return self._call_real_api(credit_code)
            pass
        
        # 使用模拟数据（演示用）
        return self.mock_basic_info(credit_code)
    
    def _call_real_api(self, credit_code: str) -> Dict[str, Any]:
        """
        真实 API 调用示例（天眼查）
        需申请 api_key 并配置
        """
        import requests
        url = f"https://open.api.tianyancha.com/services/open/ic/baseinfo/2.0"
        headers = {"Authorization": self.api_key}
        params = {"id": credit_code}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json().get("result", {})
        
        return {
            'established_years': self._calc_years(data.get("estiblishTime")),
            'registered_capital': self._parse_capital(data.get("regCapital")),
            'paid_in_capital_ratio': self._calc_paid_ratio(data.get("regCapital"), data.get("actualCapital")),
            'abnormal_records': data.get("abnormalCount", 0),
            'penalty_records': data.get("punishCount", 0)
        }
    
    @staticmethod
    def _calc_years(est_time) -> float:
        from datetime import datetime
        if not est_time:
            return 0
        try:
            if isinstance(est_time, str):
                est = datetime.strptime(est_time[:10], "%Y-%m-%d")
            else:
                est = datetime.fromtimestamp(est_time / 1000)
            return round((datetime.now() - est).days / 365.25, 1)
        except:
            return 0
    
    @staticmethod
    def _parse_capital(capital_str) -> float:
        if not capital_str:
            return 0
        import re
        num = re.findall(r'[\d.]+', str(capital_str))
        if not num:
            return 0
        val = float(num[0])
        if '万' in str(capital_str):
            val *= 10000
        return val
    
    @staticmethod
    def _calc_paid_ratio(reg, actual) -> float:
        reg_val = EnterpriseCollector._parse_capital(reg)
        actual_val = EnterpriseCollector._parse_capital(actual)
        if reg_val <= 0:
            return 0
        return round(min(actual_val / reg_val, 1.0), 2)
