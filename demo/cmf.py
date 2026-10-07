import struct
import zlib

SIGNATURE = 0x66666D63
VERSION = 1
SECTION_DATA, SECTION_GPU_BUFFER = 0, 1
USAGE_POSITION, USAGE_NORMAL, USAGE_TEXCOORD = 0, 1, 4
TYPE_FLOAT32 = 0
TOPOLOGY_TRIANGLE_LIST = 0
NO_SKELETON = 0xFF
FLT_MAX = 3.4028234663852886e38

DATA_SIZE, MESH_SIZE, LOD_SIZE, AREA_SIZE = 48, 216, 72, 64
VERTEX_LAYOUT = [(USAGE_POSITION, 0, 3), (USAGE_NORMAL, 0, 3), (USAGE_TEXCOORD, 0, 2)]
UV1_ELEMENT = (USAGE_TEXCOORD, 1, 2)


def align8(n):
    return (n + 7) & ~7


class DataSection:
    def __init__(self):
        self.buf = bytearray()

    def alloc(self, size):
        offset = align8(len(self.buf))
        self.buf += b"\0" * (offset - len(self.buf) + size)
        return offset

    def put(self, offset, fmt, *values):
        struct.pack_into(fmt, self.buf, offset, *values)

    def span(self, field, target, size):
        # Spans store a self-relative offset tagged with the low bit, plus a byte size.
        self.put(field, "<qQ", ((target - field) | 1) if size else 0, size)

    def blob(self, field, data):
        if not data:
            self.span(field, 0, 0)
            return
        offset = self.alloc(len(data))
        self.buf[offset:offset + len(data)] = data
        self.span(field, offset, len(data))


def bounds(positions):
    lo = [min(p[k] for p in positions) for k in range(3)]
    hi = [max(p[k] for p in positions) for k in range(3)]
    return lo + hi


def write_mesh(path, positions, normals, uvs, indices, name="mesh", uv1=None, extra_bounds=()):
    layout = VERTEX_LAYOUT + ([UV1_ELEMENT] if uv1 is not None else [])
    stride = 4 * sum(count for _, _, count in layout)
    if uv1 is None:
        vertex_buffer = b"".join(struct.pack("<8f", *p, *n, *t) for p, n, t in zip(positions, normals, uvs))
    else:
        vertex_buffer = b"".join(struct.pack("<10f", *p, *n, *t, *t1)
                                 for p, n, t, t1 in zip(positions, normals, uvs, uv1))
    small = len(positions) <= 0xFFFF
    index_stride = 2 if small else 4
    index_buffer = struct.pack("<%d%s" % (len(indices), "H" if small else "I"), *indices)
    box = bounds(list(positions) + [tuple(p) for p in extra_bounds])

    d = DataSection()
    data = d.alloc(DATA_SIZE)
    mesh = d.alloc(MESH_SIZE)
    d.span(data, mesh, MESH_SIZE)
    d.span(data + 16, 0, 0)
    d.span(data + 32, 0, 0)

    d.blob(mesh + 0, name.encode())
    decl, offset = b"", 0
    for usage, usage_index, count in layout:
        decl += struct.pack("<4BI", usage, usage_index, TYPE_FLOAT32, count, offset)
        offset += 4 * count
    d.blob(mesh + 16, decl)

    lod = d.alloc(LOD_SIZE)
    d.span(mesh + 32, lod, LOD_SIZE)
    d.put(lod + 0, "<4I", 1, 0, len(vertex_buffer), stride)
    d.put(lod + 16, "<4I", 2, 0, len(index_buffer), index_stride)
    d.blob(lod + 32, struct.pack("<2I", 0, len(indices) // 3))
    d.span(lod + 48, 0, 0)
    d.put(lod + 64, "<I", 0xFFFFFFFF)

    area = d.alloc(AREA_SIZE)
    d.span(mesh + 48, area, AREA_SIZE)
    d.blob(area + 0, b"area0")
    d.put(area + 16, "<6f", *box)
    d.span(area + 40, 0, 0)

    for field in (64, 80, 96, 112, 152, 168):
        d.span(mesh + field, 0, 0)
    d.put(mesh + 128, "<6f", *box)
    d.put(mesh + 184, "<6f", FLT_MAX, FLT_MAX, FLT_MAX, -FLT_MAX, -FLT_MAX, -FLT_MAX)
    d.put(mesh + 208, "<2B", TOPOLOGY_TRIANGLE_LIST, NO_SKELETON)

    sections = [(SECTION_DATA, bytes(d.buf), 0),
                (SECTION_GPU_BUFFER, vertex_buffer, stride),
                (SECTION_GPU_BUFFER, index_buffer, index_stride)]
    header_size = 32 + 16 * len(sections)
    out = bytearray(header_size)
    struct.pack_into("<4I", out, 0, SIGNATURE, VERSION, header_size, 0)
    struct.pack_into("<qQ", out, 16, 17, 16 * len(sections))
    for i, (kind, payload, alignment) in enumerate(sections):
        out += b"\0" * (align8(len(out)) - len(out))
        struct.pack_into("<3IHBB", out, 32 + 16 * i, len(out), len(payload), len(payload), alignment, kind, 0)
        out += payload
    struct.pack_into("<I", out, 12, zlib.crc32(out[16:]) & 0xFFFFFFFF)
    with open(path, "wb") as f:
        f.write(out)
