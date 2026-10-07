import struct

import numpy as np

DXGI_R16G16B16A16_FLOAT = 10
DXGI_R32G32B32A32_FLOAT = 2
DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH, DDSD_PITCH, DDSD_PIXELFORMAT = 0x1, 0x2, 0x4, 0x8, 0x1000
DDPF_FOURCC = 0x4
DDSCAPS_TEXTURE = 0x1000
TEXTURE2D = 3


def write_rgba_float(path, pixels, half=True):
    """Uncompressed RGBA float DDS (DX10 header); pixels is (height, width, 4), row 0 is the top."""
    data = np.ascontiguousarray(pixels, dtype=np.float16 if half else np.float32)
    height, width, _ = data.shape
    pitch = width * 4 * data.itemsize
    header = struct.pack("<7I", 124, DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT,
                         height, width, pitch, 0, 1)
    header += b"\0" * 44
    header += struct.pack("<2I4s5I", 32, DDPF_FOURCC, b"DX10", 0, 0, 0, 0, 0)
    header += struct.pack("<5I", DDSCAPS_TEXTURE, 0, 0, 0, 0)
    dx10 = struct.pack("<5I", DXGI_R16G16B16A16_FLOAT if half else DXGI_R32G32B32A32_FLOAT, TEXTURE2D, 0, 1, 0)
    with open(path, "wb") as f:
        f.write(b"DDS " + header + dx10 + data.tobytes())
