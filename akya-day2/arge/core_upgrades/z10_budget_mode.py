"""Z10 - read the remaining LLM budget and make the running mode visible.

The organizer budget is 15 USD, never reset; the gateway reports it at `/key/info` (`spend`,
`max_budget`). Nothing calls it today, and no single field says whether an analysis ran with the
LLM, a fallback detector, tracks only or a replay.

Integration:
- `agent/llm_client.py`: a `BudgetMonitor` next to `GLMClient` (same base URL and key), checked at
  run start and every `check_every` calls; below the floor, watch mode switches to its recorded
  run and the pipeline to the template brief.
- `/api/health`: `BudgetStatus`; `Analysis` / watch run: `resolve_mode(...)` (contracts.RunMode).
- Settings: `SENTINEL_LLM_BUDGET_FLOOR_USD`, `SENTINEL_LLM_BUDGET_URL` (optional override).
- Verify the exact `/key/info` path and response shape against the gateway once: the parser
  accepts both a flat body and one nested under "info".
"""

from collections.abc import Callable
from typing import Any

import httpx
from app.domain.base import DomainModel

from .contracts import RunMode

BUDGET_FLOOR_USD = 1.0  # below this, stop live LLM calls and replay / use templates
CHECK_EVERY_CALLS = 10


class BudgetStatus(DomainModel):
    """Remaining gateway budget; `ok=False` also when it could not be read."""

    ok: bool
    spend_usd: float | None = None
    max_budget_usd: float | None = None
    remaining_usd: float | None = None
    detail: str


def budget_url(base_url: str) -> str:
    """`https://host/v1` -> `https://host/key/info` (the key endpoint sits at the gateway root)."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return f"{root}/key/info"


def parse_budget(body: dict[str, Any], floor_usd: float = BUDGET_FLOOR_USD) -> BudgetStatus:
    """Budget from a `/key/info` body (flat, or nested under "info")."""
    info = body.get("info", body) if isinstance(body.get("info"), dict) else body
    spend, cap = info.get("spend"), info.get("max_budget")
    if not isinstance(spend, int | float) or not isinstance(cap, int | float):
        return BudgetStatus(ok=False, detail="budget fields missing in /key/info")
    remaining = float(cap) - float(spend)
    return BudgetStatus(
        ok=remaining >= floor_usd,
        spend_usd=round(float(spend), 4),
        max_budget_usd=float(cap),
        remaining_usd=round(remaining, 4),
        detail=f"{remaining:.2f} of {float(cap):.2f} USD left"
        + ("" if remaining >= floor_usd else f" (below the {floor_usd:.2f} USD floor)"),
    )


async def fetch_budget(
    url: str,
    api_key: str,
    floor_usd: float = BUDGET_FLOOR_USD,
    transport: httpx.AsyncBaseTransport | None = None,
) -> BudgetStatus:
    """GET `/key/info`; network or parse errors give `ok=False` instead of raising."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            body = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        return BudgetStatus(ok=False, detail=f"budget check failed: {type(exc).__name__}")
    if not isinstance(body, dict):
        return BudgetStatus(ok=False, detail="unexpected /key/info body")
    return parse_budget(body, floor_usd)


class BudgetMonitor:
    """Re-checks the budget every `check_every` LLM calls; `allow_live()` gates new live calls."""

    def __init__(self, fetch: Callable[[], Any], check_every: int = CHECK_EVERY_CALLS) -> None:
        self._fetch = fetch  # async () -> BudgetStatus
        self._every = check_every
        self._calls = 0
        self.status: BudgetStatus | None = None

    async def allow_live(self) -> bool:
        """True while the budget is known to be above the floor. Unknown budget -> no live calls."""
        if self.status is None or self._calls % self._every == 0:
            self.status = await self._fetch()
        self._calls += 1
        return self.status.ok


def resolve_mode(
    *,
    replay: bool,
    llm_enabled: bool,
    budget_ok: bool,
    detector_available: bool,
    fallback_detector: bool,
) -> RunMode:
    """One label for how this analysis / run was produced (shown as a badge)."""
    if replay:
        return "replay"
    if not detector_available:
        return "tracks_only"
    if fallback_detector:
        return "detector_degraded"
    if not (llm_enabled and budget_ok):
        return "llm_off"
    return "full"
