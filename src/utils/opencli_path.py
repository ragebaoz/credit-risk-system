"""
OpenCLI 路径解析工具。

credit-risk-system 依赖 OpenCLI CLI 进行浏览器自动化。
本模块把 OpenCLI 入口 JS 文件的绝对路径集中管理，支持通过环境变量覆盖。
"""

import os
import subprocess
from typing import Tuple


DEFAULT_OPENCLI_PATH = "/Users/yuxuanyu/workspace/OpenCLI/dist/src/main.js"


def get_opencli_path() -> str:
    """返回 OpenCLI 入口 JS 文件的绝对路径。"""
    path = os.environ.get("OPENCLI_PATH", DEFAULT_OPENCLI_PATH)
    return os.path.abspath(os.path.expanduser(path))


def run_opencli(*args: str, timeout: int = 15) -> Tuple[str, str, int]:
    """执行 opencli 子命令，返回 (stdout, stderr, returncode)。"""
    cmd = ["node", get_opencli_path(), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return result.stdout, result.stderr, result.returncode
