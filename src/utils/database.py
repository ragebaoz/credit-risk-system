"""
数据库工具模块
管理 SQLite 客户主数据库
"""
import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "clients.db")


def get_connection() -> sqlite3.Connection:
    """获取数据库连接"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """初始化数据库表结构"""
    conn = get_connection()
    cursor = conn.cursor()
    
    # 客户主表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        credit_code TEXT UNIQUE,
        industry TEXT,
        region TEXT,
        contact_person TEXT,
        contact_phone TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 客户评估数据表（每次评估一条记录）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS client_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        evaluation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        -- 基础信用数据
        established_years REAL,
        registered_capital REAL,
        paid_in_capital_ratio REAL,
        abnormal_records INTEGER DEFAULT 0,
        penalty_records INTEGER DEFAULT 0,
        
        -- 财务数据
        debt_ratio REAL,
        current_ratio REAL,
        revenue_growth REAL,
        cash_flow REAL,
        net_margin REAL,
        
        -- 履约行为数据
        on_time_rate REAL,
        avg_overdue_days REAL,
        max_overdue_amount REAL,
        cooperation_years REAL,
        
        -- 外部风险数据
        lawsuit_count INTEGER DEFAULT 0,
        dishonest_records INTEGER DEFAULT 0,
        pledge_freeze REAL,
        negative_news INTEGER DEFAULT 0,
        
        -- 评估结果
        total_score REAL,
        risk_grade TEXT,
        suggested_days INTEGER,
        suggested_credit REAL,
        advance_ratio REAL,
        
        -- 预警信息JSON
        warnings TEXT,
        
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )
    ''')
    
    # 交易记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        invoice_date DATE,
        due_date DATE,
        actual_pay_date DATE,
        amount REAL,
        paid_amount REAL,
        status TEXT,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )
    ''')
    
    # 预警记录表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER NOT NULL,
        alert_type TEXT,
        alert_level TEXT,
        message TEXT,
        is_resolved BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        resolved_at TIMESTAMP,
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )
    ''')
    
    # 触发器：更新 updated_at
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS update_clients_timestamp
    AFTER UPDATE ON clients
    BEGIN
        UPDATE clients SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END
    ''')
    
    conn.commit()
    conn.close()
    print("数据库初始化完成")


def add_client(name: str, credit_code: Optional[str] = None, 
               industry: Optional[str] = None, region: Optional[str] = None,
               contact_person: Optional[str] = None, contact_phone: Optional[str] = None) -> int:
    """添加新客户，返回客户ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO clients (name, credit_code, industry, region, contact_person, contact_phone)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (name, credit_code, industry, region, contact_person, contact_phone))
    conn.commit()
    client_id = cursor.lastrowid
    conn.close()
    return client_id


def get_client(client_id: int) -> Optional[Dict[str, Any]]:
    """获取客户信息"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_client_by_credit_code(credit_code: str) -> Optional[Dict[str, Any]]:
    """通过统一社会信用代码获取客户"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients WHERE credit_code = ?", (credit_code,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def list_clients(status: Optional[str] = None) -> List[Dict[str, Any]]:
    """列出所有客户"""
    conn = get_connection()
    cursor = conn.cursor()
    if status:
        cursor.execute("SELECT * FROM clients WHERE status = ? ORDER BY created_at DESC", (status,))
    else:
        cursor.execute("SELECT * FROM clients ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_evaluation(client_id: int, data: Dict[str, Any], result: Dict[str, Any]) -> int:
    """保存评估结果"""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO client_evaluations (
        client_id, evaluation_date,
        established_years, registered_capital, paid_in_capital_ratio,
        abnormal_records, penalty_records,
        debt_ratio, current_ratio, revenue_growth, cash_flow, net_margin,
        on_time_rate, avg_overdue_days, max_overdue_amount, cooperation_years,
        lawsuit_count, dishonest_records, pledge_freeze, negative_news,
        total_score, risk_grade, suggested_days, suggested_credit, advance_ratio,
        warnings
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        client_id, datetime.now(),
        data.get('established_years'),
        data.get('registered_capital'),
        data.get('paid_in_capital_ratio'),
        data.get('abnormal_records', 0),
        data.get('penalty_records', 0),
        data.get('debt_ratio'),
        data.get('current_ratio'),
        data.get('revenue_growth'),
        data.get('cash_flow'),
        data.get('net_margin'),
        data.get('on_time_rate'),
        data.get('avg_overdue_days'),
        data.get('max_overdue_amount'),
        data.get('cooperation_years'),
        data.get('lawsuit_count', 0),
        data.get('dishonest_records', 0),
        data.get('pledge_freeze'),
        data.get('negative_news', 0),
        result['total_score'],
        result['risk_grade'],
        result['suggested_days'],
        result['suggested_credit'],
        result['advance_ratio'],
        json.dumps(result.get('warnings', []), ensure_ascii=False)
    ))
    
    eval_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return eval_id


def get_latest_evaluation(client_id: int) -> Optional[Dict[str, Any]]:
    """获取客户最新评估记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM client_evaluations 
    WHERE client_id = ? 
    ORDER BY evaluation_date DESC 
    LIMIT 1
    ''', (client_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        d = dict(row)
        d['warnings'] = json.loads(d.get('warnings', '[]'))
        return d
    return None


def get_evaluation_history(client_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """获取客户评估历史"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT * FROM client_evaluations 
    WHERE client_id = ? 
    ORDER BY evaluation_date DESC 
    LIMIT ?
    ''', (client_id, limit))
    rows = cursor.fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['warnings'] = json.loads(d.get('warnings', '[]'))
        result.append(d)
    return result


def add_alert(client_id: int, alert_type: str, alert_level: str, message: str):
    """添加预警记录"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO alerts (client_id, alert_type, alert_level, message)
    VALUES (?, ?, ?, ?)
    ''', (client_id, alert_type, alert_level, message))
    conn.commit()
    conn.close()


def get_unresolved_alerts() -> List[Dict[str, Any]]:
    """获取未解决的预警"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT a.*, c.name as client_name 
    FROM alerts a 
    JOIN clients c ON a.client_id = c.id 
    WHERE a.is_resolved = 0 
    ORDER BY a.created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
