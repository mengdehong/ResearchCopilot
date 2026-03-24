"""自动页面生成。注入标题页、目录页、参考文献页。"""

from __future__ import annotations

from backend.agent.skills.ppt_generation.schema import (
    OutlineContent,
    PresentationSchema,
    ReferencesContent,
    SlideSchema,
    TitleContent,
)


def inject_auto_slides(schema: PresentationSchema) -> PresentationSchema:
    """纯函数：在 Schema 副本中注入自动生成的页面。不修改原始输入。

    注入规则：
    1. 标题页：始终插入为第一页
    2. 目录页：每个 section 首页前插入，标记当前 section
    3. 参考文献页：仅当存在引用时追加到末尾
    """
    content_slides = [s.model_copy(deep=True) for s in schema.slides]

    # 收集 sections（按出现顺序去重）
    sections: list[str] = []
    for slide in content_slides:
        if slide.section and slide.section not in sections:
            sections.append(slide.section)

    # 插入目录页（倒序插入避免索引偏移）
    for section_idx, section_name in reversed(list(enumerate(sections))):
        # 找到该 section 第一个 slide 的位置
        insert_pos = next(i for i, s in enumerate(content_slides) if s.section == section_name)
        outline_slide = SlideSchema(
            id=f"auto_outline_{section_idx}",
            layout="outline",
            content=OutlineContent(active_index=section_idx),
        )
        content_slides.insert(insert_pos, outline_slide)

    # 标题页
    title_slide = SlideSchema(
        id="auto_title",
        layout="title",
        content=TitleContent(),
    )
    content_slides.insert(0, title_slide)

    # 参考文献页（仅当有引用时）
    all_citation_keys: set[str] = set()
    for slide in schema.slides:
        all_citation_keys.update(slide.citations)
    ref_keys_from_meta = {r.key for r in schema.meta.references}
    has_references = bool(all_citation_keys | ref_keys_from_meta)

    if has_references:
        ref_slide = SlideSchema(
            id="auto_references",
            layout="references",
            content=ReferencesContent(),
        )
        content_slides.append(ref_slide)

    return PresentationSchema(
        meta=schema.meta.model_copy(deep=True),
        slides=content_slides,
    )
