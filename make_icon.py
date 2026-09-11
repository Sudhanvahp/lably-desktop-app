"""Writes assets/lably.ico from the drawn app mark, for the exe and the window.

Run once after changing the logo in app/ui/icons.py:  python make_icon.py
The .ico is committed so a build never depends on this script having run.
"""
import os
import sys

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SIZES = (16, 24, 32, 48, 64, 128, 256)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "lably.ico")


def main() -> None:
    QGuiApplication(sys.argv)
    from app.ui.icons import logo_pixmap

    # Qt has no ICO writer, so the container is assembled by hand: a header,
    # one directory entry per size, then each image as a PNG (allowed since
    # Vista and what Windows itself uses for the 256px slot).
    pngs = []
    for size in SIZES:
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        logo_pixmap(size).save(buf, "PNG")
        pngs.append((size, bytes(buf.data())))

    header = (0).to_bytes(2, "little") + (1).to_bytes(2, "little") + len(pngs).to_bytes(2, "little")
    offset = len(header) + 16 * len(pngs)
    entries, blobs = [], []
    for size, data in pngs:
        dim = 0 if size >= 256 else size
        entries.append(bytes([dim, dim, 0, 0]) + (1).to_bytes(2, "little")
                       + (32).to_bytes(2, "little") + len(data).to_bytes(4, "little")
                       + offset.to_bytes(4, "little"))
        blobs.append(data)
        offset += len(data)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as fh:
        fh.write(header + b"".join(entries) + b"".join(blobs))
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
