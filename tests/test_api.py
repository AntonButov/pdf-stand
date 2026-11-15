from fastapi.testclient import TestClient

from pdf_stand.api import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_parse_rejects_non_pdf():
    r = client.post("/parse", files={"file": ("note.txt", b"hello", "text/plain")})
    assert r.status_code == 400
