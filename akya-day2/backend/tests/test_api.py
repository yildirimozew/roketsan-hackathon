import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.watch.runner import WatchRunner
from app.core.config import Settings
from app.data.repository import Repository
from app.domain.watch import event_payload
from tests.agent.fake_llm import FakeLLM, rubric_responder
from tests.conftest import _client


def test_health_reports_missing_dependencies_without_failing(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["llm"]["available"] is False
    assert body["detector"]["available"] is False
    assert body["data"]["available"] is False


def test_data_routes_return_503_when_data_missing(client: TestClient) -> None:
    res = client.get("/api/scene")
    assert res.status_code == 503
    assert res.json()["error"] == "data_unavailable"


def test_unknown_analysis_returns_typed_404(golden_client: TestClient) -> None:
    res = golden_client.get("/api/analyses/nope")
    assert res.status_code == 404
    assert res.json() == {"error": "not_found", "detail": "analysis nope not found"}


def test_scene_and_images(golden_client: TestClient) -> None:
    scene = golden_client.get("/api/scene").json()
    assert scene["base"]["name"] == "Merkez Us"
    assert len(scene["zones"]) == 8
    (image,) = golden_client.get("/api/images").json()
    assert image["image_id"] == "img_000860" and image["zone"] == "Dogu Yolu"


def test_create_then_get_analysis_reuses_latest(golden_client: TestClient) -> None:
    first = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    again = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    fresh = golden_client.post(
        "/api/analyses", json={"image_id": "img_000860", "force_refresh": True}
    ).json()
    assert first == again and fresh != first

    analysis = golden_client.get(f"/api/analyses/{first['analysis_id']}").json()
    assert analysis["status"] == "done"
    assert [s["index"] for s in analysis["steps"]] == list(range(1, 9))
    assert analysis["brief"]["level"] == "HIGH"


def test_unknown_image_is_404(golden_client: TestClient) -> None:
    res = golden_client.post("/api/analyses", json={"image_id": "img_999999"})
    assert res.status_code == 404


def test_field_map_tracks_reports_and_motion(golden_client: TestClient) -> None:
    tracks = golden_client.get("/api/tracks").json()
    t0122 = next(t for t in tracks if t["track_id"] == "T0122")
    assert t0122["image_id"] == "img_000860" and len(t0122["points"]) > 1

    reports = golden_client.get("/api/reports").json()
    times = [r["time_min"] for r in reports]
    assert times == sorted(times)
    heavy = next(r for r in reports if r["time"] == "12:35")
    assert heavy["location"] == {"lat": 39.9253, "lon": 32.8718}

    motion = golden_client.get("/api/tracks/T0122/motion", params={"at": "14:10"}).json()
    assert motion["track_id"] == "T0122" and motion["dist_now_m"] < 2000
    assert golden_client.get("/api/tracks/nope/motion", params={"at": "14:10"}).status_code == 404
    assert golden_client.get("/api/tracks/T0122/motion", params={"at": "x"}).status_code == 422


def test_watch_run_streams_events(golden_client: TestClient) -> None:
    run_id = golden_client.post(
        "/api/watch/runs", json={"start": "14:00", "end": "14:05", "watchers": 4}
    ).json()["run_id"]
    with golden_client.stream("GET", f"/api/watch/runs/{run_id}/events") as res:
        assert res.headers["content-type"].startswith("text/event-stream")
        data = [line[6:] for line in res.iter_lines() if line.startswith("data: ")]
    types = [json.loads(d)["type"] for d in data]
    assert types[0] == "tick_started" and types[-1] == "tick_completed"
    assert types.count("tick_completed") == 2

    status = golden_client.get(f"/api/watch/runs/{run_id}").json()
    assert status["status"] == "done" and status["events"] == len(types)
    assert status["watchers"] == 4
    log = golden_client.get(f"/api/watch/runs/{run_id}/log").json()
    assert [e["type"] for e in log] == types
    assert golden_client.get("/api/watch/runs/nope").status_code == 404


def test_watch_recordings_are_listed_and_served(
    golden_settings: Settings, golden_repo: Repository, tmp_path: Path
) -> None:
    events: list[dict[str, object]] = []
    runner = WatchRunner(
        golden_repo,
        golden_settings,
        FakeLLM(responder=rubric_responder),
        lambda e: events.append(event_payload(e)),
    )
    asyncio.run(runner.run(14 * 60, 14 * 60 + 5))
    (tmp_path / "demo.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in events), encoding="utf-8"
    )
    (tmp_path / "stale.jsonl").write_text('{"type": "authority_alert", "tick": "10:00"}')
    settings = golden_settings.model_copy(update={"recordings_dir": tmp_path})
    for client in _client(settings, golden_repo, tmp_path / "admin_overrides.json"):
        (rec,) = client.get("/api/watch/recordings").json()
        assert rec["recording_id"] == "demo" and rec["ticks"] == ["14:00", "14:05"]
        assert rec["llm_turns"] > 0 and rec["events"] == len(events)
        served = client.get("/api/watch/recordings/demo").json()
        assert [e["type"] for e in served] == [e["type"] for e in events]
        assert client.get("/api/watch/recordings/nope").status_code == 404
