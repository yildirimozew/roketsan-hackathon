import json
from pathlib import Path

from app.core.config import Settings
from app.services.detection import PrecomputedDetector, build_detector


def test_precomputed_detector_filters_by_confidence_and_numbers_ids(tmp_path: Path) -> None:
    f = tmp_path / "detections.json"
    f.write_text(
        json.dumps(
            {
                "img_000860": [
                    {"label": "car", "confidence": 0.2, "bbox": [0, 0, 10, 10]},
                    {"label": "truck", "confidence": 0.87, "bbox": [727, 284, 58, 34]},
                ]
            }
        )
    )

    dets = PrecomputedDetector(f, conf_min=0.35).detect("img_000860", Path("unused.jpg"))

    assert [d.id for d in dets] == ["DET-1"]
    assert dets[0].label == "truck"
    assert dets[0].center_px == (756.0, 301.0)


def test_unknown_image_yields_no_detections(tmp_path: Path) -> None:
    det = PrecomputedDetector(tmp_path / "missing.json", conf_min=0.35)

    assert det.detect("img_x", Path("unused.jpg")) == []
    assert det.is_ready()[0] is False


def test_ultralytics_without_weights_falls_back_to_precomputed(settings: Settings) -> None:
    settings.detector_kind = "ultralytics"
    settings.detector_weights = settings.cache_dir / "missing.pt"

    assert build_detector(settings).name == "precomputed"
