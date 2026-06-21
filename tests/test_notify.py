"""
Tests for src.utils.notify
"""
from unittest.mock import MagicMock

from src.utils.notify import notify_user


def test_notify_user_sends_notification_and_waits():
    """notify_user should send a desktop notification and wait for user input."""
    mock_subprocess = MagicMock()
    mock_input = MagicMock()

    notify_user(
        title="Test Title",
        message="Test message",
        wait=True,
        _input_func=mock_input,
        _subprocess_func=mock_subprocess,
    )

    # Should call subprocess to send notification
    mock_subprocess.assert_called_once()
    args = mock_subprocess.call_args[0][0]
    assert args[0] == "osascript"
    assert "Test Title" in args[2]
    assert "Test message" in args[2]

    # Should wait for user input
    mock_input.assert_called_once()


def test_notify_user_can_skip_waiting():
    """notify_user should send notification without blocking when wait=False."""
    mock_subprocess = MagicMock()
    mock_input = MagicMock()

    notify_user(
        title="Test Title",
        message="Test message",
        wait=False,
        _input_func=mock_input,
        _subprocess_func=mock_subprocess,
    )

    mock_subprocess.assert_called_once()
    mock_input.assert_not_called()
