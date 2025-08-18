# Linux BLE printer implementation for RW402B (TSPL via Bleak)
from __future__ import annotations

import asyncio
import math
from typing import Optional, Tuple
import time
import os

from bleak import BleakScanner, BleakClient

# Enable verbose timing/debug by environment variable (default on)
DEBUG = os.getenv('RW402B_DEBUG', '1').lower() in ('1', 'true', 'yes', 'y')
# Tunables: chunk size (bytes) and per-chunk sleep in milliseconds
CHUNK_SIZE = max(1, int(os.getenv('RW402B_CHUNK', '20') or '20'))
THROTTLE_MS = max(0, int(os.getenv('RW402B_THROTTLE_MS', '0') or '0'))
PREFER_RESP = os.getenv('RW402B_PREFER_RESP', '0').lower() in ('1','true','yes','y')

def _dbg(msg: str):
    if DEBUG:
        print(f"[rw402b] {msg}")

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

    t0 = time.monotonic()
    label_w = _mm_to_dots(label_w_mm, dpi)
    label_h = _mm_to_dots(label_h_mm, dpi)

    im = img.convert("L")
    # Threshold to 1bpp: 0=black, 255=white
    im = im.point(lambda p: 0 if p < 128 else 255, mode='1')

    # Resize to label width, keep aspect
    w, h = im.size
    resized = False
    if w != label_w:
        new_h = int(round(h * (label_w / w)))
        im = im.resize((label_w, new_h), Image.NEAREST)
        resized = True

    # Clamp height to label height
    cropped = False
    if im.height > label_h:
        im = im.crop((0, 0, im.width, label_h))
        cropped = True

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
    dt = (time.monotonic() - t0) * 1000.0
    _dbg(f"bitmap: src={w}x{h} dots, target={label_w}x{label_h} dots, resized={resized}, cropped={cropped}, wb={width_bytes}, h={height}, invert={invert}, took={dt:.1f}ms")
    return packed, width_bytes, height

class RW402BPrinter:
    """
    Linux/Pi BLE implementation. Usage:
        p = RW402BPrinter(addr="DD:0D:30:32:20:B0")
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

    def print_pil_image(self, img, label_w_mm: float, label_h_mm: float, gap_mm: float = 3.0,
                        density: int = 8, speed: int = 4, direction: int = 1,
                        x: int = 0, y: int = 0, mode: int = 0):
        return asyncio.run(self._async_print_pil_image(
            img, label_w_mm, label_h_mm, gap_mm, density, speed, direction, x, y, mode
        ))

    def probe(self) -> bool:
        """Quiet connectivity test at startup. Returns True if a writable path is found.
        Caches discovered MAC and write UUID for faster subsequent prints."""
        try:
            return asyncio.run(self._async_probe())
        except Exception as e:
            _dbg(f"probe failed: {e}")
            return False

    async def _async_probe(self) -> bool:
        addr = self.addr
        if not addr:
            t0 = time.monotonic()
            addr = await self._scan_for_printer()
            _dbg(f"probe: initial scan took {(time.monotonic()-t0)*1000:.1f}ms; addr={addr}")
            if not addr:
                return False
            self.addr = addr
        # Try to establish a writable path; prefer no-response
        path = await self._choose_write_path(addr)
        if not path:
            # If we had a configured addr and probing failed, try one scan and retry
            t0 = time.monotonic()
            new_addr = await self._scan_for_printer()
            _dbg(f"probe: retry scan took {(time.monotonic()-t0)*1000:.1f}ms; addr={new_addr}")
            if new_addr:
                self.addr = new_addr
                path = await self._choose_write_path(new_addr)
        if not path:
            return False
        self._write_uuid, self._write_resp = path
        return True

    async def _async_print_pil_image(self, img, label_w_mm: float, label_h_mm: float, gap_mm: float,
                                     density: int, speed: int, direction: int,
                                     x: int, y: int, mode: int) -> None:
        t_start = time.monotonic()
        # Use configured MAC if provided; scan only if missing or on failure.
        addr = self.addr
        scanned_once = False

        async def ensure_write_path(cur_addr: str):
            if not self._write_uuid:
                t1 = time.monotonic()
                path = await self._choose_write_path(cur_addr)
                _dbg(f"phase: choose_write_path took {(time.monotonic()-t1)*1000:.1f}ms")
                if not path:
                    raise RuntimeError("No writable BLE characteristic found on RW402B.")
                self._write_uuid, self._write_resp = path

        # If we don't have an address, scan once up front
        if not addr:
            t0 = time.monotonic()
            addr = await self._scan_for_printer()
            _dbg(f"phase: scan took {(time.monotonic()-t0)*1000:.1f}ms")
            scanned_once = True
            if not addr:
                raise RuntimeError("RW402B not found during scan.")

        # Build payload
        t2 = time.monotonic()
        packed, wb, h = _pil_to_tspl_bitmap(img, label_w_mm, label_h_mm, self.dpi, self.invert)
        _dbg(f"phase: bitmap conversion took {(time.monotonic()-t2)*1000:.1f}ms; payload={len(packed)} bytes")
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

        async def try_send(cur_addr: str):
            # Ensure we have a write path for this address
            await ensure_write_path(cur_addr)
            t3 = time.monotonic()
            await self._send_chunks(cur_addr, self._write_uuid, self._write_resp, blob)
            send_ms = (time.monotonic() - t3) * 1000.0
            total_ms = (time.monotonic() - t_start) * 1000.0
            _dbg(f"phase: send took {send_ms:.1f}ms; total print call took {total_ms:.1f}ms")

        try:
            await try_send(addr)
        except Exception as e:
            # On failure, scan once (if not already), reset path, and retry
            if not scanned_once:
                _dbg(f"send/connect failed using configured addr; scanning to retry… ({e})")
                t0 = time.monotonic()
                new_addr = await self._scan_for_printer()
                _dbg(f"phase: scan (retry) took {(time.monotonic()-t0)*1000:.1f}ms")
                if new_addr:
                    addr = new_addr
                    self._write_uuid = None  # force re-probe for new address
                    await try_send(addr)
                    return
            # If already scanned once or scan failed, re-raise
            raise

    async def _scan_for_printer(self) -> Optional[str]:
        _dbg(f"Scanning for RW402B for {self.timeout:.1f}s…")
        t0 = time.monotonic()
        devs = await BleakScanner.discover(timeout=self.timeout)
        _dbg(f"scan: discover returned {len(devs)} devices in {(time.monotonic()-t0)*1000:.1f}ms")
        best = None
        best_rssi = -9999
        for d in devs:
            if _looks_like_rw402b(d.name):
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
                _dbg(f"  candidate: {d.address}  RSSI={rssi}  Name={d.name}")
        if best:
            _dbg(f"Using {best.address} ({best.name})")
            return best.address
        return None

    async def _choose_write_path(self, addr: str) -> Optional[Tuple[str, bool]]:
        for uuid in WRITE_CANDIDATES:
            # Order depends on preference; default to no-response first
            order = (True, False) if PREFER_RESP else (False, True)
            for resp in order:
                try:
                    t0 = time.monotonic()
                    async with BleakClient(addr, timeout=10) as client:
                        await client.write_gatt_char(uuid, b"", response=resp)
                    _dbg(f"Writable path OK: uuid={uuid}, response={resp}, took {(time.monotonic()-t0)*1000:.1f}ms")
                    return uuid, resp
                except Exception as e:
                    _dbg(f"Probe failed: uuid={uuid}, resp={resp}: {e}")
        return None

    async def _send_chunks(self, addr: str, uuid: str, resp: bool, blob: bytes):
        t0 = time.monotonic()
        total = len(blob)
        chunk = CHUNK_SIZE
        count = (total + chunk - 1) // chunk
        _dbg(f"send: total={total} bytes, chunks={count}, chunk={chunk}, resp={resp}, throttle_ms={THROTTLE_MS}")
        async with BleakClient(addr, timeout=20) as client:
            for i in range(0, total, chunk):
                await client.write_gatt_char(uuid, blob[i:i+chunk], response=resp)
                # If writing without response, push as fast as possible (optionally throttle if configured)
                if resp:
                    if THROTTLE_MS:
                        await asyncio.sleep(THROTTLE_MS / 1000.0)
                    else:
                        # Small yield to keep loop responsive
                        await asyncio.sleep(0)
            # Give the device a brief moment to process before disconnecting
            await asyncio.sleep(0.2 if not resp else 0.05)
        dt = (time.monotonic() - t0)
        rate = (total / dt) if dt > 0 else 0
        _dbg(f"send: completed in {dt*1000:.1f}ms ({rate/1024:.2f} KiB/s)")
