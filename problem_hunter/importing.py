"""Configurable, bounded CSV input into the shared Source model."""
import csv
from pathlib import Path

from .discovery import deduplicate
from .models import Source


def import_csv(path, mapping=None):
    path = Path(path)
    if path.stat().st_size > 20_000_000:
        raise ValueError("CSV exceeds 20 MB limit")
    aliases = {"url": ["url", "link"], "title": ["title", "headline"],
        "content": ["content", "text", "description", "body"], "author": ["author", "user", "username"],
        "published_at": ["published_at", "date", "created_at"], "source": ["source", "platform"]}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        fields = {column.strip().lower(): column for column in reader.fieldnames}
        columns = {key: next((fields[a] for a in names if a in fields), None) for key, names in aliases.items()}
        for key, value in (mapping or {}).items():
            if key not in aliases:
                raise ValueError(f"Unknown target field: {key}")
            if value not in reader.fieldnames:
                raise ValueError(f"CSV column not found: {value}")
            columns[key] = value
        if not columns["content"]:
            raise ValueError("CSV requires a content/text column; use --map content=column")
        sources = []
        for index, row in enumerate(reader, 2):
            if index > 100_001:
                raise ValueError("CSV exceeds 100,000 rows")
            values = {key: (row.get(column) or "").strip() if column else "" for key, column in columns.items()}
            if not values["content"]:
                continue
            sources.append(Source(url=values["url"], title=values["title"] or "Imported report",
                content=values["content"], author=values["author"] or None, published_at=values["published_at"] or None,
                source=values["source"] or "CSV import", content_kind="imported",
                metadata={"import_file": path.name, "import_row": index, "traceability": "original URL" if values["url"] else "CSV row only"}))
        return deduplicate(sources)
