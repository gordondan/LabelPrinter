from __future__ import annotations

import threading
from typing import Optional

from .config import get_gpio_config


class GPIOManager:
    """
    Starts GPIO listening only when there is job activity; keeps it alive while
    jobs are queued/running; shuts down after idle for N seconds (default 30).
    Reads settings from config/config.json under { "gpio": { ... } }.
    """

    def __init__(self, logger=None):
        self._logger = logger
        self._lock = threading.Lock()
        self._listener = None
        self._enabled_cfg = False
        self._idle_shutdown_sec = 30
        self._active_count = 0
        self._timer: Optional[threading.Timer] = None
        self.reload_config()

    def reload_config(self):
        cfg = get_gpio_config()
        with self._lock:
            self._enabled_cfg = bool(cfg.get('enabled', False))
            self._idle_shutdown_sec = int(cfg.get('idle_shutdown_sec', 30))
        return cfg

    def _start_listener_locked(self):
        if not self._enabled_cfg:
            return
        if self._listener is not None:
            return
        try:
            from .gpio_listener import GPIOListener
            self._listener = GPIOListener(logger=self._logger)
            self._listener.start()
        except Exception as e:
            if self._logger:
                try:
                    self._logger.warning("GPIO listener failed to start: %s", e)
                except Exception:
                    pass
            self._listener = None

    def _stop_listener_locked(self):
        if self._listener is None:
            return
        try:
            self._listener.stop()
        except Exception:
            pass
        finally:
            self._listener = None

    def notify_job_activity(self, active_delta: int):
        """Call with +1 on job enqueue/start, -1 on job completion/error.
        Starts listener on first active, and schedules shutdown when goes idle.
        """
        with self._lock:
            # cancel any pending timer
            if self._timer:
                try:
                    self._timer.cancel()
                except Exception:
                    pass
                self._timer = None

            self._active_count = max(0, self._active_count + int(active_delta))
            if self._active_count > 0:
                # Ensure listener is running
                self._start_listener_locked()
                return

            # Schedule idle shutdown
            idle_sec = max(1, int(self._idle_shutdown_sec))
            def _shutdown():
                with self._lock:
                    if self._active_count == 0:
                        self._stop_listener_locked()
            self._timer = threading.Timer(idle_sec, _shutdown)
            self._timer.daemon = True
            self._timer.start()
