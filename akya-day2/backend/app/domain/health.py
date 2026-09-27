"""Health endpoint model."""

from typing import Literal

from app.domain.base import DomainModel


class ComponentStatus(DomainModel):
    """Availability of one external dependency."""

    available: bool
    detail: str


class Health(DomainModel):
    """Liveness plus the state of every dependency with a fallback."""

    status: Literal["ok"] = "ok"
    version: str
    llm: ComponentStatus
    detector: ComponentStatus
    data: ComponentStatus
