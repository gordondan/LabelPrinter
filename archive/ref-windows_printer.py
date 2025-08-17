"""
windows_printer.py
-----------------
Contains all Windows-specific printer logic extracted from pi-label-printer.py.
"""

try:
    from PIL import ImageWin
    import win32print
    import win32ui
    import win32con
    WIN_AVAILABLE = True
except ImportError:
    WIN_AVAILABLE = False


def list_printers():
    """List available printers on Windows."""
    if not WIN_AVAILABLE:
        print("Windows printer libraries not available.")
        return []
    printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
    for i, printer in enumerate(printers):
        print(f"{i+1}: {printer[2]}")
    return printers

# Add more Windows-specific functions here as needed, e.g.,
# - print_image_win(...)
# - get_windows_device_caps(...)
# - any other win32print/win32ui logic
