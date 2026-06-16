"""
评分卡模型
基于配置文件的评分卡，将各维度指标转换为标准分数
支持：零售客户检测、无真实数据时用替代指标
"""
from typing import Dict, Any, List
from ..utils.config_loader import get_weights_config


class ScorecardModel:
    """
    信用评分卡模型
    """
    
    def __init__(self):
        self.config = get_weights_config()
        self.dimensions = self.config['dimensions']
        self.risk_grades = self.config['risk_grades']
        self.credit_policies = self.config['credit_policies']
    
    def calculate_score(self, data: Dict[str, Any], policy_adjust: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        计算客户信用评分
        
        :param data: 客户各项指标数据
        :param policy_adjust: 策略调整参数（如新客户限制）
        :return: 包含总分、各维度得分、风险等级的结果字典
        """
        policy_adjust = policy_adjust or {}
        dimension_scores = {}
        dimension_details = {}
        
        # 预处理：确保评分卡需要的派生字段存在
        data = self._preprocess_for_scorecard(dict(data))
        
        # 检测是否为零售客户（门店>5家）
        is_retail = self._is_retail_customer(data)
        
        for dim_key, dim_config in self.dimensions.items():
            # 库存周转维度：门店<5家时得分直接为0
            if dim_key == 'inventory_turnover' and not is_retail:
                dim_score = 0
                dimension_scores[dim_key] = 0
                dimension_details[dim_key] = {
                    'name': dim_config['name'],
                    'weight': dim_config['weight'],
                    'score': 0,
                    'indicators': {},
                    'reason': '门店少于5家，库存周转维度得0分'
                }
                continue
            
            dim_score, indicators = self._calc_dimension_score(dim_key, dim_config, data)
            
            # 新客户规则：限制履约行为维度最高得分
            if dim_key == 'payment_behavior' and 'payment_behavior_max' in policy_adjust:
                max_score = policy_adjust['payment_behavior_max']
                if dim_score > max_score:
                    dim_score = max_score
                    dimension_details[dim_key] = {
                        'name': dim_config['name'],
                        'weight': dim_config['weight'],
                        'score': round(dim_score, 2),
                        'indicators': indicators,
                        'capped_by_new_client_rule': True,
                        'original_score': round(sum(
                            indicators[k]['score'] * indicators[k]['weight']
                            for k in indicators
                        ), 2)
                    }
                    dimension_scores[dim_key] = round(dim_score, 2)
                    continue
            
            dimension_scores[dim_key] = round(dim_score, 2)
            dimension_details[dim_key] = {
                'name': dim_config['name'],
                'weight': dim_config['weight'],
                'score': round(dim_score, 2),
                'indicators': indicators
            }
        
        # 根据客户类型选择权重
        weights = self._get_weights(is_retail)
        
        # 加权总分
        total_score = sum(
            dimension_scores[dim] * weights[dim]
            for dim in dimension_scores
        )
        total_score = round(total_score, 2)
        
        # 注意：天眼查评分已作为基础信用维度的指标参与加权（权重20%）
        # 不再进行全局微调，避免重复加权

        # 确定风险等级
        risk_grade = self._get_risk_grade(total_score)
        
        # 获取账期建议
        policy = self.credit_policies.get(risk_grade, self.credit_policies['C'])
        
        # 应用策略调整（新客户缩减）
        suggested_days = policy['days']
        suggested_credit = policy['max_credit']
        
        if 'days_reduce' in policy_adjust:
            suggested_days = max(0, suggested_days - policy_adjust['days_reduce'])
        if 'credit_reduce' in policy_adjust:
            suggested_credit = round(suggested_credit * policy_adjust['credit_reduce'])
        
        # 零售客户：应用门店规模系数
        if is_retail:
            store_count = data.get('dp_store_count', 0) or 0
            scale_multiplier = self._get_store_scale_multiplier(store_count)
            suggested_credit = round(suggested_credit * scale_multiplier)
        
        return {
            'total_score': total_score,
            'risk_grade': risk_grade,
            'dimension_scores': dimension_scores,
            'dimension_details': dimension_details,
            'suggested_days': suggested_days,
            'suggested_credit': suggested_credit,
            'advance_ratio': policy['advance_ratio'],
            'review_cycle': policy['review_cycle'],
            'policy_desc': policy['desc'],
            'policy_adjust': policy_adjust,
            'is_retail': is_retail
        }
    
    def _preprocess_for_scorecard(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        评分卡数据预处理：计算派生字段，确保必要字段存在
        """
        # 实缴资本（天眼查网页直接显示，直接使用原始值）
        data.setdefault('paid_in_capital', 0)
        
        # 资金链断裂风险
        restriction = data.get('restriction_count', 0) or 0
        executed = data.get('executed_count', 0) or 0
        pledge_freeze = data.get('pledge_freeze_count', 0) or 0
        data['sudden_death_risk'] = (1 if restriction > 0 else 0) + (1 if executed > 0 else 0) + (1 if pledge_freeze > 0 else 0)
        
        # 确保基础字段存在
        data.setdefault('executed_count', 0)
        data.setdefault('restriction_count', 0)
        data.setdefault('pledge_freeze_count', 0)
        
        # 工商存续状态转数值（供评分卡使用）
        status = data.get('company_status', '')
        if isinstance(status, str):
            status_norm = status.strip()
            if '存续' in status_norm or '在业' in status_norm:
                data['company_status'] = 1
            else:
                data['company_status'] = 0
        
        # 大众点评暂停营业比例
        dp_total = data.get('dp_store_count', 0) or 0
        dp_paused = data.get('dp_paused_count', 0) or 0
        data['dp_pause_ratio'] = dp_paused / dp_total if dp_total > 0 else 0.0
        
        # 企业规模分类（用于诉讼和舆情动态评分）
        data['company_size'] = self._classify_size(data)
        
        # 关联公司代理指标（如果未提供，用 around_risk_count 代理）
        around_risk = data.get('around_risk_count', 0) or 0
        if 'affiliated_company_count' not in data:
            data['affiliated_company_count'] = around_risk
        if 'affiliated_company_health' not in data:
            data['affiliated_company_health'] = around_risk
        
        return data
    
    def _classify_size(self, data: Dict[str, Any]) -> str:
        """企业规模分类（基于注册资本，B2B企业门店=0是正常的，不纳入判断）"""
        capital = data.get('registered_capital', 0) or 0
        insured = data.get('insured_count', 0) or 0
        if capital >= 100000000 or insured >= 1000:
            return 'large'
        if capital < 5000000 and insured < 50:
            return 'micro'
        return 'sme'
    
    def _is_retail_customer(self, data: Dict[str, Any]) -> bool:
        """
        检测是否为零售客户（C端连锁，门店>5家）
        """
        store_count = data.get('dp_store_count', 0) or 0
        return store_count > 5
    
    def _get_weights(self, is_retail: bool) -> Dict[str, float]:
        """
        获取维度权重
        统一使用配置权重，所有客户都评估5个维度
        库存周转维度在门店<5家时得0分
        """
        return {
            dim: cfg['weight']
            for dim, cfg in self.dimensions.items()
        }
    
    def _calc_dimension_score(self, dim_key: str, dim_config: Dict[str, Any], 
                              data: Dict[str, Any]) -> tuple:
        """
        计算单个维度得分
        """
        indicators_result = {}
        weighted_sum = 0
        
        # 公司规模维度：计算实缴资本（注册资本 × 实缴比例）
        if dim_key == 'company_scale':
            reg_cap = data.get('registered_capital', 0) or 0
            paid_ratio = data.get('paid_in_capital_ratio', 0) or 0
            data['paid_in_capital'] = reg_cap * paid_ratio
        
        # 财务健康维度：无真实数据时，真实财务指标给缺省分10，只计算替代指标
        if dim_key == 'financial_health':
            has_real_data = any(
                data.get(k) is not None
                for k in ['debt_ratio', 'current_ratio', 'revenue_growth', 'cash_flow', 'net_margin']
            )
            if not has_real_data:
                # 无真实财报：真实财务指标给缺省分10，正常计算 sudden_death_risk / self_risk_count
                for ind_key, ind_config in dim_config['indicators'].items():
                    value = data.get(ind_key)
                    if ind_key in ('sudden_death_risk', 'self_risk_count'):
                        score = self._score_indicator(value, ind_config['scoring'])
                    else:
                        # 真实财务指标，无数据时给缺省分10
                        score = 10.0 if value is None else self._score_indicator(value, ind_config['scoring'])
                    weighted_sum += score * ind_config['weight']
                    indicators_result[ind_key] = {
                        'name': ind_config['name'],
                        'value': value,
                        'score': score,
                        'weight': ind_config['weight'],
                        'fallback': ind_key not in ('sudden_death_risk', 'self_risk_count') and value is None
                    }
                return weighted_sum, indicators_result
        
        # 履约行为维度：无内部数据时，内部指标给缺省分10
        if dim_key == 'payment_behavior':
            has_internal_data = data.get('on_time_rate') is not None
            if not has_internal_data:
                for ind_key, ind_config in dim_config['indicators'].items():
                    value = data.get(ind_key)
                    if ind_key in ('on_time_rate', 'avg_overdue_days', 'max_overdue_amount'):
                        # 内部指标，无数据时给缺省分10
                        score = 10.0 if value is None else self._score_indicator(value, ind_config['scoring'])
                    else:
                        # 外部替代指标正常计算
                        score = self._score_indicator(value, ind_config['scoring'])
                    weighted_sum += score * ind_config['weight']
                    indicators_result[ind_key] = {
                        'name': ind_config['name'],
                        'value': value,
                        'score': score,
                        'weight': ind_config['weight'],
                        'fallback': ind_key in ('on_time_rate', 'avg_overdue_days', 'max_overdue_amount') and value is None
                    }
                return weighted_sum, indicators_result
        
        # 默认计算
        company_size = data.get('company_size', 'micro')
        store_count = data.get('dp_store_count', 0) or 0
        for ind_key, ind_config in dim_config['indicators'].items():
            value = data.get(ind_key)
            if dim_key == 'external_risk' and ind_key == 'lawsuit_count':
                score = self._score_lawsuit(value, company_size)
            elif dim_key == 'external_risk' and ind_key == 'negative_news':
                score = self._score_negative_news(value, company_size, store_count)
            else:
                score = self._score_indicator(value, ind_config['scoring'])
            weighted_sum += score * ind_config['weight']
            indicators_result[ind_key] = {
                'name': ind_config['name'],
                'value': value,
                'score': score,
                'weight': ind_config['weight']
            }
        
        return weighted_sum, indicators_result
    
    def _score_indicator(self, value, scoring_rules: List[Dict]) -> float:
        """
        根据评分规则计算单项指标得分
        """
        if value is None:
            return 10  # 数据缺失时给缺省分10（严格策略）
        
        try:
            value = float(value)
        except (ValueError, TypeError):
            return 50
        
        for rule in scoring_rules:
            min_val = rule.get('min')
            max_val = rule.get('max')
            
            match = True
            if min_val is not None and value < min_val:
                match = False
            if max_val is not None and value > max_val:
                match = False
            
            if match:
                return float(rule['score'])
        
        # 未匹配任何规则，返回最低分
        return 0

    def _score_lawsuit(self, count, company_size: str) -> float:
        """按企业规模动态评分诉讼数量"""
        count = count or 0
        if company_size == 'large':
            if count >= 30: return 0
            if count >= 15: return 25
            if count >= 5: return 50
            if count >= 1: return 75
            return 100
        elif company_size == 'sme':
            if count >= 10: return 0
            if count >= 5: return 25
            if count >= 2: return 50
            if count >= 1: return 75
            return 100
        else:  # micro
            if count >= 3: return 0
            if count >= 2: return 30
            if count >= 1: return 60
            return 100
    
    def _score_negative_news(self, count, company_size: str, store_count: int) -> float:
        """按企业规模动态评分负面舆情，大型企业看密度（条数/门店数）"""
        count = count or 0
        store_count = store_count or 0
        if company_size == 'large' and store_count > 0:
            density = count / store_count
            if density >= 5: return 0
            if density >= 2: return 30
            if density >= 1: return 60
            if density >= 0.5: return 80
            return 100
        elif company_size == 'sme':
            if count >= 20: return 0
            if count >= 10: return 30
            if count >= 5: return 55
            if count >= 1: return 80
            return 100
        else:  # micro
            if count >= 5: return 0
            if count >= 3: return 30
            if count >= 1: return 60
            return 100

    def _get_risk_grade(self, score: float) -> str:
        """根据总分确定风险等级"""
        for grade, config in self.risk_grades.items():
            if config['min'] <= score <= config['max']:
                return grade
        return 'C'
    
    def _get_store_scale_multiplier(self, store_count: int) -> float:
        """
        门店规模系数 — 零售客户授信额度放大器
        <10家=0倍, 50家=1倍, 1000家=5倍, 其余线性插值
        """
        if store_count < 10:
            return 0.0
        if store_count >= 1000:
            return 5.0
        if store_count < 50:
            # 10-50家: 从0倍线性增长到1倍
            return (store_count - 10) / 40.0
        # 50-1000家: 从1倍线性增长到5倍
        return 1.0 + (store_count - 50) / 950.0 * 4.0
    
    def get_grade_description(self, grade: str) -> str:
        """获取等级描述"""
        return self.risk_grades.get(grade, {}).get('desc', '未知')
