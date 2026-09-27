"""Z1 - never turn "no detector" into a silent "0 vehicles, LOW".

Today `PrecomputedDetector.detect` returns [] when its JSON file is missing or has no entry for
the frame, and the pipeline only warns on `DetectorError`, so every frame reads "0 vehicles" and
`frame_level([])` is LOW with no warning. If the fallback raises too, `run_analysis` re-raises.

Integration:
- `services/detection/precomputed.py`: the `StrictPrecomputedDetector.detect` checks go into
  `PrecomputedDetector.detect` ("frame present with no boxes" stays a valid empty result).
- `agent/pipeline.py` step 2: replace the try/except with `detect_with_fallback`; when
  `available` is False the step is `warning`, Z2 adds track-only vehicles and Z8 flags the frame.
- Produce the file once with the team's best weights (`backend/scripts/precompute_detections.py`),
  check it with `validate_detections_file`, and commit it under `data/` (data/ is committed;
  weights are not) with `SENTINEL_DETECTIONS_FILE` pointing at it.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.core.errors import DetectorError
from app.domain.detection import Detection
from app.services.detection import Detector, PrecomputedDetector


class StrictPrecomputedDetector(PrecomputedDetector):
    """`PrecomputedDetector` that raises instead of returning [] for a frame it does not know."""

    def detect(self, image_id: str, image_path: Path | None) -> list[Detection]:
        """Stored detections; `DetectorError` when the file or the frame's entry is missing."""
        if not self._data:
            raise DetectorError(f"no precomputed detections at {self._file.name}")
        if image_id not in self._data:
            raise DetectorError(f"{image_id} missing from {self._file.name}")
        return super().detect(image_id, image_path)


@dataclass(frozen=True)
class DetectOutcome:
    """Result of step 2. `available=False` means no detector produced anything for this frame."""

    detections: list[Detection]
    detector: str
    available: bool
    warnings: list[str] = field(default_factory=list)


def detect_with_fallback(
    primary: Detector, fallback: Detector | None, image_id: str, image_path: Path | None
) -> DetectOutcome:
    """Try the primary detector, then the fallback. Never raises."""
    warnings: list[str] = []
    for det in (primary, fallback):
        if det is None:
            continue
        try:
            found = det.detect(image_id, image_path)
        except DetectorError as exc:
            warnings.append(f"{det.name} failed ({exc.detail})")
            continue
        if det is not primary:
            warnings.append(f"used fallback detector {det.name}")
        return DetectOutcome(found, det.name, True, warnings)
    warnings.append("no detector available: vehicles come from tracks only")
    return DetectOutcome([], "none", False, warnings)


def validate_detections_file(path: Path, image_ids: list[str], classes: list[str]) -> list[str]:
    """Problems that would make the demo silently wrong (empty list = file is fine)."""
    if not path.is_file():
        return [f"{path} does not exist"]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.name} is not valid JSON: {exc}"]
    if not isinstance(raw, dict):
        return [f"{path.name} must map image_id -> list of boxes"]
    problems = [f"missing frame {i}" for i in image_ids if i not in raw]
    for image_id, boxes in raw.items():
        for n, b in enumerate(boxes if isinstance(boxes, list) else []):
            where = f"{image_id}[{n}]"
            if b.get("label") not in classes:
                problems.append(f"{where}: unknown label {b.get('label')!r}")
            bbox = b.get("bbox")
            if not (isinstance(bbox, list) and len(bbox) == 4 and bbox[2] > 0 and bbox[3] > 0):
                problems.append(f"{where}: bbox must be [x, y, w, h] with w, h > 0")
            if not 0 <= float(b.get("confidence", -1)) <= 1:
                problems.append(f"{where}: confidence must be in [0, 1]")
    return problems
