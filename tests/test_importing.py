import pytest
from problem_hunter.importing import import_csv


def test_mapping_and_duplicate_rows(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text('Link,Complaint,User\nhttps://example.com/a,"I spend hours, daily",alice\nhttps://example.com/a,same,alice\n', encoding="utf-8")
    sources = import_csv(path, {"url": "Link", "content": "Complaint", "author": "User"})
    assert len(sources) == 1
    assert sources[0].content == "I spend hours, daily"
    assert sources[0].author == "alice"


def test_missing_content_and_mapping(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("title\nhello\n")
    with pytest.raises(ValueError, match="content"):
        import_csv(path)
    with pytest.raises(ValueError, match="not found"):
        import_csv(path, {"content": "missing"})


def test_no_url_import_preserves_row_traceability(tmp_path):
    path = tmp_path / "rows.csv"
    path.write_text("text,author\nmanual daily,alice\nmanual daily,bob\n")
    sources = import_csv(path)
    assert len(sources) == 2
    assert sources[0].metadata["traceability"] == "CSV row only"
