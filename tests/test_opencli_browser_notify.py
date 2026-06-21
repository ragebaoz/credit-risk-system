"""
Tests for OpenCLI browser anti-bot notification integration.
"""
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.collectors.opencli_browser import OpenCLIBrowser


def test_tianyancha_search_notifies_on_antibot():
    """当天眼查触发反爬/验证码时，应调用 notify_user 通知用户。"""
    browser = OpenCLIBrowser(workspace="default")
    browser.goto = MagicMock()
    browser._get_current_url = MagicMock(return_value="https://antirobot.tianyancha.com")
    browser.get_text = MagicMock(return_value="请输入验证码完成验证")

    with patch("src.collectors.opencli_browser.notify_user") as mock_notify:
        result = browser.tianyancha_search("测试公司")

        mock_notify.assert_called_once()
        assert result.get("_error") == "blocked_by_antibot"
        assert result.get("company_name") == "测试公司"


def test_dianping_search_notifies_on_captcha():
    """当大众点评触发验证码时，应调用 notify_user 通知用户。"""
    browser = OpenCLIBrowser(workspace="default")
    browser.goto = MagicMock()
    browser._get_current_url = MagicMock(return_value="https://verify.meituan.com/captcha")
    browser.eval = MagicMock(return_value={})

    with patch("src.collectors.opencli_browser.notify_user") as mock_notify:
        result = browser.dianping_search("测试品牌", city_id=1)

        mock_notify.assert_called_once()
        assert result.get("error") == "captcha_required"
