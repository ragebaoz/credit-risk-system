"""
客户状态监控器
定期重新评估所有活跃客户，检测状态变化并触发预警
"""
import sys
import os
import schedule
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.evaluation.client_eval import ClientEvaluator
from src.utils.database import list_clients, get_latest_evaluation, add_alert, get_connection


class ClientWatcher:
    """
    客户状态监控器
    """
    
    def __init__(self):
        self.evaluator = ClientEvaluator()
    
    def check_all_clients(self):
        """
        检查所有活跃客户的状态
        """
        clients = list_clients(status='active')
        print(f"\n[{datetime.now()}] 开始监控检查，共 {len(clients)} 个活跃客户\n")
        
        alerts_triggered = []
        
        for client in clients:
            client_id = client['id']
            name = client['name']
            credit_code = client.get('credit_code')
            
            # 获取上次评估
            last_eval = get_latest_evaluation(client_id)
            
            if not last_eval:
                print(f"⚠️ {name}: 无历史评估记录，跳过")
                continue
            
            # 检查是否需要重新评估
            eval_date = datetime.strptime(last_eval['evaluation_date'], '%Y-%m-%d %H:%M:%S')
            days_since_eval = (datetime.now() - eval_date).days
            
            review_cycle = last_eval.get('review_cycle', 'quarterly')
            cycle_days = {
                'annual': 365,
                'semi_annual': 180,
                'quarterly': 90,
                'monthly': 30,
                'weekly': 7,
                'immediate': 1
            }.get(review_cycle, 90)
            
            if days_since_eval < cycle_days:
                print(f"✅ {name}: 距上次评估 {days_since_eval} 天，无需复核（周期: {cycle_days}天）")
                continue
            
            # 执行重新评估
            print(f"🔄 {name}: 正在重新评估...")
            try:
                result = self.evaluator.evaluate(
                    name=name,
                    credit_code=credit_code,
                    industry=client.get('industry'),
                    save=True
                )
                
                # 检查等级变化
                old_grade = last_eval['risk_grade']
                new_grade = result['risk_grade']
                old_score = last_eval['total_score']
                new_score = result['total_score']
                
                if old_grade != new_grade:
                    msg = f"风险等级变化: {old_grade} -> {new_grade} (评分: {old_score} -> {new_score})"
                    print(f"  🔴 {msg}")
                    add_alert(client_id, 'grade_change', 'red', msg)
                    alerts_triggered.append({'client': name, 'type': '等级变化', 'msg': msg})
                elif new_score < old_score - 10:
                    msg = f"评分显著下降: {old_score} -> {new_score}"
                    print(f"  🟠 {msg}")
                    add_alert(client_id, 'score_drop', 'orange', msg)
                    alerts_triggered.append({'client': name, 'type': '评分下降', 'msg': msg})
                else:
                    print(f"  ✅ 状态稳定 ({new_grade}, {new_score}分)")
                
                # 检查新触发的预警规则
                for w in result.get('warnings', []):
                    if w.get('level') in ['red', 'orange']:
                        msg = f"{w['name']}: {w['desc']}"
                        add_alert(client_id, w['name'], w['level'], msg)
                        alerts_triggered.append({'client': name, 'type': w['name'], 'msg': msg})
            
            except Exception as e:
                print(f"  ❌ 评估失败: {e}")
        
        print(f"\n[{datetime.now()}] 监控检查完成，触发 {len(alerts_triggered)} 条预警")
        return alerts_triggered
    
    def run_schedule(self):
        """
        启动定时监控
        默认每天上午9点执行一次检查
        """
        schedule.every().day.at("09:00").do(self.check_all_clients)
        
        print("监控调度器已启动，每天 09:00 执行检查")
        print("按 Ctrl+C 停止\n")
        
        while True:
            schedule.run_pending()
            time.sleep(60)


def generate_monitoring_report() -> str:
    """
    生成监控报告（HTML格式）
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 统计各等级客户数量
    cursor.execute('''
    SELECT risk_grade, COUNT(*) as count FROM client_evaluations
    WHERE id IN (
        SELECT MAX(id) FROM client_evaluations GROUP BY client_id
    )
    GROUP BY risk_grade
    ''')
    grade_dist = {r['risk_grade']: r['count'] for r in cursor.fetchall()}
    
    # 近期预警
    cursor.execute('''
    SELECT a.*, c.name as client_name 
    FROM alerts a 
    JOIN clients c ON a.client_id = c.id 
    WHERE a.is_resolved = 0 
    ORDER BY a.created_at DESC 
    LIMIT 20
    ''')
    alerts = cursor.fetchall()
    
    conn.close()
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>客户信用风险监控报告</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        h2 {{ color: #555; margin-top: 30px; }}
        .stats {{ display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }}
        .stat-card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; min-width: 150px; text-align: center; }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #007bff; }}
        .stat-label {{ color: #666; margin-top: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background: #f8f9fa; font-weight: bold; }}
        .badge {{ padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: bold; }}
        .badge-AAA {{ background: #28a745; color: white; }}
        .badge-AA {{ background: #5cb85c; color: white; }}
        .badge-A {{ background: #17a2b8; color: white; }}
        .badge-BBB {{ background: #ffc107; color: #333; }}
        .badge-BB {{ background: #fd7e14; color: white; }}
        .badge-B {{ background: #dc3545; color: white; }}
        .badge-C {{ background: #721c24; color: white; }}
        .alert-red {{ color: #dc3545; }}
        .alert-orange {{ color: #fd7e14; }}
        .alert-yellow {{ color: #ffc107; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 客户信用风险监控报告</h1>
        <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>风险等级分布</h2>
        <div class="stats">
    """
    
    for grade in ['AAA', 'AA', 'A', 'BBB', 'BB', 'B', 'C']:
        count = grade_dist.get(grade, 0)
        html += f'''
            <div class="stat-card">
                <div class="stat-value"><span class="badge badge-{grade}">{grade}</span></div>
                <div class="stat-label">{count} 家</div>
            </div>
        '''
    
    html += """
        </div>
        
        <h2>⚠️ 未处理预警</h2>
        <table>
            <tr>
                <th>客户名称</th>
                <th>预警类型</th>
                <th>等级</th>
                <th>预警内容</th>
                <th>发生时间</th>
            </tr>
    """
    
    for alert in alerts:
        level_class = f"alert-{alert['alert_level']}"
        html += f"""
            <tr>
                <td>{alert['client_name']}</td>
                <td>{alert['alert_type']}</td>
                <td class="{level_class}">{alert['alert_level'].upper()}</td>
                <td>{alert['message']}</td>
                <td>{alert['created_at']}</td>
            </tr>
        """
    
    html += """
        </table>
    </div>
</body>
</html>
    """
    
    return html


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='客户状态监控')
    parser.add_argument('--run-once', action='store_true', help='立即执行一次检查')
    parser.add_argument('--report', action='store_true', help='生成监控报告')
    parser.add_argument('--output', default='reports/monitoring_report.html', help='报告输出路径')
    
    args = parser.parse_args()
    
    watcher = ClientWatcher()
    
    if args.report:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        html = generate_monitoring_report()
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"📄 报告已生成: {args.output}")
    elif args.run_once:
        watcher.check_all_clients()
    else:
        watcher.run_schedule()
