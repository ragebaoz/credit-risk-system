"""
预警通知模块
支持邮件/钉钉/企业微信等多种通知方式
"""
import os
from typing import List, Dict, Any


class AlertNotifier:
    """
    预警通知器
    """
    
    def __init__(self):
        self.webhook_url = os.environ.get('DINGTALK_WEBHOOK')
        self.email_config = {
            'smtp_host': os.environ.get('SMTP_HOST'),
            'smtp_port': os.environ.get('SMTP_PORT', 587),
            'username': os.environ.get('SMTP_USER'),
            'password': os.environ.get('SMTP_PASS'),
            'to': os.environ.get('ALERT_EMAIL_TO', '').split(',')
        }
    
    def send_dingtalk(self, title: str, content: str):
        """
        发送钉钉机器人消息
        需配置 DINGTALK_WEBHOOK 环境变量
        """
        if not self.webhook_url:
            print("未配置钉钉 Webhook，跳过通知")
            return
        
        import requests
        import json
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": f"## {title}\n\n{content}"
            }
        }
        
        try:
            resp = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            print(f"钉钉通知发送结果: {resp.status_code}")
        except Exception as e:
            print(f"钉钉通知发送失败: {e}")
    
    def send_email(self, subject: str, body: str, to_list: List[str] = None):
        """
        发送邮件通知
        需配置 SMTP 相关环境变量
        """
        if not self.email_config['smtp_host']:
            print("未配置 SMTP，跳过邮件通知")
            return
        
        import smtplib
        from email.mime.text import MIMEText
        
        recipients = to_list or self.email_config['to']
        if not recipients:
            return
        
        msg = MIMEText(body, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = self.email_config['username']
        msg['To'] = ', '.join(recipients)
        
        try:
            with smtplib.SMTP(self.email_config['smtp_host'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['username'], self.email_config['password'])
                server.send_message(msg)
            print(f"邮件已发送至: {recipients}")
        except Exception as e:
            print(f"邮件发送失败: {e}")
    
    def notify_grade_change(self, client_name: str, old_grade: str, new_grade: str, score: float):
        """
        通知客户等级变化
        """
        title = f"⚠️ 客户风险等级变化: {client_name}"
        content = f"""
**客户名称**: {client_name}

**等级变化**: {old_grade} → {new_grade}

**当前评分**: {score}

**建议措施**: 
- 请立即复核该客户账期安排
- 考虑暂停新增发货
- 联系客户了解经营状况

请及时处理！
        """
        
        self.send_dingtalk(title, content)
        self.send_email(title, content.replace('\n', '<br>'))
    
    def notify_daily_summary(self, alerts: List[Dict[str, Any]]):
        """
        发送每日预警汇总
        """
        if not alerts:
            return
        
        title = f"📊 客户信用风险日报 ({len(alerts)} 条预警)"
        
        content = "### 今日预警汇总\n\n"
        for alert in alerts:
            content += f"- **{alert['client']}** | {alert['type']}: {alert['msg']}\n"
        
        self.send_dingtalk(title, content)
