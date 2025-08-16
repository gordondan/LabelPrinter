# rw402b_ble/printer.py
# Print PIL images to Munbyn/Beeprt RW402B over BLE (TSPL) using Bleak.

import asyncio
import math
from typing import Optional, Tuple

from bleak import BleakScanner, BleakClient

# Candidate GATT characteristics seen on RW402B
WRITE_CANDIDATES = [
    "49535343-8841-43f4-a8d4-ecbe34729bb3",  # Silabs RX (write)
    "0000fff2-0000-1000-8000-00805f9b34fb",  # FFF2 (write)
]

def _looks_like_rw402b(name: Optional[str]) -> bool:
    if not name:
        return False
    n = name.lower()
    return ("rw402b" in n) or ("munbyn" in n) or ("beeprt" in n)

def _mm_to_dots(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / 25.4))

def _pil_to_tspl_bitmap(img, label_w_mm: float, label_h_mm: float, dpi: int, invert: bool) -> Tuple[bytes, int, int]:
    """
    Convert a PIL.Image (any mode) to a TSPL BITMAP payload (packed 1bpp, MSB-first).
    Returns (packed_bytes, width_bytes, height_rows)
    """
    from PIL import Image

    label_w = _mm_to_dots(label_w_mm, dpi)
    label_h = _mm_to_dots(label_h_mm, dpi)

    im = img.convert("L")
    # Threshold to 1bpp: 0=black, 255=white
    im = im.point(lambda p: 0 if p < 128 else 255, mode='1')

    # Resize to label width, keep aspect
    w, h = im.size
    if w != label_w:
        new_h = int(round(h * (label_w / w)))
        im = im.resize((label_w, new_h), Image.NEAREST)

    # Clamp height to label height
    if im.height > label_h:
        im = im.crop((0, 0, im.width, label_h))

    # Pack bits MSB-first, 1 = black (RW402B needed invert=True in your tests)
    packed = bytearray()
    for y in range(im.height):
        byte = 0
        bitcount = 0
        for x in range(im.width):
            px = im.getpixel((x, y))  # 0 or 255
            bit = 1 if px == 0 else 0  # black->1, white->0
            byte = ((byte << 1) | bit) & 0xFF
            bitcount += 1
            if bitcount == 8:
                packed.append(byte)
                byte = 0
                bitcount = 0
        if bitcount:
            byte <<= (8 - bitcount)
            packed.append(byte)

    if invert:
        packed = bytes((~b) & 0xFF for b in packed)
    else:
        packed = bytes(packed)

    width_bytes = math.ceil(im.width / 8)
    height = im.height
    return packed, width_bytes, height

class RW402BPrinter:
    """
    Usage:
        p = RW402BPrinter(addr="DD:0D:30:32:20:B0")  # or leave addr=None to auto-scan
        p.print_pil_image(image, label_w_mm=57, label_h_mm=31.75, gap_mm=3)
    """

    def __init__(self, addr: Optional[str] = None, timeout: float = 4.0,
                 dpi: int = 203, invert: bool = True):
        self.addr = addr
        self.timeout = timeout
        self.dpi = dpi
        self.invert = invert
        self._write_uuid: Optional[str] = None
        self._write_resp: bool = True

    # ---------- public sync wrappers (safe to call from your app) ----------

    def print_pil_image(self, img, label_w_mm: float, label_h_mm: float, gap_mm: float = 3.0,
                        density: int = 8, speed: int = 4, direction: int = 1,
                        x: int = 0, y: int = 0, mode: int = 0):
        """Blocking wrapper."""
        return asyncio.run(self._async_print_pil_image(
            img, label_w_mm, label_h_mm, gap_mm, density, speed, direction, x, y, mode
        ))

    # ---------------------- async implementation ---------------------------

    async def _async_print_pil_image(self, img, label_w_mm: float, label_h_mm: float, gap_mm: float,
                                     density: int, speed: int, direction: int,
                                     x: int, y: int, mode: int) -> None:
        addr = self.addr or await self._scan_for_printer()
        if not addr:
            raise RuntimeError("RW402B not found during scan.")

        if not self._write_uuid:
            path = await self._choose_write_path(addr)
            if not path:
                raise RuntimeError("No writable BLE characteristic found on RW402B.")
            self._write_uuid, self._write_resp = path

        # Build TSPL and payload
        packed, wb, h = _pil_to_tspl_bitmap(img, label_w_mm, label_h_mm, self.dpi, self.invert)
        header = (
            f"SIZE {label_w_mm:.2f} mm,{label_h_mm:.2f} mm\r\n"
            f"GAP {gap_mm:.2f} mm,0\r\n"
            f"DENSITY {density}\r\n"
            f"SPEED {speed}\r\n"
            f"DIRECTION {direction}\r\n"
            "CLS\r\n"
        ).encode("ascii")
        bitcmd = f"BITMAP {x},{y},{wb},{h},{mode},".encode("ascii")
        tail = b"\r\nPRINT 1\r\n"
        blob = header + bitcmd + packed + tail

        await self._send_chunks(addr, self._write_uuid, self._write_resp, blob)

    # ----------------------------- helpers ---------------------------------

    async def _scan_for_printer(self) -> Optional[str]:
        print(f"Scanning for RW402B for {self.timeout:.1f}s…")
        devs = await BleakScanner.discover(timeout=self.timeout)
        # Choose the best by RSSI if multiple
        best = None
        best_rssi = -9999
        for d in devs:
            if _looks_like_rw402b(d.name):
                # Try to get RSSI from various places
                rssi = getattr(d, "rssi", None)
                if rssi is None and isinstance(getattr(d, "details", None), dict):
                    props = d.details.get("props") if isinstance(d.details.get("props"), dict) else None
                    if props and isinstance(props.get("RSSI"), int):
                        rssi = props["RSSI"]
                if rssi is None and getattr(d, "advertisement_data", None) is not None:
                    rssi = getattr(d.advertisement_data, "rssi", None)
                if not isinstance(rssi, int):
                    rssi = -999
                if rssi > best_rssi:
                    best = d
                    best_rssi = rssi
                print(f"  candidate: {d.address}  RSSI={rssi}  Name={d.name}")
        if best:
            print(f"Using {best.address} ({best.name})")
            return best.address
        return None

    async def _choose_write_path(self, addr: str) -> Optional[Tuple[str, bool]]:
        """Try candidates with response=True then False by doing a tiny write."""
        for uuid in WRITE_CANDIDATES:
            for resp in (True, False):
                try:
                    async with BleakClient(addr, timeout=10) as client:
                        await client.write_gatt_char(uuid, b"", response=resp)
                    print(f"Writable path OK: uuid={uuid}, response={resp}")
                    return uuid, resp
                except Exception as e:
                    print(f"Probe failed: uuid={uuid}, resp={resp}: {e}")
        return None

    async def _send_chunks(self, addr: str, uuid: str, resp: bool, blob: bytes):
        """Write in 20-byte chunks with a short delay to avoid MTU issues."""
        async with BleakClient(addr, timeout=20) as client:
            for i in range(0, len(blob), 20):
                await client.write_gatt_char(uuid, blob[i:i+20], response=resp)
                await asyncio.sleep(0.005)
