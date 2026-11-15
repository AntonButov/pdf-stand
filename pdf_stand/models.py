from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ParseError:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class TableResult:
    page: int
    rows: list[list[str | None]]

    def to_dict(self) -> dict[str, Any]:
        return {"page": self.page, "rows": self.rows}


@dataclass
class ParseResult:
    ok: bool
    pages: int = 0
    tables: list[TableResult] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    engine: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "pages": self.pages,
            "tables": [t.to_dict() for t in self.tables],
            "errors": [e.to_dict() for e in self.errors],
            "engine": self.engine,
        }

    def stable_tables(self) -> list[dict[str, Any]]:
        """Normalized tables for golden comparison."""
        return [
            {
                "page": t.page,
                "rows": [[("" if c is None else str(c).strip()) for c in row] for row in t.rows],
            }
            for t in self.tables
        ]
