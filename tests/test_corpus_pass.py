from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdf_stand.pipeline import parse_file

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.json"
PASS = ROOT / "tests" / "corpus" / "pass"
EXPECTED = ROOT / "tests" / "corpus" / "expected"


def _entries() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["pass"]


@pytest.mark.parametrize("entry", _entries(), ids=lambda e: e["id"])
def test_corpus_pass(entry: dict):
    path = PASS / entry["file"]
    assert path.exists()
    result = parse_file(path)
    assert result.ok, result.to_dict()
    assert len(result.tables) >= int(entry.get("min_tables", 1))

    golden = json.loads((EXPECTED / f"{path.stem}.json").read_text(encoding="utf-8"))
    assert result.stable_tables() == golden["tables"]


def test_manifest_has_20():
    assert len(_entries()) == 20
