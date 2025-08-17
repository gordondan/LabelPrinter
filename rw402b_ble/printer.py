"""
OS-dispatching import shim for RW402B printing.
On Linux/Pi: use BLE TSPL via bleak (rw402b_ble.linux.printer.RW402BPrinter).
On Windows: use Win32 print driver (rw402b_ble.windows.printer.RW402BPrinter).
"""

import platform

system = platform.system().lower()
if system == 'windows':
    from .windows.printer import RW402BPrinter  # type: ignore
else:
    from .linux.printer import RW402BPrinter  # type: ignore
