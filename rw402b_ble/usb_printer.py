# USB printer implementation for RW402B (TSPL via pyusb)
from __future__ import annotations

import math
import time
import os
from typing import Optional, Tuple

DEBUG = os.getenv('RW402B_DEBUG', '1').lower() in ('1', 'true', 'yes', 'y')

def _dbg(msg: str):
    if DEBUG:
        print(f"[rw402b-usb] {msg}")

def _mm_to_dots(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / 25.4))

def _pil_to_tspl_bitmap(img, label_w_mm: float, label_h_mm: float, dpi: int, invert: bool) -> Tuple[bytes, int, int]:
    """Convert a PIL.Image to a TSPL BITMAP payload (packed 1bpp, MSB-first)."""
    from PIL import Image

    t0 = time.monotonic()
    label_w = _mm_to_dots(label_w_mm, dpi)
    label_h = _mm_to_dots(label_h_mm, dpi)

    im = img.convert("L")
    im = im.point(lambda p: 0 if p < 128 else 255, mode='1')

    w, h = im.size
    if w != label_w:
        new_h = int(round(h * (label_w / w)))
        im = im.resize((label_w, new_h), Image.NEAREST)

    if im.height > label_h:
        im = im.crop((0, 0, im.width, label_h))

    packed = bytearray()
    for y in range(im.height):
        byte = 0
        bitcount = 0
        for x in range(im.width):
            px = im.getpixel((x, y))
            bit = 1 if px == 0 else 0
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
    _dbg(f"bitmap: wb={width_bytes}, h={height}, invert={invert}, took={dt:.1f}ms")
    return packed, width_bytes, height


class RW402BUSBPrinter:
    """
    USB implementation for RW402B. Usage:
        p = RW402BUSBPrinter()
        p.print_pil_image(image, label_w_mm=76.2, label_h_mm=25.4, gap_mm=3)
    """

    # Munbyn RW402B USB IDs
    VENDOR_ID = 0x0d28
    PRODUCT_ID = 0xccdd

    def __init__(self, dpi: int = 203, invert: bool = True):
        self.dpi = dpi
        self.invert = invert
        self._dev = None
        self._ep_out = None

    def _connect(self):
        """Connect to the USB printer."""
        import usb.core
        import usb.util

        if self._dev is not None:
            return

        t0 = time.monotonic()
        dev = usb.core.find(idVendor=self.VENDOR_ID, idProduct=self.PRODUCT_ID)
        if dev is None:
            raise RuntimeError("RW402B USB printer not found")

        _dbg(f"Found USB printer in {(time.monotonic()-t0)*1000:.1f}ms")

        # Detach kernel driver if needed (Linux)
        try:
            if dev.is_kernel_driver_active(0):
                dev.detach_kernel_driver(0)
        except Exception:
            pass

        # Set configuration
        try:
            dev.set_configuration()
        except Exception:
            pass  # May already be configured

        # Get the printer interface (class 7)
        cfg = dev.get_active_configuration()
        intf = usb.util.find_descriptor(cfg, bInterfaceClass=7)
        if intf is None:
            raise RuntimeError("Printer interface not found")

        # Find the OUT endpoint
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        if ep_out is None:
            raise RuntimeError("OUT endpoint not found")

        self._dev = dev
        self._ep_out = ep_out
        _dbg(f"Connected to USB printer, endpoint 0x{ep_out.bEndpointAddress:02x}")

    def print_pil_image(self, img, label_w_mm: float, label_h_mm: float, gap_mm: float = 3.0,
                        density: int = 8, speed: int = 4, direction: int = 1,
                        x: int = 0, y: int = 0, mode: int = 0):
        """Print a PIL image to the label printer."""
        t_start = time.monotonic()

        self._connect()

        # Build TSPL payload
        t2 = time.monotonic()
        packed, wb, h = _pil_to_tspl_bitmap(img, label_w_mm, label_h_mm, self.dpi, self.invert)
        _dbg(f"bitmap conversion took {(time.monotonic()-t2)*1000:.1f}ms; payload={len(packed)} bytes")

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

        # Send to printer
        t3 = time.monotonic()
        bytes_sent = self._ep_out.write(blob)
        send_ms = (time.monotonic() - t3) * 1000.0
        total_ms = (time.monotonic() - t_start) * 1000.0

        _dbg(f"sent {bytes_sent} bytes in {send_ms:.1f}ms; total print took {total_ms:.1f}ms")

    def close(self):
        """Release the USB device."""
        if self._dev is not None:
            import usb.util
            usb.util.dispose_resources(self._dev)
            self._dev = None
            self._ep_out = None
