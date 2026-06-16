"""
数据收集基类
定义统一接口，具体实现可对接真实 API 或使用模拟数据
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseCollector(ABC):
    """数据收集器基类"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    @abstractmethod
    def collect(self, credit_code: str, company_name: str) -> Dict[str, Any]:
        """
        收集数据
        :param credit_code: 统一社会信用代码
        :param company_name: 公司名称
        :return: 收集到的数据字典
        """
        pass


class MockDataMixin:
    """
    模拟数据混入类
    用于演示和测试，生产环境应替换为真实 API 调用
    """
    
    @staticmethod
    def _hash_seed(text: str) -> int:
        """基于文本生成确定性随机种子"""
        return sum(ord(c) * (i + 1) for i, c in enumerate(text)) % 10000
    
    def mock_basic_info(self, credit_code: Optional[str] = None) -> Dict[str, Any]:
        """模拟企业基础信息"""
        seed = self._hash_seed(credit_code or "unknown")
        import random
        rng = random.Random(seed)
        
        years = rng.randint(1, 20)
        capital = rng.choice([500000, 1000000, 3000000, 5000000, 10000000, 50000000, 100000000])
        # 实缴资本直接生成（天眼查网页直接显示，不用算比例）
        paid_in = rng.choice([100000, 500000, 1500000, 3000000, 8000000, 40000000, 90000000])
        abnormal = rng.choices([0, 1, 2, 3], weights=[70, 15, 10, 5])[0]
        penalty = rng.choices([0, 1, 2], weights=[80, 15, 5])[0]
        
        # 新增：公司规模相关模拟数据
        insured = rng.choices([0, 5, 20, 100, 500, 2000], weights=[10, 15, 25, 25, 15, 10])[0]
        tyc_score = rng.randint(40, 95)
        self_risk = rng.choices([0, 1, 3, 10, 30], weights=[50, 25, 15, 7, 3])[0]
        around_risk = rng.choices([0, 2, 8, 25, 60], weights=[40, 25, 20, 10, 5])[0]
        
        return {
            'established_years': years,
            'registered_capital': capital,
            'paid_in_capital': paid_in,
            'paid_in_capital_ratio': round(paid_in / capital, 2) if capital > 0 else 0.0,
            'abnormal_records': abnormal,
            'penalty_records': penalty,
            'company_status': '存续',
            'insured_count': insured,
            'tianyancha_score': tyc_score,
            'self_risk_count': self_risk,
            'around_risk_count': around_risk,
        }
    
    def mock_financial_info(self, credit_code: Optional[str] = None) -> Dict[str, Any]:
        """模拟财务信息（默认不提供真实财报数据，触发缺省逻辑）"""
        # 生产环境应接入真实财务报表
        # 演示模式下默认返回None，让评分卡使用缺省分10
        return {
            'debt_ratio': None,
            'current_ratio': None,
            'revenue_growth': None,
            'cash_flow': None,
            'net_margin': None,
        }
    
    def mock_judicial_info(self, credit_code: Optional[str] = None) -> Dict[str, Any]:
        """模拟司法信息"""
        seed = self._hash_seed((credit_code or "unknown") + "jud")
        import random
        rng = random.Random(seed)
        
        lawsuit = rng.choices([0, 1, 2, 5, 10], weights=[60, 20, 10, 7, 3])[0]
        dishonest = 1 if rng.random() < 0.08 else 0
        pledge = round(rng.uniform(0, 0.6), 3) if rng.random() < 0.3 else 0
        
        return {
            'lawsuit_count': lawsuit,
            'dishonest_records': dishonest,
            'pledge_freeze': pledge
        }
    
    def mock_news_info(self, credit_code: Optional[str] = None) -> Dict[str, Any]:
        """模拟舆情信息"""
        seed = self._hash_seed((credit_code or "unknown") + "news")
        import random
        rng = random.Random(seed)
        
        negative = rng.choices([0, 1, 3, 5, 10, 20], weights=[50, 20, 15, 8, 5, 2])[0]
        
        return {
            'negative_news': negative
        }
