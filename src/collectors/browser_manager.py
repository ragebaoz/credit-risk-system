"""
浏览器管理器 — 只检测、不启动、不杀进程。
依赖用户已打开的 Chrome + OpenCLI Extension。
"""
import time
from typing import Optional, Dict, Any

from src.utils.opencli_path import run_opencli


def check_opencli_extension() -> bool:
    """检查 OpenCLI daemon + extension 是否已连接"""
    try:
        stdout, _, rc = run_opencli("daemon", "status", timeout=2)
        if rc != 0:
            return False
        return "connected" in stdout.lower() and "disconnected" not in stdout.lower()
    except Exception:
        return False


def get_opencli_workspace_status(workspace: str = "default") -> Dict[str, Any]:
    """获取指定 browser workspace 的状态"""
    try:
        stdout, stderr, rc = run_opencli(
            "browser", "--workspace", workspace, "state", timeout=2
        )
        return {
            "ok": rc == 0 and "error" not in stdout.lower(),
            "stdout": stdout,
            "stderr": stderr,
            "rc": rc,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ensure_opencli_browser(workspace: str = "default") -> Dict[str, Any]:
    """
    确保 OpenCLI Browser 可用。
    只检测，不启动新 Chrome。如果用户已有 Chrome + Extension，直接复用。
    """
    # 1. 检查 daemon + extension
    if not check_opencli_extension():
        return {
            "ok": False,
            "error": (
                "OpenCLI extension 未连接。\n"
                "请确保你的 Chrome 已打开，且 OpenCLI 扩展已启用。\n"
                "如果扩展已安装但未连接，尝试点击扩展图标刷新，或运行：\n"
                "  opencli daemon restart"
            ),
        }

    # 2. 检查 workspace 是否可访问
    status = get_opencli_workspace_status(workspace)
    if status["ok"]:
        return {"ok": True, "workspace": workspace, "mode": "opencli_extension"}

    # 3. 尝试绑定到当前标签页（bound workspace）
    try:
        stdout, stderr, rc = run_opencli(
            "browser", "bind", "--workspace", f"bound:{workspace}", timeout=2
        )
        if rc == 0 or "bound" in stdout.lower():
            return {"ok": True, "workspace": f"bound:{workspace}", "mode": "bound_tab"}
    except Exception:
        pass

    return {
        "ok": False,
        "error": (
            f"OpenCLI browser workspace '{workspace}' 不可用。\n"
            f"错误信息: {status.get('stderr', status.get('error', 'unknown'))}\n"
            "请确保 Chrome 中已有页面打开，然后重试。"
        ),
    }
