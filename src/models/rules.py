"""
规则引擎
处理硬性规则和预警规则
支持按企业规模分层的诉讼阈值 + 诉讼类型加权
"""
import re
from typing import Dict, Any, List, Tuple
from ..utils.config_loader import get_rules_config


class RulesEngine:
    """
    信用评估规则引擎
    支持硬性否决规则和预警规则
    新增：企业规模分层、诉讼类型加权
    """
    
    def __init__(self):
        self.config = get_rules_config()
        self.hard_rules = self.config.get('hard_rules', {})
        self.warning_rules = self.config.get('warning', {})
        self.industry_adjustments = self.config.get('industry_adjustments', {})
    
    def evaluate(self, data: Dict[str, Any], base_grade: str, score: float) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """
        执行规则评估
        
        :param data: 客户数据
        :param base_grade: 评分卡给出的基础等级
        :param score: 基础分数
        :return: (调整后等级, 触发的否决规则列表, 触发的预警列表, 策略调整参数)
        """
        # 预处理：计算企业规模和加权诉讼分
        data = self._preprocess_data(data)
        
        triggered_veto = []
        triggered_warnings = []
        final_grade = base_grade
        policy_adjust = {}
        
        # 执行否决规则
        for rule in self.hard_rules.get('veto', []):
            if self._check_condition(rule['condition'], data):
                triggered_veto.append({
                    'name': rule['name'],
                    'desc': rule['desc'],
                    'action': rule['action']
                })
                action_grade = rule['action'].replace('grade_max:', '').strip()
                if self._grade_value(action_grade) < self._grade_value(final_grade):
                    final_grade = action_grade
        
        # 执行头部企业保底规则（渠道话语权保护）
        for rule in self.hard_rules.get('head_enterprise', []):
            if self._check_condition(rule['condition'], data):
                triggered_veto.append({
                    'name': rule['name'],
                    'desc': rule['desc'],
                    'action': rule['action']
                })
                action = rule['action']
                if 'grade_min:' in action:
                    action_grade = action.replace('grade_min:', '').strip()
                    if self._grade_value(action_grade) > self._grade_value(final_grade):
                        final_grade = action_grade
                elif 'grade_max:' in action:
                    action_grade = action.replace('grade_max:', '').strip()
                    if self._grade_value(action_grade) < self._grade_value(final_grade):
                        final_grade = action_grade
        
        # 执行预警规则
        for rule in self.hard_rules.get('warning', []):
            if self._check_condition(rule['condition'], data):
                triggered_warnings.append({
                    'name': rule['name'],
                    'desc': rule['desc'],
                    'level': rule['level']
                })
        
        # 执行新客户规则
        for rule in self.hard_rules.get('new_client', []):
            if self._check_condition(rule['condition'], data):
                triggered_warnings.append({
                    'name': rule['name'],
                    'desc': rule['desc'],
                    'level': 'yellow',
                    'action': rule.get('action', ''),
                    'policy_adjust': rule.get('policy_adjust', '')
                })
                action = rule.get('action', '')
                if 'payment_behavior_score_max:' in action:
                    max_score = float(action.replace('payment_behavior_score_max:', '').strip())
                    policy_adjust['payment_behavior_max'] = max_score
                pa = rule.get('policy_adjust', '')
                if 'days_reduce:' in pa:
                    m = re.search(r'days_reduce:\s*(\d+)', pa)
                    if m:
                        policy_adjust['days_reduce'] = int(m.group(1))
                if 'credit_reduce:' in pa:
                    m = re.search(r'credit_reduce:\s*([\d.]+)', pa)
                    if m:
                        policy_adjust['credit_reduce'] = float(m.group(1))
        
        # 行业调整
        industry = data.get('industry', '')
        if industry in self.industry_adjustments:
            adj = self.industry_adjustments[industry]
            triggered_warnings.append({
                'name': '行业调整',
                'desc': adj['desc'],
                'level': 'info',
                'multiplier': adj['multiplier']
            })
        
        return final_grade, triggered_veto, triggered_warnings, policy_adjust
    
    def _preprocess_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        预处理数据：计算企业规模、加权诉讼分、替代指标等
        """
        data = dict(data)  # 复制避免修改原始数据
        
        # 1. 企业规模分类
        data['company_size'] = self._classify_size(data)
        
        # 2. 诉讼类型加权分
        data['weighted_lawsuit_score'] = self._calc_weighted_lawsuit_score(data)
        
        # 3. 买卖合同纠纷占比
        lawsuit_count = data.get('lawsuit_count', 0) or 0
        contract_dispute = data.get('contract_dispute_count', 0) or 0
        data['contract_dispute_ratio'] = contract_dispute / lawsuit_count if lawsuit_count > 0 else 0.0
        
        # 4. 资金链断裂风险综合指标（限高 + 被执行 + 股权冻结）
        restriction = data.get('restriction_count', 0) or 0
        executed = data.get('executed_count', 0) or 0
        pledge_freeze = data.get('pledge_freeze_count', 0) or 0
        data['sudden_death_risk'] = (1 if restriction > 0 else 0) + (1 if executed > 0 else 0) + (1 if pledge_freeze > 0 else 0)
        # 确保规则条件表达式解析时能替换到这些字段
        data['executed_count'] = executed
        data['restriction_count'] = restriction
        data['pledge_freeze_count'] = pledge_freeze
        
        # 5. 实缴资本（天眼查网页直接显示，直接使用原始值）
        data.setdefault('paid_in_capital', 0)
        
        # 5. 大众点评暂停营业比例
        dp_total = data.get('dp_store_count', 0) or 0
        dp_paused = data.get('dp_paused_count', 0) or 0
        data['dp_pause_ratio'] = dp_paused / dp_total if dp_total > 0 else 0.0
        
        return data
    
    def _classify_size(self, data: Dict[str, Any]) -> str:
        """
        企业规模分类
        :return: 'micro' | 'sme' | 'large'
        """
        capital = data.get('registered_capital', 0) or 0
        store_count = data.get('dp_store_count', 0) or 0
        
        # 大型：注册资本≥1亿 或 门店>200家
        if capital >= 100000000 or store_count > 200:
            return 'large'
        # 微型：注册资本<500万 且 门店<10家
        if capital < 5000000 and store_count < 10:
            return 'micro'
        # 其余为中小企业
        return 'sme'
    
    def _calc_weighted_lawsuit_score(self, data: Dict[str, Any]) -> float:
        """
        诉讼类型加权得分
        买卖合同纠纷 ×3，借款/金融 ×2，其他 ×1
        当前简化版：用 contract_dispute_count ×3 + (lawsuit_count - contract_dispute_count) ×1
        """
        lawsuit_count = data.get('lawsuit_count', 0) or 0
        contract_dispute = data.get('contract_dispute_count', 0) or 0
        other = max(0, lawsuit_count - contract_dispute)
        return contract_dispute * 3.0 + other * 1.0
    
    def _check_condition(self, condition: str, data: Dict[str, Any]) -> bool:
        """
        简单条件表达式解析
        支持: >, <, >=, <=, ==, !=, AND, OR
        """
        try:
            expr = condition
            for key, val in data.items():
                if isinstance(val, str):
                    expr = expr.replace(key, f"'{val}'")
                else:
                    expr = expr.replace(key, str(val))
            
            expr = expr.replace(' AND ', ' and ').replace(' OR ', ' or ')
            return bool(eval(expr, {"__builtins__": {}}, {}))
        except:
            return False
    
    def _grade_value(self, grade: str) -> int:
        """
        等级转换为数值，用于比较
        AAA=6, AA=5, A=4, BBB=3, BB=2, B=1, C=0
        """
        mapping = {'AAA': 6, 'AA': 5, 'A': 4, 'BBB': 3, 'BB': 2, 'B': 1, 'C': 0}
        return mapping.get(grade, -1)
