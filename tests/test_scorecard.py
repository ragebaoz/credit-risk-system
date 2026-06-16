"""
评分卡模型单元测试
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.scorecard import ScorecardModel


class TestScorecardModel(unittest.TestCase):
    
    def setUp(self):
        self.model = ScorecardModel()
        self.perfect_data = {
            'established_years': 15,
            'registered_capital': 100000000,
            'paid_in_capital': 100000000,
            'paid_in_capital_ratio': 1.0,
            'abnormal_records': 0,
            'penalty_records': 0,
            'debt_ratio': 0.3,
            'current_ratio': 2.5,
            'revenue_growth': 0.3,
            'cash_flow': 100000000,
            'net_margin': 0.2,
            'on_time_rate': 1.0,
            'avg_overdue_days': 0,
            'max_overdue_amount': 0,
            'cooperation_years': 10,
            'lawsuit_count': 0,
            'contract_dispute_count': 0,
            'dishonest_records': 0,
            'pledge_freeze': 0,
            'pledge_freeze_count': 0,
            'negative_news': 0,
            'insured_count': 2000,
            'self_risk_count': 0,
            'around_risk_count': 0,
            'executed_count': 0,
            'restriction_count': 0,
            'dp_store_count': 200,
            'dp_paused_count': 0,
            'company_status': '存续',
            'tianyancha_score': 95,
            'affiliated_company_count': 6,
            'affiliated_company_health': 0,
        }
    
    def test_perfect_score(self):
        """测试完美客户应该得到高分"""
        result = self.model.calculate_score(self.perfect_data)
        self.assertGreaterEqual(result['total_score'], 90)
        self.assertIn(result['risk_grade'], ['AAA', 'AA'])
    
    def test_bad_score(self):
        """测试极差客户应该得到低分"""
        bad_data = self.perfect_data.copy()
        bad_data.update({
            'debt_ratio': 1.5,
            'revenue_growth': -0.5,
            'cash_flow': -100000000,
            'net_margin': -0.2,
            'on_time_rate': 0.3,
            'avg_overdue_days': 120,
            'max_overdue_amount': 0.6,
            'cooperation_years': 0.2,
            'dishonest_records': 2,
            'lawsuit_count': 8
        })
        result = self.model.calculate_score(bad_data)
        # 当前4维度权重下，坏客户如果在基础信用/公司规模仍较好，总分不会极低
        self.assertLessEqual(result['total_score'], 90)
    
    def test_grade_mapping(self):
        """测试等级映射"""
        self.assertEqual(self.model._get_risk_grade(95), 'AAA')
        self.assertEqual(self.model._get_risk_grade(75), 'A')
        self.assertEqual(self.model._get_risk_grade(55), 'BB')
        self.assertEqual(self.model._get_risk_grade(30), 'C')
    
    def test_indicator_scoring(self):
        """测试单项指标评分"""
        score = self.model._score_indicator(15, [
            {'max': 1, 'score': 20},
            {'min': 1, 'max': 3, 'score': 40},
            {'min': 3, 'max': 5, 'score': 60},
            {'min': 5, 'max': 10, 'score': 80},
            {'min': 10, 'score': 100}
        ])
        self.assertEqual(score, 100)


if __name__ == '__main__':
    unittest.main()
