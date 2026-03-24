"""渲染后端工厂。"""

from backend.agent.skills.ppt_generation.renderer.typst_renderer import TypstRenderer


def create_renderer(backend: str) -> TypstRenderer:
    """根据 backend 参数创建渲染后端实例。

    Args:
        backend: 渲染后端名称，目前仅支持 "typst"。

    Raises:
        NotImplementedError: 不支持的后端。
    """
    if backend == "typst":
        return TypstRenderer()
    raise NotImplementedError(f"Renderer backend not implemented: {backend}")
