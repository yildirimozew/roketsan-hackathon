"""Car registry: shared per-vehicle memory for watch mode (level, pending change, notes).

Level rules (docs/AGENT_PROMPTS_AND_TOOLS.md §3.2), enforced here rather than in prompts:
1. A watcher may raise a level or keep it, never lower it.
2. A watcher's raise becomes the registry level after two consecutive ticks; until then it is
   `pending`.
3. The supervisor's `set_level` applies immediately and may lower.
"""

from dataclasses import dataclass

from app.domain.watch import WATCH_LEVELS, Note, PendingLevel, RegistryEntry, WatchLevel


def level_index(level: WatchLevel) -> int:
    """LOW=0, MEDIUM=1, HIGH=2."""
    return WATCH_LEVELS.index(level)


@dataclass(frozen=True)
class LevelChange:
    """A level transition to report as an event."""

    track_id: str
    from_level: WatchLevel
    to_level: WatchLevel
    by: str
    pending: bool
    reason: str


class CarRegistry:
    """In-memory registry for one watch run."""

    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def get(self, track_id: str) -> RegistryEntry:
        """Entry for a vehicle (created at LOW on first use)."""
        return self._entries.setdefault(track_id, RegistryEntry(track_id=track_id))

    def entries(self) -> list[RegistryEntry]:
        """All entries, sorted by track id."""
        return [self._entries[k] for k in sorted(self._entries)]

    def note_ids(self) -> set[str]:
        """Every note id in the registry (for evidence validation)."""
        return {n.id for e in self._entries.values() for n in e.notes}

    def effective_level(self, track_id: str) -> WatchLevel:
        """The higher of the registry level and a pending raise."""
        e = self.get(track_id)
        if e.pending is not None and level_index(e.pending.level) > level_index(e.level):
            return e.pending.level
        return e.level

    def add_note(
        self,
        track_id: str,
        tick: str,
        author: str,
        level: WatchLevel,
        text: str,
        evidence_ids: list[str],
    ) -> Note:
        """Append a note; ids are NOTE-<track_id>-<n>."""
        e = self.get(track_id)
        note = Note(
            id=f"NOTE-{track_id}-{len(e.notes) + 1}",
            tick=tick,
            author=author,
            level=level,
            text=text,
            evidence_ids=evidence_ids,
        )
        e.notes.append(note)
        return note

    def propose(
        self, track_id: str, level: WatchLevel, tick: str, by: str, reason: str
    ) -> LevelChange | None:
        """A watcher's level for this tick, under rules 1 and 2."""
        e = self.get(track_id)
        if level_index(level) <= level_index(e.level):
            e.pending = None  # back to (or below) the registry level: drop any pending raise
            return None
        if e.pending is not None and e.pending.level == level:
            if e.pending.since == tick:
                return None
            old = e.level
            e.level, e.pending = level, None
            return LevelChange(track_id, old, level, by, pending=False, reason=reason)
        e.pending = PendingLevel(level=level, since=tick, by=by)
        return LevelChange(track_id, e.level, level, by, pending=True, reason=reason)

    def lower(self, track_id: str, level: WatchLevel, by: str, reason: str) -> LevelChange | None:
        """De-escalation by a watcher (the caller checked it is allowed): applies immediately."""
        e = self.get(track_id)
        if level_index(level) >= level_index(e.level):
            return None
        old = e.level
        e.level, e.pending = level, None
        return LevelChange(track_id, old, level, by, pending=False, reason=reason)

    def set_level(
        self, track_id: str, level: WatchLevel, by: str, reason: str
    ) -> LevelChange | None:
        """Supervisor override (rule 3): applies immediately and clears any pending raise."""
        e = self.get(track_id)
        old = e.level
        e.pending = None
        if old == level:
            return None
        e.level = level
        return LevelChange(track_id, old, level, by, pending=False, reason=reason)
