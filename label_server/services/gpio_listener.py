from __future__ import annotations

import os
import sys
import time
import logging
import threading
import subprocess
from typing import Optional


class GPIOListener:
    """
    Lightweight GPIO edge listener for Raspberry Pi using RPi.GPIO.

        Enable by setting environment variable GPIO_ENABLED=1. Configure via either:
            Specific today-button names (preferred):
                - TODAY_BUTTON_PIN (int, default 26, BCM numbering)
                - TODAY_BUTTON_EDGE (RISING|FALLING|BOTH, default FALLING)
                - TODAY_BUTTON_PULL (UP|DOWN|NONE, default UP)
                - TODAY_BUTTON_BOUNCE_MS (int ms, default 200)
                - TODAY_BUTTON_ACTION (optional: PRINT_TODAY)
            Or legacy generic names (backward compatible):
                - GPIO_PIN (int)
                - GPIO_EDGE (RISING|FALLING|BOTH)
                - GPIO_PULL (UP|DOWN|NONE)
                - GPIO_BOUNCE_MS (int ms)
                - GPIO_ACTION (optional)

    If GPIO_ACTION=PRINT_TODAY, pressing the pin will invoke label-printer.py
    to print a date label (today), using existing config and OS-specific printer.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._enabled = os.getenv('GPIO_ENABLED', '0') in ('1', 'true', 'TRUE', 'True', 'yes')
        self._thread_guard = threading.Lock()
        self._started = False
        self._GPIO = None  # type: ignore
        # Preferred specific vars, fallback to legacy
        pin = os.getenv('TODAY_BUTTON_PIN') or os.getenv('GPIO_PIN') or '26'
        edge = os.getenv('TODAY_BUTTON_EDGE') or os.getenv('GPIO_EDGE') or 'FALLING'
        pull = os.getenv('TODAY_BUTTON_PULL') or os.getenv('GPIO_PULL') or 'UP'
        bounce = os.getenv('TODAY_BUTTON_BOUNCE_MS') or os.getenv('GPIO_BOUNCE_MS') or '200'
        action = os.getenv('TODAY_BUTTON_ACTION') or os.getenv('GPIO_ACTION')
        self._pin = int(str(pin))
        self._bounce = int(str(bounce))
        self._edge = (str(edge) or 'FALLING').upper()
        self._pull = (str(pull) or 'UP').upper()
        self._action = action  # e.g., PRINT_TODAY
        self._last_fired = 0.0

    def start(self):
        if not self._enabled:
            self.logger.info("GPIO listener disabled (set GPIO_ENABLED=1 to enable).")
            return
        if not sys.platform.startswith('linux'):
            self.logger.info("GPIO listener only supported on Linux/Raspberry Pi; skipping on %s", sys.platform)
            return
        try:
            import RPi.GPIO as GPIO  # type: ignore
        except Exception as e:
            self.logger.warning("RPi.GPIO not available: %s. GPIO disabled.", e)
            return

        with self._thread_guard:
            if self._started:
                return
            self._started = True

        self._GPIO = GPIO
        GPIO.setmode(GPIO.BCM)

        pud = {
            'UP': GPIO.PUD_UP,
            'DOWN': GPIO.PUD_DOWN,
            'NONE': GPIO.PUD_OFF,
        }.get(self._pull, GPIO.PUD_UP)

        try:
            GPIO.setup(self._pin, GPIO.IN, pull_up_down=pud)
            edge_const = {
                'RISING': GPIO.RISING,
                'FALLING': GPIO.FALLING,
                'BOTH': GPIO.BOTH,
            }.get(self._edge, GPIO.RISING)

            GPIO.add_event_detect(self._pin, edge_const, callback=self._on_edge, bouncetime=self._bounce)
            self.logger.info("GPIO listener started on BCM pin %d (edge=%s, pull=%s, bounce=%dms) [action=%s]",
                             self._pin, self._edge, self._pull, self._bounce, (self._action or 'none'))
        except Exception as e:
            self.logger.error("Failed to initialize GPIO on pin %d: %s", self._pin, e)
            self.stop()

    def stop(self):
        try:
            if self._GPIO is not None:
                self._GPIO.cleanup()
        except Exception:
            pass
        finally:
            with self._thread_guard:
                self._started = False
            # Reduce log noise
            try:
                self.logger.debug("GPIO listener stopped.")
            except Exception:
                pass

    # --- Internal ---
    def _on_edge(self, channel: int):
        now = time.monotonic()
        # Extra guard in case bouncetime isn’t sufficient
        if (now - self._last_fired) * 1000.0 < max(0, self._bounce // 2):
            return
        self._last_fired = now
        try:
            self.logger.info("GPIO edge detected on pin %d (edge=%s)", channel, self._edge)
            self._handle_action(channel)
        except Exception as e:
            self.logger.error("GPIO callback error: %s", e)

    def _handle_action(self, channel: int):
        if not self._action:
            # Default: just log the event
            return
        act = self._action.upper()
        if act == 'PRINT_TODAY':
            self._print_today_label()

    def _print_today_label(self):
        """Emit front-end event and also invoke label-printer.py to print today's date label once."""
        # Notify clients (kiosk) to show busy state and messages
        try:
            from .events import bus
            bus.publish({"type": "print-today"})
        except Exception:
            pass
        try:
            script_path = os.path.join(os.path.dirname(__file__), '..', '..', 'label-printer.py')
            script_path = os.path.normpath(script_path)
            env = os.environ.copy()
            # Respect border default via env; default to enabled
            env.setdefault('LABEL_BORDER_ENABLED', '1')
            cmd = [sys.executable or 'python3', script_path, '-o', '-c', '1']
            self.logger.info("GPIO action PRINT_TODAY: running %s", ' '.join(cmd))
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
            if result.returncode == 0:
                self.logger.info("PRINT_TODAY OK: %s", (result.stdout or '').strip())
            else:
                self.logger.error("PRINT_TODAY failed rc=%s: %s", result.returncode, (result.stderr or result.stdout or '').strip())
        except Exception as e:
            self.logger.error("PRINT_TODAY exception: %s", e)
