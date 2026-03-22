"""容器化沙箱管理。CodeExecutor Protocol + DockerExecutor 实现。"""

import contextlib
import io
import tarfile
import time
import typing
from dataclasses import dataclass, field
from typing import Protocol

import docker
import requests
from docker.models.containers import Container

from backend.core.exceptions import SandboxError
from backend.core.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ExecutionRequest:
    """沙箱执行请求。"""

    code: str
    timeout_seconds: int = 600
    input_files: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    """沙箱执行结果。"""

    success: bool
    exit_code: int
    stdout: str
    stderr: str
    output_files: dict[str, bytes] = field(default_factory=dict)
    duration_seconds: float = 0.0


class CodeExecutor(Protocol):
    """代码执行器抽象接口。"""

    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...


class DockerExecutor:
    """基于 Docker 的代码执行器。"""

    LABELS: typing.ClassVar[dict[str, str]] = {"app": "research-copilot", "role": "sandbox"}

    def __init__(
        self,
        *,
        image: str = "research-copilot-sandbox:latest",
        memory_limit: str = "4g",
        cpu_count: int = 2,
    ) -> None:
        self._image = image
        self._memory_limit = memory_limit
        self._nano_cpus = cpu_count * 1_000_000_000
        self._client = docker.from_env()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """创建容器→注入代码→执行→提取结果→强制销毁。"""
        container: Container | None = None
        start_time = time.monotonic()
        logger.info(
            "sandbox_execute_start",
            image=self._image,
            timeout=request.timeout_seconds,
            input_files_count=len(request.input_files),
        )

        try:
            container = self._create_container()
            logger.info(
                "sandbox_container_created",
                container_id=container.short_id,
            )
            self._inject_code(container, request.code, request.input_files)
            exit_code, stdout, stderr = self._run(container, request.timeout_seconds)
            output_files = self._extract_outputs(container) if exit_code == 0 else {}
            duration = time.monotonic() - start_time
            is_timeout = exit_code == 137 and "timed out" in stderr

            logger.info(
                "sandbox_execute_complete",
                container_id=container.short_id,
                exit_code=exit_code,
                duration_ms=round(duration * 1000),
                timeout=is_timeout,
                output_files_count=len(output_files),
            )

            return ExecutionResult(
                success=(exit_code == 0),
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                output_files=output_files,
                duration_seconds=duration,
            )
        except docker.errors.DockerException as exc:
            logger.error(
                "sandbox_execution_failed",
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise SandboxError(
                f"Sandbox execution failed: {type(exc).__name__}"
            ) from exc
        finally:
            if container:
                self._destroy_container(container)

    def _create_container(self) -> Container:
        return self._client.containers.create(
            image=self._image,
            command=["python", "/workspace/script.py"],
            network_disabled=True,
            mem_limit=self._memory_limit,
            nano_cpus=self._nano_cpus,
            user="sandbox",
            labels=self.LABELS,
            stdin_open=False,
            tty=False,
        )

    def _inject_code(
        self,
        container: Container,
        code: str,
        input_files: dict[str, bytes],
    ) -> None:
        tar_buffer = self._build_tar(
            {
                "script.py": code.encode(),
                **{f"data/{name}": content for name, content in input_files.items()},
            }
        )
        container.put_archive("/workspace/", tar_buffer)

    def _run(self, container: Container, timeout: int) -> tuple[int, str, str]:
        container.start()
        try:
            result = container.wait(timeout=timeout)
            exit_code: int = result.get("StatusCode", 1)
        except requests.exceptions.ConnectionError:
            # Docker SDK raises ConnectionError when wait() times out
            with contextlib.suppress(docker.errors.DockerException):
                container.kill()
            return 137, "", f"Execution timed out after {timeout}s"

        stdout_bytes = container.logs(stdout=True, stderr=False, stream=False)
        stderr_bytes = container.logs(stdout=False, stderr=True, stream=False)
        stdout = (stdout_bytes or b"").decode(errors="replace")
        stderr = (stderr_bytes or b"").decode(errors="replace")
        return exit_code, stdout, stderr

    def _extract_outputs(self, container: Container) -> dict[str, bytes]:
        try:
            bits, _ = container.get_archive("/output/")
            tar_stream = io.BytesIO(b"".join(bits))
            result: dict[str, bytes] = {}
            with tarfile.open(fileobj=tar_stream) as tar:
                for member in tar.getmembers():
                    if member.isfile():
                        f = tar.extractfile(member)
                        if f:
                            name = (
                                member.name.split("/", 1)[-1] if "/" in member.name else member.name
                            )
                            result[name] = f.read()
            return result
        except docker.errors.NotFound:
            return {}

    def _destroy_container(self, container: Container) -> None:
        try:
            container.stop(timeout=5)
            container.remove(force=True)
        except docker.errors.DockerException:
            logger.warning("sandbox_cleanup_failed", container_id=container.short_id)

    @staticmethod
    def _build_tar(files: dict[str, bytes]) -> bytes:
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            for name, content in files.items():
                info = tarfile.TarInfo(name=name)
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        tar_buffer.seek(0)
        return tar_buffer.read()
