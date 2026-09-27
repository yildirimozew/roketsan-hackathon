"""Application settings. The only place that reads environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
# Organizer's OpenAI-compatible gateway (docs/part2_docs/stage2/gorev_tanimi.txt).
GLM_GATEWAY_URL = "https://berriailitellm-databasev1826rc3-production-d691.up.railway.app/v1"
ReasoningEffort = Literal["low", "high", "max"]


class Settings(BaseSettings):
    """Runtime configuration, loaded from env vars with prefix `SENTINEL_` and `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_",
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # Paths
    data_dir: Path = REPO_DIR / "data"
    models_dir: Path = REPO_DIR / "models"
    cache_dir: Path = BACKEND_DIR / ".cache"
    # Recorded watch runs (JSONL event logs) served to the UI's demo mode, no LLM needed.
    recordings_dir: Path = BACKEND_DIR / "recordings"

    # API
    cors_origins: list[str] = ["http://localhost:5173"]
    log_level: str = "INFO"

    # LLM (OpenAI-compatible GLM gateway). Empty key => LLM disabled, fallbacks used.
    # The key is read from GLM_API_KEY (or SENTINEL_LLM_API_KEY).
    llm_base_url: str = GLM_GATEWAY_URL
    llm_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("GLM_API_KEY", "SENTINEL_LLM_API_KEY")
    )
    llm_model: str = "glm-5.3-flash"
    # GLM always reasons before answering, so calls take ~10-40 s.
    llm_timeout_s: float = 120.0
    llm_max_retries: int = 2
    llm_max_concurrency: int = 4  # gateway limit per team
    llm_cache: bool = True  # disk cache under cache_dir/llm, keyed by the full request
    brief_language: Literal["tr", "en"] = "tr"

    # Watch mode (docs/AGENT_FLOW.md, docs/AGENT_PROMPTS_AND_TOOLS.md)
    watcher_count: int = 4  # watchers share the 8 sectors and take turns checking them
    trackers_enabled: bool = False  # trackers are backlog (PLAN.md §10)
    watcher_model: str | None = None  # None => llm_model
    supervisor_model: str | None = None  # None => llm_model
    watcher_reasoning_effort: ReasoningEffort = "low"
    supervisor_reasoning_effort: ReasoningEffort = "high"
    watcher_max_tool_calls: int = 3
    watcher_spot_checks: int = 2  # random quiet vehicles each watcher also judges per check
    supervisor_max_tool_calls: int = 6
    tracker_slots: int = 3

    # Detector
    detector_kind: Literal["precomputed", "ultralytics"] = "precomputed"
    detector_weights: Path = REPO_DIR / "models" / "detector.pt"
    detections_file: Path = BACKEND_DIR / ".cache" / "detections.json"
    detect_conf_min: float = 0.35
    detect_classes: list[str] = ["car", "van", "truck", "bus"]
    detector_device: str = "auto"  # "auto" (CUDA if available), "cpu" or a GPU index
    # Inference size in px; None = the model's training size. 960 is ~2x faster than 1280
    # on a GTX 1650 with the same boxes on our frames.
    detector_imgsz: int | None = 960

    # Agent tunables (AGENT_DESIGN §3)
    match_max_m: float = 25.0
    report_radius_m: float = 300.0
    stop_speed_ms: float = 1.0
    # Zones sit on a ~3.2 km ring around the base and frames lie up to ~2 km from a center.
    zone_radius_m: float = 2000.0

    @field_validator(
        "data_dir",
        "models_dir",
        "cache_dir",
        "recordings_dir",
        "detector_weights",
        "detections_file",
    )
    @classmethod
    def _resolve_from_repo_root(cls, path: Path) -> Path:
        """Relative paths in .env are relative to the repo root, not the process cwd."""
        return path if path.is_absolute() else REPO_DIR / path

    @field_validator("llm_base_url", mode="before")
    @classmethod
    def _default_base_url(cls, value: object) -> object:
        """An empty SENTINEL_LLM_BASE_URL in .env means the organizer gateway."""
        return value or GLM_GATEWAY_URL

    @property
    def llm_enabled(self) -> bool:
        """True when both endpoint and key are configured."""
        return bool(self.llm_base_url and self.llm_api_key and self.llm_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton (override in tests via dependency overrides)."""
    return Settings()
