import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from app import app


client = TestClient(app)


def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_generate_without_llm_uses_planner():
    response = client.post("/api/generate-config", json={"prompt": "生成一个标准件螺丝", "use_gemini": False})
    assert response.status_code == 200
    data = response.json()
    assert data["spec"]["decomposition"]["scope"] == "standard_part"
    assert data["spec"]["parts"][0]["kind"] == "screw"


def test_build_returns_python_source_url():
    generated = client.post(
        "/api/generate-config",
        json={"prompt": "\u751f\u6210\u4e00\u4e2a\u6807\u51c6\u4ef6\u87ba\u4e1d", "use_gemini": False},
    )
    assert generated.status_code == 200
    response = client.post("/api/build", json={"spec": generated.json()["spec"]})
    assert response.status_code == 200
    data = response.json()
    assert data["source_url"].endswith(".py")
