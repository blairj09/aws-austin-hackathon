"""Append-only JSONL audit log: every handoff, tool call, finding, and failure."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class AuditLog:
    path: Path | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    listeners: list[Callable[[dict[str, Any]], None]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _t0: float = field(default_factory=time.time, repr=False)

    def log(self, kind: str, actor: str, **data: Any) -> dict[str, Any]:
        event = {
            "t": round(time.time() - self._t0, 2),
            "kind": kind,  # handoff | tool_call | tool_result | finding | red_flag | error | final
            "actor": actor,
            **data,
        }
        with self._lock:
            self.events.append(event)
            if self.path:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a") as f:
                    f.write(json.dumps(event, default=str) + "\n")
        for fn in self.listeners:
            fn(event)
        return event

    def watch(self, chat, actor: str) -> None:
        """Log every tool request and result a chatlas chat makes."""
        chat.on_tool_request(
            lambda req: self.log("tool_call", actor, tool=req.name, arguments=req.arguments)
        )
        chat.on_tool_result(
            lambda res: self.log(
                "tool_result",
                actor,
                tool=res.request.name if res.request else None,
                result=_short(res.value),
                error=str(res.error) if res.error else None,
            )
        )


def _short(value: Any, n: int = 400) -> str:
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    return s if len(s) <= n else s[:n] + "…"
