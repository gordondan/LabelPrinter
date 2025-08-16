#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Find a Munbyn/Beeprt RW402B over BLE with Bleak.
- Scans for devices whose name contains "rw402b", "munbyn", or "beeprt"
- Prints MAC, RSSI (if available), and name
- Optional: probe GATT to see if common write/notify UUIDs are present

Usage:
  ./find_rw402b.py                 # quick 4s scan
  ./find_rw402b.py --timeout 8     # longer scan
  ./find_rw402b.py --probe         # also probe strongest candidate
  ./find_rw402b.py --addr AA:BB:CC:DD:EE:FF --probe   # skip scan; probe specific MAC
"""

import asyncio
import argparse
from typing import Optional, Tuple, List

from bleak import BleakScanner, BleakClient
from bleak.backends.device import BLEDevice

# Common RW402B write/notify candidates
WRITE_CANDIDATES = [
    "49535343-8841-43f4-a8d4-ecbe34729bb3",  # SILABS RX (write)
    "0000fff2-0000-1000-8000-00805f9b34fb",  # FFF2 (write)
]
NOTIFY_CANDIDATES = [
    "49535343-1e4d-4bd9-ba61-23c647249616",  # SILABS TX (notify)
    "0000fff1-0000-1000-8000-00805f9b34fb",  # FFF1 (notify)
]

def looks_like_rw402b(name: Optional[str]) -> bool:
    if not name:
        return False
    n = name.lower()
    return ("rw402b" in n) or ("munbyn" in n) or ("beeprt" in n)

def get_rssi(dev: BLEDevice) -> Optional[int]:
    """Try to obtain RSSI across Bleak/BlueZ versions."""
    # 1) Some versions expose BLEDevice.rssi directly
    rssi = getattr(dev, "rssi", None)
    if isinstance(rssi, int):
        return rssi

    # 2) Sometimes in dev.details as dicts
    det = getattr(dev, "details", None)
    if isinstance(det, dict):
        # BlueZ often nests under "props" -> "RSSI"
        props = det.get("props") if isinstance(det.get("props"), dict) else None
        if props and isinstance(props.get("RSSI"), int):
            return props["RSSI"]
        # direct key
        if isinstance(det.get("RSSI"), int):
            return det["RSSI"]

    # 3) Some backends use advertised_data
    adv = getattr(dev, "advertisement_data", None)
    if adv is not None:
        adv_rssi = getattr(adv, "rssi", None)
        if isinstance(adv_rssi, int):
            return adv_rssi

    return None

async def scan(timeout: float) -> List[Tuple[BLEDevice, int]]:
    print(f"Scanning for {timeout:.1f}s…")
    devices = await BleakScanner.discover(timeout=timeout)
    hits: List[Tuple[BLEDevice, int]] = []

    for d in devices:
        rssi_val = get_rssi(d)
        rssi_str = f"{rssi_val:4d}" if isinstance(rssi_val, int) else "   ?"
        tag = " <- likely RW402B" if looks_like_rw402b(d.name) else ""
        print(f"{d.address:17s}  RSSI={rssi_str}  Name={d.name}{tag}")
        if looks_like_rw402b(d.name):
            hits.append((d, rssi_val if isinstance(rssi_val, int) else -999))
    return hits

async def probe_characteristics(addr: str) -> bool:
    print(f"\nProbing GATT on {addr} …")
    try:
        async with BleakClient(addr, timeout=10) as client:
            svcs = await client.get_services()
            found_write = []
            found_notify = []
            for s in svcs:
                for c in s.characteristics:
                    props = set(c.properties or [])
                    cu = c.uuid.lower()
                    if cu in [u.lower() for u in WRITE_CANDIDATES] and (
                        "write" in props or "write-without-response" in props
                    ):
                        found_write.append((c.uuid, sorted(props)))
                    if cu in [u.lower() for u in NOTIFY_CANDIDATES] and ("notify" in props):
                        found_notify.append((c.uuid, sorted(props)))

            if not found_write:
                print("No expected WRITE characteristics found. (We can still try both candidates when printing.)")
            else:
                print("Write characteristic(s) found:")
                for u, p in found_write:
                    print(f"  {u}  props={p}")

            if found_notify:
                print("Notify characteristic(s) found:")
                for u, p in found_notify:
                    print(f"  {u}  props={p}")
            else:
                print("No expected NOTIFY characteristics found (optional).")

            return True
    except Exception as e:
        print(f"Probe failed: {e}")
        return False

async def main():
    ap = argparse.ArgumentParser(description="Find Munbyn RW402B via BLE (Bleak).")
    ap.add_argument("--timeout", type=float, default=4.0, help="Scan time in seconds (default: 4.0)")
    ap.add_argument("--probe", action="store_true", help="After scan, probe the strongest RW402B hit for write/notify")
    ap.add_argument("--addr", help="Skip scan and directly probe this MAC")
    args = ap.parse_args()

    if args.addr:
        await probe_characteristics(args.addr)
        return

    hits = await scan(args.timeout)
    if not hits:
        print("\nNo obvious RW402B/Munbyn devices found.")
        print("Tips: increase --timeout, press Feed to wake the printer, move closer, or ensure no phone/app is connected.")
        return

    best_dev, best_rssi = max(hits, key=lambda t: t[1])
    rssi_str = "?" if best_rssi == -999 else str(best_rssi)
    print(f"\nLikely target: {best_dev.address}  (Name={best_dev.name}, RSSI={rssi_str})")

    if args.probe:
        await probe_characteristics(best_dev.address)

if __name__ == "__main__":
    asyncio.run(main())
