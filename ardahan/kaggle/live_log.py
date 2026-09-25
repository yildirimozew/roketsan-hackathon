"""Read a running Kaggle kernel's log live (the CLI's `kernels logs` returns nothing until the run ends).

Uses the SDK's GetKernelSessionLogsStream: Server-Sent Events while the session runs, the persisted
JSON log once it has ended. Prints log lines matching --grep, for at most --seconds.

Usage: python ardahan/kaggle/live_log.py OWNER/KERNEL [--seconds 60] [--grep REGEX]
Credentials: ~/.kaggle/kaggle.json, or KAGGLE_USERNAME / KAGGLE_KEY in the environment.
"""
import argparse
import json
import re
import sys
import threading
import time

from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.kernels.types.kernels_api_service import ApiGetKernelSessionLogsStreamRequest

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\\\S+?\\")


def lines_from_payload(text: str):
    text = text.strip()
    if text.startswith("["):  # persisted log: JSON list of {"stream_name","time","data"}
        for e in json.loads(text):
            yield e.get("time"), e.get("data", "")
        return
    for raw in text.splitlines():  # SSE: "data: {...}" events
        if not raw.startswith("data:"):
            continue
        body = raw[5:].strip()
        try:
            e = json.loads(body)
            yield e.get("time"), e.get("data", "")
        except json.JSONDecodeError:
            yield None, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kernel")
    ap.add_argument("--seconds", type=int, default=60)
    ap.add_argument("--grep", default=".")
    ap.add_argument("--tail", type=int, default=40)
    a = ap.parse_args()
    owner, slug = a.kernel.split("/")
    api = KaggleApi()
    api.authenticate()
    req = ApiGetKernelSessionLogsStreamRequest()
    req.user_name, req.kernel_slug, req.wait_for_logs_url_seconds = owner, slug, 30

    out = []

    def fetch():
        # Send the prepared request ourselves: the SDK's call() waits for the whole body,
        # and an SSE stream only ends when the session does.
        with api.build_kaggle_client() as k:
            hc = k._http_client
            hc._init_session()
            http_req = hc._prepare_request("kernels.KernelsApiService", "GetKernelSessionLogsStream", req)
            settings = hc._session.merge_environment_settings(http_req.url, {}, None, None, None)
            settings["stream"] = True
            r = hc._session.send(http_req, **settings)
            if r.status_code != 200:
                out.append(f"HTTP {r.status_code}: {r.text[:300]}")
                return
            for line in r.iter_lines(decode_unicode=True):
                out.append((line or "") + "\n")

    t = threading.Thread(target=fetch, daemon=True)
    t.start()
    t.join(a.seconds)
    pat = re.compile(a.grep)
    hits = []
    for ts, data in lines_from_payload("".join(out)):
        for line in data.replace("\r", "\n").split("\n"):
            line = ANSI.sub("", line).strip()
            if line and pat.search(line):
                hits.append(f"{ts:9.1f}  {line[:220]}" if isinstance(ts, (int, float)) else line[:220])
    print("\n".join(hits[-a.tail:]) if hits else f"(no matching lines; {sum(map(len, out))} bytes received)")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
