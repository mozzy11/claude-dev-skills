#!/usr/bin/env python3
"""Lists the friction signals in Claude Code session transcripts (.jsonl).

Usage: retro_signals.py <transcript.jsonl> [more.jsonl ...]

Prints, per session: the user's own messages with the assistant text right
before each, tool errors and blocked calls, retried commands, MCP disconnects,
Monitor expiries, and long waits between user messages. It finds candidates
for the session-retro skill; it does not judge them.
"""
import json
import re
import sys
from datetime import datetime

ERROR_HINTS = re.compile(
    r"ENOSPC|PUSH BLOCKED|Blocked:|permission|rejected|denied|timed out|"
    r"did not complete within|Traceback|BUILD FAILURE|FAILURE!|ERROR\]|"
    r"exit code [1-9]|CONNECT_TIMEOUT|failed to connect|No matching deferred tools",
    re.IGNORECASE,
)
SYSTEM_MARKERS = ("<task-notification>", "[SYSTEM NOTIFICATION", "<command-", "This session is being continued")
WRAPPERS = re.compile(
    r"<system-reminder>.*?</system-reminder>|<ide_[a-z_]+>.*?</ide_[a-z_]+>|<task-notification>.*?</task-notification>",
    re.DOTALL,
)
def own_words(text):
    """The user's own text, without the reminders and IDE context the harness wraps around it."""
    return WRAPPERS.sub("", text or "").strip()


def parse_time(entry):
    stamp = entry.get("timestamp")
    if not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def text_of(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts)


def short(text, limit=300):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def report(path):
    entries = []
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    print(f"=== {path} ({len(entries)} lines)")
    last_assistant_text = ""
    last_user_time = None
    commands = {}
    counts = {"user": 0, "errors": 0, "retries": 0, "gaps": 0}

    for entry in entries:
        attachment = entry.get("attachment") or {}
        if entry.get("type") == "attachment" and attachment.get("type") == "queued_command":
            if (attachment.get("origin") or {}).get("kind") == "human":
                prompt = attachment.get("prompt")
                said = own_words(text_of(prompt) if isinstance(prompt, list) else str(prompt or ""))
                if said:
                    counts["user"] += 1
                    print(f"  [user, mid-turn] {short(said, 400)}")
                    if last_assistant_text:
                        print(f"         after: {short(last_assistant_text, 240)}")
            continue
        message = entry.get("message") or {}
        role = message.get("role")
        content = message.get("content")
        when = parse_time(entry)

        if role == "assistant":
            said = text_of(content)
            if said.strip():
                last_assistant_text = said
            for block in content or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    command = (block.get("input") or {}).get("command")
                    if command:
                        key = re.sub(r"\s+", " ", command)[:160]
                        commands[key] = commands.get(key, 0) + 1
            continue

        if role != "user":
            continue

        if isinstance(content, list) and any(
            isinstance(block, dict) and block.get("type") == "tool_result" for block in content
        ):
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                result = block.get("content")
                result_text = text_of(result) if isinstance(result, list) else str(result or "")
                if block.get("is_error") or ERROR_HINTS.search(result_text[:2000]):
                    counts["errors"] += 1
                    print(f"  [tool] {short(result_text, 240)}")
            continue

        said = own_words(text_of(content))
        if not said or said.startswith(SYSTEM_MARKERS):
            continue
        counts["user"] += 1
        if when and last_user_time and (when - last_user_time).total_seconds() > 3600:
            counts["gaps"] += 1
            print(f"  [gap] {int((when - last_user_time).total_seconds() // 60)} min before the next user message")
        if when:
            last_user_time = when
        print(f"  [user] {short(said, 400)}")
        if last_assistant_text:
            print(f"         after: {short(last_assistant_text, 240)}")

    for command, times in commands.items():
        if times >= 3:
            counts["retries"] += 1
            print(f"  [retry x{times}] {short(command, 200)}")

    print(f"  summary: {counts}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    for path in sys.argv[1:]:
        report(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
