# Windows printer implementation for RW402B using Win32 print drivers
from __future__ import annotations

import win32print
import win32ui
import win32con
from PIL import ImageWin

class RW402BPrinter:
    """Windows driver-based printer wrapper compatible with Linux class API."""
    def __init__(self, addr=None, timeout: float = 4.0, dpi: int = 203, invert: bool = True, config: dict | None = None):
        # Keep signature compatibility; Windows path doesn't use BLE addr.
        self.timeout = timeout
        self.dpi = dpi
        self.invert = invert
        self.config = config or {}

    def print_pil_image(self, image, label_w_mm: float, label_h_mm: float, gap_mm: float = 3.0,
                        density: int = 8, speed: int = 4, direction: int = 1,
                        x: int = 0, y: int = 0, mode: int = 0,
                        printer_name: str | None = None, printer_config: dict | None = None) -> bool:
        width_px, height_px = image.size
        cfg = printer_config or {}
        try:
            hDC = win32ui.CreateDC()
            # Choose a label printer without relying on the OS default
            target_printer = printer_name or (self.config or {}).get('default_printer') or self._discover_label_printer_name()
            if not target_printer:
                raise RuntimeError("No label printer found. Set 'default_printer' in config or install a Munbyn/Beeprt (RW402B) printer.")
            print(f"Attempting to connect to printer: '{target_printer}'")
            hDC.CreatePrinterDC(target_printer)

            # windows_device_caps are stored in the global config
            caps = (self.config or {}).get('windows_device_caps', {})
            printer_width = hDC.GetDeviceCaps(caps.get('PHYSICALWIDTH', 110))
            printer_height = hDC.GetDeviceCaps(caps.get('PHYSICALHEIGHT', 111))
            printer_dpi_x = hDC.GetDeviceCaps(caps.get('LOGPIXELSX', 88))
            printer_dpi_y = hDC.GetDeviceCaps(caps.get('LOGPIXELSY', 90))
            printable_width = hDC.GetDeviceCaps(caps.get('HORZRES', 8))
            printable_height = hDC.GetDeviceCaps(caps.get('VERTRES', 10))
            offset_x = hDC.GetDeviceCaps(caps.get('PHYSICALOFFSETX', 112))
            offset_y = hDC.GetDeviceCaps(caps.get('PHYSICALOFFSETY', 113))

            print(f"\n=== Printer Info ===")
            print(f"Printer DPI: {printer_dpi_x}x{printer_dpi_y}")
            print(f"Physical size: {printer_width}x{printer_height} device units")
            print(f"Printable area: {printable_width}x{printable_height} pixels")
            print(f"Margins: left={offset_x}, top={offset_y} device units")

            hDC.StartDoc('Label')
            hDC.StartPage()
            hDC.SetMapMode(win32con.MM_TEXT)

            dib = ImageWin.Dib(image)

            if printable_width > width_px:
                auto_center_offset = (printable_width - width_px) // 2
            else:
                auto_center_offset = 0

            positioning_mode = cfg.get('positioning_mode', 'auto')
            if positioning_mode == 'auto':
                if printable_width > width_px:
                    h_offset = auto_center_offset
                else:
                    h_offset = offset_x
            elif positioning_mode == 'physical_offset':
                h_offset = offset_x
            elif positioning_mode == 'center':
                h_offset = auto_center_offset
            elif positioning_mode == 'manual':
                h_offset = cfg.get('horizontal_offset', 0)
            else:
                h_offset = offset_x

            additional_offset = cfg.get('horizontal_offset', 0)
            if additional_offset != 0 and positioning_mode != 'manual':
                h_offset += additional_offset

            dib.draw(hDC.GetHandleOutput(), (h_offset, 0, h_offset + width_px, height_px))
            print(f"Drawing at position ({h_offset}, 0, {h_offset + width_px}, {height_px})")

            hDC.EndPage()
            hDC.EndDoc()
            hDC.DeleteDC()
            print(f"Label sent to printer: {target_printer}")
            return True
        except Exception as e:
            print(f"Printing failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _discover_label_printer_name(self) -> str | None:
        """Find an installed printer that looks like the RW402B/Munbyn/Beeprt label printer."""
        try:
            flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            printers = win32print.EnumPrinters(flags)
            names = [p[2] for p in printers if isinstance(p, (list, tuple)) and len(p) >= 3]
            candidates = []
            for n in names:
                ln = (n or "").lower()
                score = 0
                if 'rw402b' in ln: score += 100
                if 'munbyn' in ln: score += 90
                if 'beeprt' in ln: score += 80
                if 'label' in ln: score += 10
                if score > 0:
                    candidates.append((score, n))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]
        except Exception:
            pass
        return None
