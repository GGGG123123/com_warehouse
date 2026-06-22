"""实时告警通知模块"""

from loguru import logger
from typing import Optional
from datetime import datetime
import httpx


class AlertNotifier:
    """告警通知器 - 支持多种通知渠道"""

    def __init__(self):
        self.enabled = True

    def notify_error(self, error_type: str, message: str, context: Optional[dict] = None):
        """发送错误通知

        Args:
            error_type: 错误类型 (如 "DatabaseError", "AgentExecutionError")
            message: 错误信息
            context: 额外上下文信息
        """
        if not self.enabled:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alert_data = {
            "timestamp": timestamp,
            "type": error_type,
            "message": message,
            "context": context or {}
        }

        # 记录到日志
        logger.error(f"[ALERT] {error_type}: {message}", extra=alert_data)

        # TODO: 根据需要添加其他通知渠道
        # 1. 企业微信/钉钉机器人
        # self._send_to_wecom(alert_data)
        # 2. 邮件通知
        # self._send_email(alert_data)
        # 3. 短信通知(紧急情况)
        # self._send_sms(alert_data)

    def _send_to_wecom(self, alert_data: dict):
        """发送到企业微信机器人 (示例)"""
        webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"

        try:
            content = f"""**系统告警**
类型: {alert_data['type']}
时间: {alert_data['timestamp']}
详情: {alert_data['message']}"""

            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }

            httpx.post(webhook_url, json=payload, timeout=5.0)
        except Exception as e:
            logger.warning(f"企业微信通知失败: {e}")


# 全局通知器实例
alert_notifier = AlertNotifier()
