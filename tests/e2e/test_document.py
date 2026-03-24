"""E2E: Document 端点验证。"""

import uuid

import httpx
import pytest

from tests.e2e.seed import SeedData

pytestmark = pytest.mark.e2e


async def _initiate_upload(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: str,
    title: str = "Test Doc",
) -> str:
    """Helper: 发起上传并返回 document_id。"""
    resp = await client.post(
        "/api/v1/documents/upload-url",
        headers=headers,
        json={
            "workspace_id": workspace_id,
            "title": title,
            "file_path": "application/pdf",
        },
    )
    assert resp.status_code == 201
    return resp.json()["document_id"]


async def test_initiate_upload(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """POST /api/documents/upload-url — 发起上传。"""
    response = await test_client.post(
        "/api/v1/documents/upload-url",
        headers=auth_headers,
        json={
            "workspace_id": str(seed_data.workspace_id),
            "title": "E2E Test Paper",
            "file_path": "application/pdf",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "document_id" in data
    assert "upload_url" in data
    assert "storage_key" in data


@pytest.mark.skip(reason="confirm_upload 需要真实文件存在于 storage，mock storage 无法满足")
async def test_confirm_upload_then_get(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """确认上传 → 获取文档详情完整流程。"""
    doc_id = await _initiate_upload(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "E2E Confirm Test",
    )

    # 确认上传（document_id 是 query parameter）
    confirm_resp = await test_client.post(
        f"/api/v1/documents/confirm?document_id={doc_id}",
        headers=auth_headers,
    )
    assert confirm_resp.status_code == 200

    # 获取详情
    get_resp = await test_client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["title"] == "E2E Confirm Test"


async def test_list_documents(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/documents?workspace_id=... — 列出文档。"""
    response = await test_client.get(
        "/api/v1/documents",
        headers=auth_headers,
        params={"workspace_id": str(seed_data.workspace_id)},
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_get_document_not_found(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """GET /api/documents/{id} — 不存在的文档返回 404。"""
    response = await test_client.get(
        f"/api/v1/documents/{uuid.uuid4()}",
        headers=auth_headers,
    )

    assert response.status_code == 404


async def test_get_document_status(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/documents/{id}/status — 获取文档解析状态。"""
    doc_id = await _initiate_upload(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Status Check Doc",
    )

    response = await test_client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "parse_status" in data


async def test_get_document_artifacts(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """GET /api/documents/{id}/artifacts — 获取解析产物。"""
    doc_id = await _initiate_upload(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "Artifacts Doc",
    )

    response = await test_client.get(
        f"/api/v1/documents/{doc_id}/artifacts",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "paragraphs" in data


async def test_delete_document(
    test_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    seed_data: SeedData,
) -> None:
    """DELETE /api/documents/{id} — 删除后 GET 返回 404。"""
    doc_id = await _initiate_upload(
        test_client,
        auth_headers,
        str(seed_data.workspace_id),
        "To Delete Doc",
    )

    del_resp = await test_client.delete(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
    )
    assert del_resp.status_code == 204

    get_resp = await test_client.get(
        f"/api/v1/documents/{doc_id}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 404
