"""验证所有 ORM 模型可正常导入。"""

from backend.models import (
    Base,
    DocSummary,
    Document,
    EditorDraft,
    Equation,
    Figure,
    Paragraph,
    PromptOverride,
    QuotaRecord,
    Reference,
    RefreshToken,
    RunSnapshot,
    SectionHeading,
    Table,
    Thread,
    User,
    Workspace,
)


def test_all_models_importable() -> None:
    """所有 ORM 模型均可导入。"""
    models = [
        User,
        Workspace,
        Thread,
        Document,
        RunSnapshot,
        EditorDraft,
        QuotaRecord,
        PromptOverride,
        DocSummary,
        Paragraph,
        Table,
        Figure,
        Equation,
        SectionHeading,
        Reference,
        RefreshToken,
    ]
    assert len(models) == 16


def test_base_has_metadata() -> None:
    """Base.metadata 应包含所有表名。"""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "workspaces",
        "threads",
        "documents",
        "run_snapshots",
        "editor_drafts",
        "quota_records",
        "prompt_overrides",
        "doc_summaries",
        "paragraphs",
        "tables",
        "figures",
        "equations",
        "section_headings",
        "references",
        "refresh_tokens",
    }
    assert expected.issubset(table_names)
