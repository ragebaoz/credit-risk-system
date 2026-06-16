"""
财务数据收集器
支持从 Excel/PDF 解析财务数据
"""
from typing import Dict, Any, Optional
from .base import BaseCollector, MockDataMixin


class FinancialCollector(BaseCollector, MockDataMixin):
    """
    财务数据收集器
    
    支持来源：
    - 客户提供的财务报表（Excel/PDF）
    - 模拟数据（演示用）
    """
    
    def collect(self, credit_code: str, company_name: str, 
                excel_path: Optional[str] = None) -> Dict[str, Any]:
        """
        收集财务数据
        无真实财务报表时返回空值，由评分卡使用替代指标（sudden_death_risk）
        """
        if excel_path:
            return self._parse_excel(excel_path)
        
        if self.api_key:
            # 可对接第三方财务数据服务
            pass
        
        # 无真实财务数据：返回None值，评分卡将使用 sudden_death_risk 替代
        print("[财务] 未提供真实财务报表，财务健康维度将使用外部替代指标")
        return {
            'debt_ratio': None,
            'current_ratio': None,
            'revenue_growth': None,
            'cash_flow': None,
            'net_margin': None,
        }
    
    def _parse_excel(self, path: str) -> Dict[str, Any]:
        """
        解析财务报表 Excel
        预期包含关键指标的工作表
        """
        import pandas as pd
        
        df = pd.read_excel(path, sheet_name="关键指标")
        
        # 根据列名映射提取数据
        def get_value(col_name):
            row = df[df['指标'] == col_name]
            return row.iloc[0, -1] if not row.empty else None
        
        return {
            'debt_ratio': get_value('资产负债率'),
            'current_ratio': get_value('流动比率'),
            'revenue_growth': get_value('营业收入增长率'),
            'cash_flow': get_value('经营活动现金流量净额'),
            'net_margin': get_value('销售净利率')
        }
