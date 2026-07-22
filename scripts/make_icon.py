"""Generate assets/paios.ico — the product icon, stdlib only.

    python scripts/make_icon.py

The icon is drawn programmatically (no Pillow, no font files): the
PAIOS dark surface with the accent-blue "P" mark, matching the GUI
theme palette (frontend/desktop/paios_gui/theme.py). Emits an .ico
containing PNG-compressed images at 16/24/32/48/64/256 px.
"""

import struct
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TARGET = REPO_ROOT / "assets" / "paios.ico"

BACKGROUND = (0x14, 0x16, 0x1A)  # theme BACKGROUND
ACCENT = (0x4C, 0x9B, 0xE8)  # theme ACCENT
TEXT = (0xD7, 0xDA, 0xE0)  # theme TEXT


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def encode_png(size: int, pixels: list[tuple[int, int, int, int]]) -> bytes:
    """Minimal RGBA PNG encoder (filter 0 on every scanline)."""
    raw = bytearray()
    for y in range(size):
        raw.append(0)
        for x in range(size):
            raw.extend(pixels[y * size + x])
    header = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _png_chunk(b"IEND", b"")
    )


def draw(size: int) -> list[tuple[int, int, int, int]]:
    """The mark: rounded dark tile, accent 'P' built from bars."""
    pixels = []
    radius = size * 0.18
    # 'P' geometry in unit coordinates.
    stem_x = (0.30, 0.44)
    stem_y = (0.22, 0.80)
    loop_outer_x = (0.30, 0.74)
    loop_outer_y = (0.22, 0.58)
    loop_inner_x = (0.44, 0.60)
    loop_inner_y = (0.34, 0.46)

    def inside_tile(px: float, py: float) -> bool:
        cx = min(max(px, radius), size - radius)
        cy = min(max(py, radius), size - radius)
        return (px - cx) ** 2 + (py - cy) ** 2 <= radius**2 or (
            radius <= px <= size - radius or radius <= py <= size - radius
        )

    def in_box(ux: float, uy: float, bx: tuple, by: tuple) -> bool:
        return bx[0] <= ux <= bx[1] and by[0] <= uy <= by[1]

    for y in range(size):
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            ux, uy = px / size, py / size
            if not inside_tile(px, py):
                pixels.append((0, 0, 0, 0))
                continue
            is_p = (
                in_box(ux, uy, stem_x, stem_y)
                or (
                    in_box(ux, uy, loop_outer_x, loop_outer_y)
                    and not in_box(ux, uy, loop_inner_x, loop_inner_y)
                )
            )
            color = ACCENT if is_p else BACKGROUND
            pixels.append((*color, 255))
    return pixels


def build_ico(sizes: tuple[int, ...]) -> bytes:
    images = [encode_png(size, draw(size)) for size in sizes]
    directory = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for size, image in zip(sizes, images):
        entries += struct.pack(
            "<BBBBHHII",
            size if size < 256 else 0,
            size if size < 256 else 0,
            0, 0, 1, 32, len(image), offset,
        )
        offset += len(image)
    return directory + entries + b"".join(images)


def main() -> int:
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_bytes(build_ico((16, 24, 32, 48, 64, 256)))
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
