"""Minimal PNG writing in pure Python."""
import struct
import zlib


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def palette_png(width, height, pixels, palette):
    """An RGBA PNG from one palette index per pixel (rows top first); palette is (r, g, b, a) colours."""
    colours = [bytes(c) for c in palette]
    rgba = b"".join(colours[p] for p in pixels)
    row = width * 4
    raw = b"".join(b"\x00" + rgba[y * row:(y + 1) * row] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw, 1)) + _chunk(b"IEND", b""))
