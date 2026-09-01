"""PyInstaller entry point.

PyInstaller cannot start a package with `python -m app`, so it needs a plain
script that calls the same main().
"""
import multiprocessing
import sys

from app.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
