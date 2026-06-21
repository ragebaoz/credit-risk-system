"""
单客户评估执行器
整合数据收集、评分模型、规则引擎，输出最终评估结果
"""
import sys
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.collectors.enterprise import EnterpriseCollector
from src.collectors.financial import FinancialCollector
from src.collectors.judicial import JudicialCollector
from src.collectors.news import NewsCollector
from src.collectors.browser_aiqicha import AiQichaEnterpriseCollector
from src.collectors.opencli_tianyancha_browser import OpenCLITianYanChaCollector, TianYanChaEnterpriseCollector
from src.collectors.opencli_browser import OpenCLIBrowser
from src.collectors.browser_manager import ensure_opencli_browser
from src.models.scorecard import ScorecardModel
from src.models.rules import RulesEngine
from src.utils.database import (
    add_client, get_client, get_client_by_credit_code,
    save_evaluation, get_latest_evaluation
)
from src.utils.validators import validate_credit_code


class ClientEvaluator:
    """
    客户信用评估器
    """
    
    def __init__(self, api_key: Optional[str] = None, use_opencli: bool = True, use_browser: bool = False, headless: bool = True, new_client: bool = False):
        self.use_opencli = use_opencli
        self.use_browser = use_browser
        self.headless = headless
        self.new_client = new_client
        self._opencli_browser: Optional[OpenCLIBrowser] = None
        
        # 模式优先级: OpenCLI Browser > API/模拟数据
        if use_opencli:
            print("[评估器] 尝试使用 OpenCLI Browser 模式（复用你当前的 Chrome + 登录态）")
            browser_status = ensure_opencli_browser(workspace="default")
            if browser_status["ok"]:
                print(f"[评估器] ✅ OpenCLI Browser 已就绪 (workspace={browser_status['workspace']})")
                self.enterprise_collector = TianYanChaEnterpriseCollector(workspace=browser_status["workspace"])
                self._opencli_browser = OpenCLIBrowser(workspace=browser_status["workspace"])
                self.dianping_collector = self._opencli_browser
                # OpenCLI 浏览器模式同时覆盖部分司法数据
                self.judicial_collector = None
                self.use_browser = True  # 标记为浏览器模式，用于后续逻辑判断
            else:
                print(f"[评估器] ⚠️ OpenCLI Browser 不可用: {browser_status.get('error', 'unknown')}")
                print("[评估器] OpenCLI Browser 不可用，回退到 API/模拟数据模式")
                self.enterprise_collector = EnterpriseCollector(api_key)
                self.dianping_collector = None
                self.judicial_collector = JudicialCollector(api_key)
        else:
            print("[评估器] 使用 API/模拟数据模式")
            self.enterprise_collector = EnterpriseCollector(api_key)
            self.dianping_collector = None
            self.judicial_collector = JudicialCollector(api_key)
        
        self.financial_collector = FinancialCollector(api_key)
        self.news_collector = NewsCollector(api_key)
        self.scorecard = ScorecardModel()
        self.rules_engine = RulesEngine()
    
    def evaluate(self, name: str, credit_code: Optional[str] = None,
                 industry: Optional[str] = None,
                 financial_excel: Optional[str] = None,
                 internal_data: Optional[Dict[str, Any]] = None,
                 save: bool = True) -> Dict[str, Any]:
        """
        执行客户信用评估
        
        :param name: 客户名称
        :param credit_code: 统一社会信用代码（可选，用于信息收集）
        :param industry: 行业类型
        :param financial_excel: 财务报表路径
        :param internal_data: 内部交易数据（如历史回款记录）
        :param save: 是否保存到数据库
        :return: 评估结果字典
        """
        print(f"\n{'='*60}")
        print(f"开始评估客户: {name}")
        print(f"{'='*60}\n")
        
        # 1. 收集数据
        raw_data = self._collect_data(name, credit_code, financial_excel, internal_data)
        if industry:
            raw_data['industry'] = industry
        
        print("\n【收集到的原始数据】")
        for k, v in raw_data.items():
            print(f"  {k}: {v}")
        
        # 2. 规则引擎预处理（获取新客户策略调整）
        _, _, _, policy_adjust = self.rules_engine.evaluate(raw_data, 'A', 100)
        
        # 3. 评分卡计算
        score_result = self.scorecard.calculate_score(raw_data, policy_adjust)
        print(f"\n【评分卡结果】")
        print(f"  总分: {score_result['total_score']}")
        print(f"  基础等级: {score_result['risk_grade']}")
        for dim, score in score_result['dimension_scores'].items():
            detail = score_result['dimension_details'].get(dim, {})
            print(f"  - {dim}: {score}分")
        if score_result.get('is_retail'):
            print(f"  [零售客户] 已激活库存周转维度")
        
        # 4. 规则引擎最终评估
        final_grade, veto_rules, warnings, _ = self.rules_engine.evaluate(
            raw_data, score_result['risk_grade'], score_result['total_score']
        )
        
        print(f"\n【规则引擎】")
        if veto_rules:
            print(f"  ⚠️ 触发否决规则:")
            for r in veto_rules:
                print(f"    - {r['name']}: {r['desc']}")
        if final_grade != score_result['risk_grade']:
            print(f"  等级调整: {score_result['risk_grade']} -> {final_grade}")
        
        if warnings:
            print(f"  🔔 触发预警:")
            for w in warnings:
                level_emoji = {'red': '🔴', 'orange': '🟠', 'yellow': '🟡', 'info': 'ℹ️'}.get(w['level'], '⚪')
                print(f"    {level_emoji} [{w.get('level', '')}] {w['name']}: {w['desc']}")
        
        # 4.5 如果规则引擎调整了等级（保底或否决），同步更新账期建议
        if final_grade != score_result['risk_grade']:
            final_policy = self.scorecard.credit_policies.get(final_grade, self.scorecard.credit_policies['C'])
            score_result['suggested_days'] = final_policy['days']
            score_result['suggested_credit'] = final_policy['max_credit']
            score_result['advance_ratio'] = final_policy['advance_ratio']
            score_result['review_cycle'] = final_policy['review_cycle']
            score_result['policy_desc'] = final_policy['desc']
            # 重新应用策略调整（新客户缩减）
            policy_adjust = score_result.get('policy_adjust', {})
            if 'days_reduce' in policy_adjust:
                score_result['suggested_days'] = max(0, score_result['suggested_days'] - policy_adjust['days_reduce'])
            if 'credit_reduce' in policy_adjust:
                score_result['suggested_credit'] = round(score_result['suggested_credit'] * policy_adjust['credit_reduce'])
            # 重新应用门店规模系数（零售客户）
            if score_result.get('is_retail'):
                store_count = raw_data.get('dp_store_count', 0) or 0
                scale_multiplier = self.scorecard._get_store_scale_multiplier(store_count)
                score_result['suggested_credit'] = round(score_result['suggested_credit'] * scale_multiplier)
        
        # 5. 整合结果
        result = {
            'client_name': name,
            'credit_code': credit_code,
            'evaluation_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_score': score_result['total_score'],
            'base_grade': score_result['risk_grade'],
            'risk_grade': final_grade,
            'suggested_days': score_result['suggested_days'],
            'suggested_credit': score_result['suggested_credit'],
            'advance_ratio': score_result['advance_ratio'],
            'review_cycle': score_result['review_cycle'],
            'policy_desc': score_result['policy_desc'],
            'policy_adjust': score_result.get('policy_adjust', {}),
            'dimension_scores': score_result['dimension_scores'],
            'dimension_details': score_result['dimension_details'],
            'veto_rules': veto_rules,
            'warnings': warnings,
            'raw_data': raw_data,
            'is_retail': score_result.get('is_retail', False)
        }
        
        # 6. 保存到数据库
        if save and credit_code:
            client = get_client_by_credit_code(credit_code)
            if not client:
                client_id = add_client(
                    name=name,
                    credit_code=credit_code,
                    industry=industry,
                    contact_info='',
                    notes=''
                )
            else:
                client_id = client['id']
            
            eval_id = save_evaluation(client_id, raw_data, result)
            result['evaluation_id'] = eval_id
            print(f"\n✅ 评估结果已保存 (ID: {eval_id})")
        
        return result
    
    def _collect_data(self, name: str, credit_code: Optional[str], 
                      financial_excel: Optional[str],
                      internal_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        收集所有维度的数据
        """
        data = {}
        
        # 收集外部数据：API模式需要信用代码，浏览器模式可通过公司名称搜索
        should_collect = (credit_code and validate_credit_code(credit_code)) or self.use_browser
        if should_collect:
            print(f"正在收集企业信息...")
            data.update(self.enterprise_collector.collect(credit_code, name))
            
            print(f"正在收集财务信息...")
            data.update(self.financial_collector.collect(credit_code, name, financial_excel))
            
            if self.judicial_collector:
                print(f"正在收集司法风险信息...")
                data.update(self.judicial_collector.collect(credit_code, name))
            
            # 浏览器模式已从详情页获取舆情数据，不再调用 news_collector 覆盖
            if not self.use_browser:
                print(f"正在收集舆情信息...")
                data.update(self.news_collector.collect(credit_code, name))
            
            # 浏览器模式下自动抓取大众点评门店数据
            if self.dianping_collector and not data.get('dp_store_count'):
                print(f"正在抓取大众点评门店数据...")
                try:
                    if isinstance(self.dianping_collector, OpenCLIBrowser):
                        # OpenCLI Browser 模式：调用 dianping_search_multi_cities
                        dp_result = self.dianping_collector.dianping_search_multi_cities(name)
                        dp_data = {
                            "dp_store_count": dp_result.get("total_store_count"),
                            "dp_paused_count": dp_result.get("total_paused_count"),
                            "dp_avg_rating": dp_result.get("avg_rating_across_cities"),
                        }
                    else:
                        dp_data = self.dianping_collector.collect(name)
                    # 只填充用户未提供的字段
                    for k, v in dp_data.items():
                        if k not in data or data[k] is None:
                            data[k] = v
                except Exception as e:
                    print(f"[评估器] 大众点评抓取失败: {e}，继续评估（请手动提供门店数据）")
        else:
            print("未提供有效统一社会信用代码，跳过外部数据收集")
            # 填充默认值
            data = {
                'established_years': None,
                'registered_capital': None,
                'paid_in_capital_ratio': None,
                'abnormal_records': 0,
                'penalty_records': 0,
                'debt_ratio': None,
                'current_ratio': None,
                'revenue_growth': None,
                'cash_flow': None,
                'net_margin': None,
                'lawsuit_count': 0,
                'dishonest_records': 0,
                'pledge_freeze': 0,
                'negative_news': 0
            }
        
        # 合并内部交易数据
        if internal_data:
            print("合并内部交易数据...")
            data.update(internal_data)
        
        # 设置履约行为默认值（无论是否有 internal_data）
        if self.new_client:
            print("新客户模式：无历史交易数据，采用保守估计...")
            # 注意：不再填充 on_time_rate/avg_overdue_days/max_overdue_amount 虚假默认值
            # 这些指标将由外部替代指标（executed_count, restriction_count）支撑
            data.setdefault('on_time_rate', None)
            data.setdefault('avg_overdue_days', None)
            data.setdefault('max_overdue_amount', None)
            data.setdefault('cooperation_years', 0)
        else:
            # 默认内部数据（有交易但用户未提供明细）
            print("未提供内部交易数据，使用系统默认值（请尽快替换为真实数据）...")
            # 同样不再填充虚假默认值
            data.setdefault('on_time_rate', None)
            data.setdefault('avg_overdue_days', None)
            data.setdefault('max_overdue_amount', None)
            data.setdefault('cooperation_years', 2)
        
        return data


def print_report(result: Dict[str, Any]):
    """打印评估报告"""
    print(f"\n{'='*60}")
    print(f"信用评估报告")
    print(f"{'='*60}")
    print(f"客户名称: {result['client_name']}")
    print(f"评估时间: {result['evaluation_date']}")
    print(f"{'-'*60}")
    print(f"综合评分: {result['total_score']} / 100")
    print(f"风险等级: {result['risk_grade']}")
    if result.get('is_retail'):
        print(f"客户类型: 零售客户（已评估库存周转）")
    print(f"{'-'*60}")
    print(f"💰 账期建议:")
    print(f"   建议账期: {result['suggested_days']} 天")
    print(f"   建议授信: ¥{result['suggested_credit']:,.0f}")
    print(f"   复核周期: {result['review_cycle']}")
    print(f"   管理措施: {result['policy_desc']}")
    print(f"{'-'*60}")
    print(f"📊 各维度得分:")
    for dim, score in result['dimension_scores'].items():
        detail = result['dimension_details'].get(dim, {})
        print(f"   {detail.get('name', dim)}: {score}分 (权重{detail.get('weight', 0)*100:.0f}%)")
    
    # 指标级打分
    print(f"\n📋 指标级打分明细:")
    for dim, indicators in result.get('indicator_scores', {}).items():
        dim_name = result.get('dimension_details', {}).get(dim, {}).get('name', dim)
        print(f"   [{dim_name}]")
        for ind_key, ind_data in indicators.items():
            raw = ind_data.get('raw_value', 'N/A')
            score = ind_data.get('score', 0)
            weight = ind_data.get('weight', 0)
            print(f"      {ind_key}: 原始值={raw}, 得分={score}, 权重={weight*100:.0f}%")
    
    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='客户信用评估工具')
    parser.add_argument('--name', required=True, help='客户名称')
    parser.add_argument('--credit-code', help='统一社会信用代码')
    parser.add_argument('--industry', help='行业类型')
    parser.add_argument('--financial', help='财务报表Excel路径')
    parser.add_argument('--opencli', action='store_true', default=True, help='使用 OpenCLI Browser 模式（默认开启，复用当前 Chrome）')
    parser.add_argument('--no-opencli', action='store_true', help='禁用 OpenCLI Browser，回退到 API/模拟数据模式')
    parser.add_argument('--browser', action='store_true', help='已废弃，不再支持 Playwright CDP 模式')
    parser.add_argument('--no-headless', action='store_true', help='浏览器可视化模式（调试用）')
    parser.add_argument('--new-client', action='store_true', help='首次合作客户（无历史交易数据）')
    parser.add_argument('--no-save', action='store_true', help='不保存到数据库')
    
    # 零售客户库存周转参数
    parser.add_argument('--inventory-days', type=int, help='库存周转天数（零售客户）')
    parser.add_argument('--sales-trend', type=float, help='近3月销售环比（如-0.2表示下滑20%）')
    
    # 大众点评数据（可手动传入）
    parser.add_argument('--dp-store-count', type=int, help='大众点评门店总数')
    parser.add_argument('--dp-paused-count', type=int, help='大众点评暂停营业门店数')
    parser.add_argument('--dp-avg-rating', type=float, help='大众点评平均评分')
    parser.add_argument('--dp-total-reviews', type=int, help='大众点评总评论数')
    parser.add_argument('--dp-avg-price', type=int, help='大众点评平均客单价')
    parser.add_argument('--dp-high-end-ratio', type=float, help='大众点评高端店铺占比(0-1)')
    
    args = parser.parse_args()
    
    # 构建内部数据（包含库存周转和大众点评数据）
    internal_data = {}
    if args.inventory_days is not None:
        internal_data['inventory_turnover_days'] = args.inventory_days
    if args.sales_trend is not None:
        internal_data['recent_sales_trend'] = args.sales_trend
    if args.dp_store_count is not None:
        internal_data['dp_store_count'] = args.dp_store_count
    if args.dp_paused_count is not None:
        internal_data['dp_paused_count'] = args.dp_paused_count
    if args.dp_avg_rating is not None:
        internal_data['dp_avg_rating'] = args.dp_avg_rating
    if args.dp_total_reviews is not None:
        internal_data['dp_total_reviews'] = args.dp_total_reviews
    if args.dp_avg_price is not None:
        internal_data['dp_avg_price'] = args.dp_avg_price
    if args.dp_high_end_ratio is not None:
        internal_data['dp_high_end_ratio'] = args.dp_high_end_ratio
    
    evaluator = ClientEvaluator(
        use_opencli=not args.no_opencli,
        use_browser=args.browser,
        headless=not args.no_headless,
        new_client=args.new_client
    )
    result = evaluator.evaluate(
        name=args.name,
        credit_code=args.credit_code,
        industry=args.industry,
        financial_excel=args.financial,
        internal_data=internal_data if internal_data else None,
        save=not args.no_save
    )
    
    print_report(result)
