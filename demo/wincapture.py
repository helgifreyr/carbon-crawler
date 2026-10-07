import ctypes
import struct
from ctypes import wintypes

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
PW_CLIENTONLY = 0x1
PW_RENDERFULLCONTENT = 0x2


def capture_client_bmp(hwnd, path):
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    width, height = rect.right - rect.left, rect.bottom - rect.top
    screen_dc = user32.GetDC(0)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)
    user32.PrintWindow(hwnd, mem_dc, PW_CLIENTONLY | PW_RENDERFULLCONTENT)

    header = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 24, 0, 0, 0, 0, 0, 0)
    stride = (width * 3 + 3) & ~3
    pixels = ctypes.create_string_buffer(stride * height)
    gdi32.GetDIBits(mem_dc, bitmap, 0, height, pixels, ctypes.c_char_p(header), 0)

    with open(path, "wb") as f:
        f.write(b"BM" + struct.pack("<IHHI", 14 + 40 + len(pixels), 0, 0, 14 + 40))
        f.write(header)
        f.write(pixels.raw)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(0, screen_dc)
