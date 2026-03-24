"""渲染后端工厂。"""

from backend.agent.skills.ppt_generation.renderer.beamer_renderer import BeamerRenderer
from backend.agent.skills.ppt_generation.renderer.typst_renderer import TypstRenderer


def create_renderer(backend: str) -> TypstRenderer | BeamerRenderer:
    """根据 backend 参数创建渲染后端实例。

    Args:
        backend: 渲染后端名称，支持 "typst" 和 "beamer"。

    Raises:
        NotImplementedError: 不支持的后端。
    """
    if backend == "typst":
        return TypstRenderer()
    if backend == "beamer":
        return BeamerRenderer()
    raise NotImplementedError(f"Renderer backend not implemented: {backend}")
