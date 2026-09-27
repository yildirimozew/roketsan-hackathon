"""Admin tuning API (spec §3.5)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.watch.prompts import PROMPT_FILES, file_text
from app.services.tuning import DEFAULT_TUNING


def _body(**ceiling: float) -> dict:  # type: ignore[type-arg]
    t = DEFAULT_TUNING.model_copy(
        update={"ceiling": DEFAULT_TUNING.ceiling.model_copy(update=ceiling)}
    )
    return t.model_dump(mode="json")


def test_get_returns_defaults(client: TestClient) -> None:
    view = client.get("/api/admin/tuning").json()
    assert view["overridden"] == [] and view["load_warning"] is None
    assert view["current"] == view["defaults"]
    assert "approach_high_km" in view["prompt_variables"]["watcher"]


def test_put_then_get_then_delete(client: TestClient) -> None:
    res = client.put("/api/admin/tuning", json=_body(at_base_m=1500.0))
    assert res.status_code == 200 and res.json()["overridden"] == ["ceiling.at_base_m"]
    assert client.get("/api/admin/tuning").json()["current"]["ceiling"]["at_base_m"] == 1500.0
    reset = client.delete("/api/admin/tuning").json()
    assert reset["overridden"] == []


def test_put_rejects_rule_breaks_with_paths(client: TestClient) -> None:
    res = client.put("/api/admin/tuning", json=_body(arrived_from_m=0.0))
    assert res.status_code == 422
    assert res.json() == {"error": "invalid_tuning", "detail": "ceiling.arrived_from_m: positive"}


def test_preview(client: TestClient) -> None:
    body = {
        "name": "supervisor",
        "text": file_text(PROMPT_FILES["supervisor"]),
        "tuning": DEFAULT_TUNING.model_dump(mode="json"),
    }
    res = client.post("/api/admin/prompts/preview", json=body).json()
    assert res["rendered"].startswith("# Role") and res["missing"] == []


def test_analysis_cache_respects_tuning(golden_client: TestClient) -> None:
    first = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    again = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    assert again["analysis_id"] == first["analysis_id"]
    golden_client.put("/api/admin/tuning", json=_body(at_base_m=1500.0))
    tuned = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    assert tuned["analysis_id"] != first["analysis_id"]


def test_golden_client_uses_an_isolated_tuning_store(
    golden_client: TestClient, tmp_path: Path
) -> None:
    from app.api.deps import get_tuning_store

    store = golden_client.app.dependency_overrides[get_tuning_store]()  # type: ignore[attr-defined]
    assert store.path.is_relative_to(tmp_path)
    view = golden_client.get("/api/admin/tuning").json()
    assert view["overridden"] == [] and view["load_warning"] is None
