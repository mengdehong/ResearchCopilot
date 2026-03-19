"""Sandbox Manager 单元测试(mock Docker SDK)。"""
from unittest.mock import MagicMock, patch

import docker.errors
import requests.exceptions

from backend.services.sandbox_manager import DockerExecutor, ExecutionRequest


@patch("backend.services.sandbox_manager.docker")
def test_execute_success(mock_docker: MagicMock) -> None:
    """执行成功时返回 success=True, stdout/stderr 分离, 容器被清理。"""
    # 保留真实的 errors 模块, 否则 except docker.errors.* 会崩溃
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.side_effect = lambda stdout, stderr, stream: (
        b"result\n" if stdout else b""
    )
    container.get_archive.side_effect = docker.errors.NotFound("no output dir")
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="print('hello')"))

    assert result.success is True
    assert result.exit_code == 0
    assert "result" in result.stdout
    assert result.stderr == ""
    assert result.output_files == {}
    container.start.assert_called_once()
    container.wait.assert_called_once_with(timeout=600)
    container.remove.assert_called_once()


@patch("backend.services.sandbox_manager.docker")
def test_execute_failure_with_stderr(mock_docker: MagicMock) -> None:
    """执行失败时 stderr 包含错误信息, stdout 为空。"""
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.wait.return_value = {"StatusCode": 1}
    container.logs.side_effect = lambda stdout, stderr, stream: (
        b"" if stdout else b"SyntaxError: invalid syntax\n"
    )
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="invalid python"))

    assert result.success is False
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "SyntaxError" in result.stderr


@patch("backend.services.sandbox_manager.docker")
def test_execute_timeout(mock_docker: MagicMock) -> None:
    """仅 ConnectionError 被视为超时, 容器被 kill, 返回 exit_code=137。"""
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.wait.side_effect = requests.exceptions.ConnectionError("read timeout")
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(
        ExecutionRequest(code="import time; time.sleep(999)", timeout_seconds=1),
    )

    assert result.success is False
    assert result.exit_code == 137
    assert "timed out" in result.stderr
    container.kill.assert_called_once()
