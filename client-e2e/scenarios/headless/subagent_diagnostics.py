"""Headless profile rejections retain their source on stderr."""

from __future__ import annotations

from e2e.app_server.events import assistant_msg, complete_entry, turn_completed
from e2e.app_server.scenario import Timeline

_ENTRY_ID = "profile-diagnostics-assistant"
_added = assistant_msg(
    "finished without the rejected profiles",
    entry_id=_ENTRY_ID,
    generation_status="in_progress",
)

client_args = ("-p", "hello", "--output", "streaming")
handshake = {
    "runtime/read": {
        "runtime": {
            "issues": [
                {
                    "file": ".vibe/agents/large.toml",
                    "message": "instructions: String should have at most 65536 characters",
                }
            ]
        }
    }
}

timeline: Timeline = ["", _added, complete_entry(_ENTRY_ID), turn_completed()]
stdout_before_completion = (
    {**_added["params"]["entry"], "generationStatus": "completed"},
)
headless_stderr = "Warning: .vibe/agents/large.toml: instructions: String should have at most 65536 characters\n"
headless_requests = ("runtime/read", "session/stop")
