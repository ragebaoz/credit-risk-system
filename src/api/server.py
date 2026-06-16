"""
Flask API 服务
提供 RESTful 接口供外部系统调用
"""
import sys
import os
from datetime import datetime
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.evaluation.client_eval import ClientEvaluator
from src.utils.database import (
    init_database, add_client, get_client, get_client_by_credit_code,
    list_clients, get_latest_evaluation, get_evaluation_history,
    get_unresolved_alerts
)

app = Flask(__name__)
evaluator = ClientEvaluator()


@app.route('/api/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})


@app.route('/api/clients', methods=['GET'])
def get_clients():
    """获取客户列表"""
    status = request.args.get('status')
    clients = list_clients(status)
    return jsonify({'data': clients, 'total': len(clients)})


@app.route('/api/clients', methods=['POST'])
def create_client():
    """创建新客户"""
    data = request.json
    client_id = add_client(
        name=data.get('name'),
        credit_code=data.get('credit_code'),
        industry=data.get('industry'),
        region=data.get('region'),
        contact_person=data.get('contact_person'),
        contact_phone=data.get('contact_phone')
    )
    return jsonify({'id': client_id, 'message': '客户创建成功'}), 201


@app.route('/api/clients/<int:client_id>', methods=['GET'])
def get_client_detail(client_id):
    """获取客户详情及最新评估"""
    client = get_client(client_id)
    if not client:
        return jsonify({'error': '客户不存在'}), 404
    
    latest_eval = get_latest_evaluation(client_id)
    history = get_evaluation_history(client_id, limit=5)
    
    return jsonify({
        'client': client,
        'latest_evaluation': latest_eval,
        'history': history
    })


@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    """
    执行信用评估
    
    请求体：
    {
        "name": "客户名称",
        "credit_code": "统一社会信用代码",
        "industry": "行业",
        "internal_data": {
            "on_time_rate": 0.85,
            "avg_overdue_days": 15,
            ...
        }
    }
    """
    data = request.json
    if not data or not data.get('name'):
        return jsonify({'error': '缺少客户名称'}), 400
    
    try:
        result = evaluator.evaluate(
            name=data['name'],
            credit_code=data.get('credit_code'),
            industry=data.get('industry'),
            internal_data=data.get('internal_data'),
            save=True
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/evaluate/quick', methods=['POST'])
def quick_evaluate():
    """
    快速评估（不保存，用于试算）
    """
    data = request.json
    if not data or not data.get('name'):
        return jsonify({'error': '缺少客户名称'}), 400
    
    try:
        result = evaluator.evaluate(
            name=data['name'],
            internal_data=data.get('internal_data'),
            save=False
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """获取未处理预警"""
    alerts = get_unresolved_alerts()
    return jsonify({'data': alerts, 'total': len(alerts)})


if __name__ == '__main__':
    # 确保数据库已初始化
    init_database()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"🚀 服务启动: http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
