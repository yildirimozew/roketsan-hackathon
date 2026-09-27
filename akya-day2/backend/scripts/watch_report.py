"""Render a traced watch run (JSONL with `agent_trace` events) as a readable Markdown report.

    uv run python -m scripts.watch_report .cache/watch_runs/1010-1030.jsonl out.md

For every tick and every agent turn it shows, in order: what the model received (input summary,
full message folded), each LLM call (the model's reasoning, its tool calls with arguments), each
tool result, and the final output after code checks, followed by what the output changed. The
system prompts are printed once in an appendix.
"""

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

Event = dict[str, Any]


def cell(text: Any) -> str:
    """Safe Markdown table cell."""
    return str(text if text is not None else "–").replace("|", "\\|").replace("\n", " ")


def pretty_user_message(text: str) -> str:
    """Indent the JSON blocks of a tick message so it can be read."""

    def indent(m: re.Match[str]) -> str:
        try:
            value = json.loads(m.group(2))
        except json.JSONDecodeError:
            return m.group(0)
        if isinstance(value, list):  # one item per line: compact but scannable
            body = "\n".join(json.dumps(v, ensure_ascii=False) for v in value) or "(empty)"
        else:
            body = json.dumps(value, ensure_ascii=False)
        return f"<{m.group(1)}>\n{body}\n</{m.group(1)}>"

    return re.sub(r"<(\w+)>\n(.*?)\n</\1>", indent, text, flags=re.S)


def input_summary(user: str) -> str:
    """One line: how many rows, one-liners, arrivals, notes, frames and reports were sent."""

    def count(tag: str) -> int:
        m = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", user, re.S)
        try:
            value = json.loads(m.group(1)) if m else []
        except json.JSONDecodeError:
            return 0
        return len(value) if isinstance(value, list) else 0

    first = user.split("\n", 1)[0]
    if "<vehicles>" in user:
        spots = user.count('"spot_check": true')
        return (
            f"{first} Sent in full: {count('vehicles')} vehicles ({spots} random spot checks); "
            f"as one-liners: {count('quiet_vehicles')}; new arrivals: {count('new_arrivals')}; "
            f"notes: {count('registry_notes')}; frames: {count('frames')}; "
            f"reports: {count('untrusted_reports')}."
        )
    return (
        f"{first} Watcher messages: {count('watcher_messages')}; unchecked sectors: "
        f"{count('unchecked_sectors')}; frames: {count('frames')}; recent events: "
        f"{count('recent_events')}; area reports: {count('untrusted_reports')}."
    )


def trim_result(result: Any) -> str:
    """Tool result as JSON, with long point lists shortened."""
    data = json.loads(json.dumps(result))
    for route in data.get("routes", []) if isinstance(data, dict) else []:
        pts = route.get("points", [])
        if len(pts) > 6:
            route["points"] = [*pts[:2], f"… {len(pts) - 4} more points …", *pts[-2:]]
    return json.dumps(data, ensure_ascii=False, indent=1)


def verdict_table(output: Event, rows: dict[str, Event]) -> list[str]:
    lines = [
        "| Vehicle | Facts computed by code | Level | Reason (model) | Note for the next watcher |",
        "|---|---|---|---|---|",
    ]
    for v in output.get("vehicles", []):
        # Raw model output may omit track_id; the agent derives it from the TRK-* evidence.
        trk = [e[4:] for e in v.get("evidence_ids") or [] if str(e).startswith("TRK-")]
        v = {**v, "track_id": v.get("track_id") or (trk[0] if trk else "?")}
        row = rows.get(v["track_id"], {})
        facts = row.get("one_liner", "")
        if row:
            facts += f" · rubric {row['rubric']['score']} {row['rubric']['level']}"
        lines.append(
            f"| {v['track_id']} | {cell(facts)} | **{v['level']}** | {cell(v['reason'])} "
            f"| {cell(v.get('note'))} |"
        )
    return lines


def render_call_args(name: str, args: Any, rows: dict[str, Event]) -> list[str]:
    if name == "submit_watch_report" and isinstance(args, dict):
        out = [f"> {cell(args.get('street_state'))}", "", *verdict_table(args, rows)]
        for p in args.get("patterns", []):
            ids = ", ".join(p.get("track_ids") or []) or "(ids from evidence)"
            out.append(f"- Group {ids}: {p.get('description')}")
        return out
    return ["```json", json.dumps(args, ensure_ascii=False, indent=1), "```"]


def render_turn(trace: Event, rows: dict[str, Event], effects: list[str]) -> list[str]:
    lines = [
        f"**Input.** {input_summary(trace['user_message'])}",
        "",
        "<details><summary>Full message the model received (system prompt: "
        f"<code>{trace['prompt_file']}</code>, see appendix)</summary>",
        "",
        "```text",
        pretty_user_message(trace["user_message"]),
        "```",
        "",
        "</details>",
        "",
    ]
    results = {s["id"]: s for s in trace["steps"] if s["step"] == "tool"}
    for step in trace["steps"]:
        if step["step"] == "repair":
            lines += [f"**Code → model:** _{step['message']}_", ""]
            continue
        if step["step"] != "llm":
            continue
        cached = " · from cache" if step["cached"] else ""
        lines += [
            f"**LLM call {step['call']}** · {step['latency_ms'] / 1000:.1f} s · "
            f"{step['prompt_tokens']} tokens in, {step['completion_tokens']} out{cached}",
            "",
        ]
        if not step["reasoning"]:
            lines += ["_(GLM returned no reasoning text for this call)_", ""]
        else:
            lines += [
                "<details><summary>Model reasoning</summary>",
                "",
                *[f"> {line}" if line else ">" for line in step["reasoning"].strip().splitlines()],
                "",
                "</details>",
                "",
            ]
        if step["content"].strip():
            lines += [f"Model text: {step['content'].strip()}", ""]
        for call in step["tool_calls"]:
            lines += [f"→ **Tool call `{call['name']}`**", ""]
            lines += render_call_args(call["name"], call["arguments"], rows)
            lines.append("")
            res = results.get(call["id"])
            if res is not None:
                if res["result"] == {"ok": True}:
                    lines += ["← accepted by code", ""]
                elif "error" in res["result"]:
                    lines += [f"← **rejected by code:** {res['result']['error']}", ""]
                else:
                    lines += [
                        "<details><summary>← result</summary>",
                        "",
                        "```json",
                        trim_result(res["result"]),
                        "```",
                        "",
                        "</details>",
                        "",
                    ]
    lines += [
        f"**Result.** Generated by: {trace['generated_by']} · {trace['duration_ms'] / 1000:.1f} s"
    ]
    lines += [f"- {e}" for e in effects] or ["- no level changes"]
    return [*lines, ""]


def render(events: list[Event], title: str) -> str:
    by_tick: dict[str, list[Event]] = defaultdict(list)
    for e in events:
        by_tick[e["tick"]].append(e)
    traces = [e for e in events if e["type"] == "agent_trace"]
    calls = [s for tr in traces for s in tr["steps"] if s["step"] == "llm"]
    first_start = next(e for e in events if e["type"] == "tick_started")
    out = [
        f"# {title}",
        "",
        "How to read this: every tick starts with a table of what happened. Then each agent turn "
        "shows **Input** (what the model received; open the fold for the full message), each "
        "**LLM call** with the model's own **reasoning** and its **tool calls**, the answer from "
        "code (**←**), and the **Result** it had on the car registry. Numbers in the input are "
        "computed by code; the model only judges and writes. Model text is in Turkish "
        "(`SENTINEL_BRIEF_LANGUAGE=tr`).",
        "",
        f"- Ticks: {', '.join(by_tick)}",
        f"- Watchers and the sector each checked at {first_start['tick']}: "
        + ", ".join(f"{w} → {s}" for w, s in first_start["checks"].items()),
        f"- LLM calls: {len(calls)} · tokens in {sum(c['prompt_tokens'] for c in calls)}, "
        f"out {sum(c['completion_tokens'] for c in calls)}",
        "",
    ]
    for tick, evs in by_tick.items():
        start = next(e for e in evs if e["type"] == "tick_started")
        sup = next((e for e in evs if e["type"] == "supervisor_decision"), None)
        alerts = [e["alert"] for e in evs if e["type"] == "operator_alert"]
        changes = [e for e in evs if e["type"] == "level_changed"]
        done = next((e for e in evs if e["type"] == "tick_completed"), None)
        out += [f"## Tick {tick}", "", "| | |", "|---|---|"]
        out.append(
            "| Checks | " + ", ".join(f"{w} → {s}" for w, s in start["checks"].items()) + " |"
        )
        out.append(f"| Drone frames | {', '.join(start['frames']) or 'none'} |")
        out.append(
            f"| Level changes | {sum(1 for c in changes if c['pending'])} pending, "
            f"{sum(1 for c in changes if not c['pending'])} confirmed |"
        )
        if sup:
            out.append(f"| Supervisor threat level | **{sup['decision']['threat_level']}** |")
        for a in alerts:
            out.append(
                f"| Operator alert {a['alert_id']} [{a['urgency']}] | {cell(a['headline'])} |"
            )
        if done:
            out.append(
                f"| Tick time | {done['duration_ms'] / 1000:.0f} s · levels {done['levels']} |"
            )
        out.append("")

        for fe in (e for e in evs if e["type"] == "frame_analyzed"):
            out += [
                f"### Frame {fe['image_id']} · {fe['sector']} (YOLO, code)",
                "",
                f"{fe['note']}. Tracked vehicles inside the frame: "
                f"{', '.join(fe['tracks_in_frame'])}.",
                "",
                "| Detection | Type | Confidence | Matched vehicle | Distance |",
                "|---|---|---|---|---|",
                *[
                    f"| {d['detection_id']} | {d['label']} | {d['confidence']:.2f} | "
                    f"{d['track_id'] or 'no track'} | "
                    f"{'–' if d['match_m'] is None else str(d['match_m']) + ' m'} |"
                    for d in fe["detections"]
                ],
                "",
            ]

        reports = {e["watcher"]: e for e in evs if e["type"] == "watcher_report"}
        for tr in (e for e in evs if e["type"] == "agent_trace"):
            if tr["agent"] == "supervisor":
                continue
            wid = tr["agent"].split(":")[1]
            rep = reports.get(wid, {})
            rows = {r["track_id"]: r for r in rep.get("rows", [])}
            eff = [
                f"{c['track_id']}: {c['from_level']} → {c['to_level']} "
                f"({'pending until the next check' if c['pending'] else 'confirmed'})"
                for c in changes
                if c["by"] == tr["agent"]
            ]
            eff += [w for w in rep.get("warnings", [])]
            out += [f"### Watcher {wid} checks {', '.join(rep.get('sectors', []))}", ""]
            out += render_turn(tr, rows, eff)
        for wid, rep in reports.items():
            if not rep["rows"]:
                out += [
                    f"### Watcher {wid} checks {', '.join(rep['sectors'])}",
                    "",
                    "No vehicles.",
                    "",
                ]

        sup_trace = next(
            (e for e in evs if e["type"] == "agent_trace" and e["agent"] == "supervisor"), None
        )
        if sup_trace and sup:
            eff = [f"`{a['tool']}`: {a['summary']}" for a in sup["actions"]]
            eff += [
                f"{c['track_id']}: {c['from_level']} → {c['to_level']} (supervisor)"
                for c in changes
                if c["by"] == "supervisor"
            ]
            out += ["### Supervisor", ""]
            out += render_turn(sup_trace, {}, eff)
            d = sup["decision"]
            out += [
                f"**Situation summary for the operator ({d['threat_level']}):**",
                "",
                f"> {d['situation_summary']}",
                "",
            ]
            for a in alerts:
                out += [
                    f"**Operator alert {a['alert_id']}** [{a['urgency']}] "
                    f"{', '.join(a['track_ids'])}",
                    "",
                    f"> **{a['headline']}**",
                    ">",
                    f"> {a['description']}",
                    "",
                ]
        out += ["---", ""]

    out += ["## Appendix: system prompts", ""]
    seen: set[str] = set()
    for tr in traces:
        key = tr["agent"].split(":")[0]
        if key in seen:
            continue
        seen.add(key)
        out += [
            f"### {tr['prompt_file']} (as sent to {tr['agent']}; other watchers differ only "
            "in their id and area)",
            "",
            "```markdown",
            tr["system_prompt"],
            "```",
            "",
        ]
    return "\n".join(out) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--title", default="Watch run")
    args = parser.parse_args()
    events = [json.loads(line) for line in args.log.read_text(encoding="utf-8").splitlines()]
    args.out.write_text(render(events, args.title), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
