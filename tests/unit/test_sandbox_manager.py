"""Sandbox Manager 单元测试(mock Docker SDK)。"""
from unittest.mock import MagicMock, patch

import docker.errors

from backend.services.sandbox_manager import DockerExecutor, ExecutionRequest


@patch("backend.services.sandbox_manager.docker")
def test_execute_success(mock_docker: MagicMock) -> None:
    """执行成功时返回 success=True 并清理容器。"""
    # 保留真实的 errors 模块, 否则 except docker.errors.* 会崩溃
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.wait.return_value = {"StatusCode": 0}
    container.logs.return_value = b"result\n"
    container.get_archive.side_effect = docker.errors.NotFound("no output dir")
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="print('hello')"))

    assert result.success is True
    assert result.exit_code == 0
    assert result.output_files == {}
    container.start.assert_called_once()
    container.wait.assert_called_once_with(timeout=600)
    container.remove.assert_called_once()


@patch("backend.services.sandbox_manager.docker")
def test_execute_failure(mock_docker: MagicMock) -> None:
    """执行失败时返回 success=False。"""
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.wait.return_value = {"StatusCode": 1}
    container.logs.return_value = b"SyntaxError\n"
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="invalid python"))

    assert result.success is False
    assert "SyntaxError" in result.stdout


@patch("backend.services.sandbox_manager.docker")
def test_execute_timeout(mock_docker: MagicMock) -> None:
    """超时时容器被 kill, 返回 exit_code=137。"""
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.wait.side_effect = Exception("read timeout")
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="import time; time.sleep(999)", timeout_seconds=1))

    assert result.success is False
    assert result.exit_code == 137
    assert "timed out" in result.stderr
    container.kill.assert_called_once()
