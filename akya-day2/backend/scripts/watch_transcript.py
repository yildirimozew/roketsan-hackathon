"""Render a watch-run event log (JSONL) as a complete, readable Markdown transcript.

    uv run python -m scripts.watch_transcript .cache/watch_runs/1350-1415.jsonl out.md

Everything the agents produced is included: every watcher verdict (all levels), patterns, level
changes, supervisor summaries, patterns and actions, alerts, tracker updates and warnings.
"""

import argparse
import json
from pathlib import Path
from typing import Any


def _vehicle_table(rows: list[dict[str, Any]], verdicts: dict[str, dict[str, Any]]) -> list[str]:
    out = [
        "| Vehicle | Level | Facts (code) | Reason (model) | Evidence | Note |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        v = verdicts.get(r["track_id"])
        facts = f"{r['one_liner']} · rubric {r['rubric']['score']} {r['rubric']['level']}"
        if v is None:
            out.append(f"| {r['track_id']} | LOW (quiet) | {facts} | – | – | – |")
            continue
        note = v.get("note") or "–"
        out.append(
            f"| {r['track_id']} | **{v['level']}** | {facts} | {v['reason']} | "
            f"{', '.join(v['evidence_ids'])} | {note} |"
        )
    return out


def render(events: list[dict[str, Any]]) -> str:
    """Markdown for a whole run."""
    lines: list[str] = []
    for e in events:
        t = e["type"]
        if t == "tick_started":
            frames = ", ".join(e["frames"]) or "none"
            checks = ", ".join(f"{w} → {sec}" for w, sec in e.get("checks", {}).items())
            lines += [
                "",
                f"## Tick {e['tick']}",
                "",
                f"{e['active_vehicles']} active vehicles · frames: {frames}",
                *(["", f"Checks this tick: {checks}"] if checks else []),
                "",
            ]
        elif t == "frame_analyzed":
            lines += [
                f"**Frame {e['image_id']}** ({e['sector']}): {len(e['detections'])} detections"
            ]
            for d in e["detections"]:
                match = (
                    f" → {d['track_id']} ({d['match_m']} m)" if d.get("track_id") else " → no track"
                )
                lines.append(f"- {d['detection_id']} {d['label']} {d['confidence']:.2f}{match}")
            lines.append("")
        elif t == "watcher_report":
            r = e["report"]
            verdicts = {v["track_id"]: v for v in r["vehicles"]}
            tools = ", ".join(e["tool_calls"]) or "–"
            lines += [
                f"### Watcher {e['watcher']} · {', '.join(e['sectors'])}",
                "",
                f"*{e['generated_by']}, {e['duration_ms'] / 1000:.1f} s, tool calls: {tools}*",
                "",
                f"> {r['street_state']}",
                "",
                *_vehicle_table(e["rows"], verdicts),
                "",
            ]
            for p in r["patterns"]:
                lines.append(
                    f"- **Group** {', '.join(p['track_ids'])}: {p['description']} "
                    f"({', '.join(p['evidence_ids'])})"
                )
            if e["warnings"]:
                lines += ["", *[f"- warning: {w}" for w in e["warnings"]]]
            lines.append("")
        elif t == "level_changed":
            state = "pending" if e["pending"] else "confirmed"
            lines.append(
                f"- Level {e['track_id']}: {e['from_level']} → {e['to_level']} "
                f"({state}, {e['by']}): {e['reason']}"
            )
        elif t == "supervisor_decision":
            d = e["decision"]
            tools = ", ".join(e["tool_calls"]) or "–"
            lines += [
                "",
                "### Supervisor",
                "",
                f"*{e['generated_by']}, {e['duration_ms'] / 1000:.1f} s, tool calls: {tools}*",
                "",
                f"**Threat level: {d['threat_level']}**",
                "",
                f"> {d['situation_summary']}",
                "",
            ]
            for p in d["patterns"]:
                lines.append(
                    f"- **Pattern** {', '.join(p['track_ids'])} "
                    f"({', '.join(p['sectors'])}): {p['description']}"
                )
            for a in e["actions"]:
                lines.append(f"- **Action** `{a['tool']}`: {a['summary']}")
            if d["watch_next"]:
                lines.append(f"- Watch next: {', '.join(d['watch_next'])}")
            lines += [*[f"- warning: {w}" for w in e["warnings"]], ""]
        elif t == "operator_alert":
            a = e["alert"]
            lines += [
                f"**Operator alert {a['alert_id']}** [{a['urgency']}] "
                f"{', '.join(a['track_ids'])}: {a['headline']}",
                "",
                f"> {a['description']}",
                "",
                f"Evidence: {', '.join(a['evidence_ids'])}",
                "",
            ]
        elif t == "authority_alert":
            a = e["alert"]
            s = a["suspicion"]
            lines += [
                f"**Alert {a['alert_id']}** [{a['urgency']}, {a['status']}] "
                f"{', '.join(a['track_ids'])}: {a['headline']}",
                "",
                f"- Hypothesis: {s['hypothesis']}",
                f"- Clears it: {s['what_would_clear_it']}",
                f"- Confidence: {s['confidence']} · evidence: {', '.join(s['evidence_ids'])}",
                "",
            ]
        elif t == "tracker_update":
            tr = e["tracker"]
            eta = f", ETA {tr['eta_to_base_min']} min" if tr["eta_to_base_min"] is not None else ""
            lines.append(
                f"- Tracker {tr['tracker_id']} {tr['state']} {tr['track_id']} "
                f"({tr['source']}): {tr['dist_to_base_m']} m from base, "
                f"{tr['speed_ms']} m/s{eta}"
            )
        elif t == "warning":
            lines.append(f"- warning ({e['scope']}): {e['message']}")
        elif t == "tick_completed":
            lines += [
                "",
                f"*Tick done in {e['duration_ms'] / 1000:.1f} s · levels {e['levels']}*",
                "",
                "---",
            ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()
    events = [json.loads(line) for line in args.log.read_text(encoding="utf-8").splitlines()]
    title = args.title or f"Watch run {args.log.stem}"
    args.out.write_text(f"# {title}\n" + render(events), encoding="utf-8")
    print(f"wrote {args.out} ({len(events)} events)")


if __name__ == "__main__":
    main()
