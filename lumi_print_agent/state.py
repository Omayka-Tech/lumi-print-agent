"""Estado compartido del proceso (último trabajo, callback de UI)."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional


class AgentState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_ok: Optional[bool] = None
        self.last_error: str = ""
        self.last_at: str = ""
        self.last_detail: str = ""
        self.open_ui: Optional[Callable[[], None]] = None

    def record(self, ok: bool, detail: str = "", error: str = "") -> None:
        with self._lock:
            self.last_ok = ok
            self.last_detail = detail
            self.last_error = error
            self.last_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "ok": self.last_ok,
                "error": self.last_error,
                "at": self.last_at,
                "detail": self.last_detail,
            }


RUNTIME = AgentState()
