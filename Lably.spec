# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build recipe for Lably.

Produces ONE file - Lably.exe - so it can be sent straight over WhatsApp with
no zipping. The trade-off is startup: a one-file build unpacks itself into a
temp folder on every launch, so first paint takes a few seconds.

Only the Qt modules the app actually uses are kept. PySide6 ships a great deal
the app never touches (WebEngine, Quick, 3D, multimedia, SQL drivers) and
excluding it roughly thirds the size.
"""

excluded_qt = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtNetworkAuth", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtWebSockets",
    "PySide6.QtWebChannel", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
]

excluded_other = [
    "tkinter", "unittest", "pydoc", "doctest", "pytest", "numpy", "pandas",
    "matplotlib", "PIL", "setuptools", "pip",
]


a = Analysis(
    ["entry.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_qt + excluded_other,
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Lably",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # Deliberately off. UPX-packing an exe is one of the strongest heuristic
    # signals antivirus engines have: self-extracting compressed code is what
    # droppers look like, so a packed build gets flagged far more often than an
    # unpacked one. UPX is not on this machine's PATH today, which means the
    # setting is currently doing nothing anyway - pinning it False stops a build
    # on some other machine from silently becoming a packed one.
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window behind the app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/lably.ico",
    # Publisher / description shown in Properties, SmartScreen and Task Manager.
    version="version_info.py",
)
