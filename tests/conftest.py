"""共享测试 fixtures。"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    """创建 FastAPI 同步测试客户端。"""
    return TestClient(app)
