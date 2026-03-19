"""Research Copilot — FastAPI 启动入口。"""

from fastapi import FastAPI

app = FastAPI(
    title="Research Copilot",
    description="意图驱动型自动案头研究工作站",
    version="0.1.0",
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """健康检查端点。"""
    return {"status": "ok"}
