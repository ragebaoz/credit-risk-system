"""
用户通知工具。

在浏览器自动化遇到验证码或反爬拦截时，通过桌面通知提醒用户手动处理，
并可选择暂停流程等待用户确认。
"""

import subprocess
import sys


def notify_user(
    title: str,
    message: str,
    wait: bool = True,
    _input_func=input,
    _subprocess_func=subprocess.run,
) -> None:
    """
    发送桌面通知并可选地等待用户确认。

    :param title: 通知标题
    :param message: 通知正文
    :param wait: 是否暂停等待用户按回车继续
    :param _input_func: 用于测试注入的输入函数
    :param _subprocess_func: 用于测试注入的 subprocess 函数
    """
    # 终端醒目提示
    print(f"\n{'='*60}")
    print(f"🔔 {title}")
    print(f"{'='*60}")
    print(message)
    print(f"{'='*60}\n")

    # 桌面通知
    if sys.platform == "darwin":
        _subprocess_func(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}" sound name "default"',
            ],
            check=False,
        )
    elif sys.platform == "win32":
        try:
            from win10toast import ToastNotifier

            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=10)
        except Exception:
            pass
    else:
        # Linux: try notify-send
        _subprocess_func(
            ["notify-send", title, message],
            check=False,
        )

    if wait:
        _input_func("请处理验证码/反爬后按回车继续...")
