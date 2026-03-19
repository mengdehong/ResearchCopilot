"""Sandbox Manager 单元测试（mock Docker SDK）。"""
from unittest.mock import MagicMock, patch

import docker.errors

from backend.services.sandbox_manager import DockerExecutor, ExecutionRequest


@patch("backend.services.sandbox_manager.docker")
def test_execute_success(mock_docker: MagicMock) -> None:
    """执行成功时返回 success=True 并清理容器。"""
    # 保留真实的 errors 模块，否则 except docker.errors.* 会崩溃
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.exec_run.return_value = (0, (b"result\n", b""))
    container.get_archive.side_effect = docker.errors.NotFound("no output dir")
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="print('hello')"))

    assert result.success is True
    assert result.exit_code == 0
    assert result.output_files == {}
    container.start.assert_called_once()
    container.remove.assert_called_once()


@patch("backend.services.sandbox_manager.docker")
def test_execute_failure(mock_docker: MagicMock) -> None:
    """执行失败时返回 success=False 和 stderr。"""
    mock_docker.errors = docker.errors

    container = MagicMock()
    container.exec_run.return_value = (1, (b"", b"SyntaxError\n"))
    mock_docker.from_env.return_value.containers.create.return_value = container

    executor = DockerExecutor()
    result = executor.execute(ExecutionRequest(code="invalid python"))

    assert result.success is False
    assert "SyntaxError" in result.stderr
