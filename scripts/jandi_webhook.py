"""
Claude Code Stop hook → Jandi webhook relay.

stdin: {"session_id": "...", "transcript_path": "...", "hook_event_name": "Stop"}
Reads the latest assistant text from the transcript JSONL and POSTs it to Jandi.
Silent on failure (must not block the user).
"""
import json
import sys
import urllib.request
import urllib.error

WEBHOOK_URL = "https://wh.jandi.com/connect-api/webhook/11320800/7c1bdd4a0947be10377703affd57e97a"
MAX_BODY_CHARS = 3000


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tp = payload.get("transcript_path")
    if not tp:
        return 0

    try:
        with open(tp, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return 0

    last_text = None
    for line in reversed(lines[-200:]):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") != "assistant":
            continue
        for c in e.get("message", {}).get("content", []) or []:
            if c.get("type") == "text":
                t = (c.get("text") or "").strip()
                if t:
                    last_text = t
                    break
        if last_text:
            break

    if not last_text:
        return 0

    body = last_text if len(last_text) <= MAX_BODY_CHARS else last_text[:MAX_BODY_CHARS] + "\n\n…(truncated)"

    msg = {
        "body": body,
        "connectColor": "#e89200",
        "connectInfo": [
            {"title": "Claude Code 응답", "description": f"session {payload.get('session_id','')[:8]}"}
        ],
    }
    data = json.dumps(msg).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={
            "Accept": "application/vnd.tosslab.jandi-v2+json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5).read()
    except (urllib.error.URLError, TimeoutError):
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
