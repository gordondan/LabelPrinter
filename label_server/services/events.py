from __future__ import annotations

import json
import queue
import threading
from typing import Any, List


class EventBus:
    def __init__(self):
        self._subs: List[queue.Queue] = []
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue()
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subs.remove(q)
            except ValueError:
                pass

    def publish(self, event: Any) -> None:
        with self._lock:
            subs = list(self._subs)
        data = json.dumps(event)
        for q in subs:
            try:
                q.put_nowait(data)
            except Exception:
                pass


bus = EventBus()
