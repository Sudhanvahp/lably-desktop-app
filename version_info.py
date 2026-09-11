# -*- coding: utf-8 -*-
# Windows version resource stamped onto Lably.exe by PyInstaller (see Lably.spec).
#
# This is what Explorer shows under Properties > Details, what SmartScreen and
# the UAC prompt print as the publisher line when the exe is first run, and
# what Task Manager lists the process as. It is the exe's own way of saying
# who developed it, before the app has even started.
#
# Keep the strings in step with app/branding.py.
VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 2, 0, 0),
        prodvers=(1, 2, 0, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable("040904B0", [
                StringStruct("CompanyName", "ACHUTHTECH"),
                StringStruct("FileDescription", "Lably - Blood Report Manager - Developed by ACHUTHTECH"),
                StringStruct("FileVersion", "1.2.0.0"),
                StringStruct("InternalName", "Lably"),
                StringStruct("LegalCopyright", "Copyright (c) ACHUTHTECH. Made in India."),
                StringStruct("OriginalFilename", "Lably.exe"),
                StringStruct("ProductName", "Lably by ACHUTHTECH"),
                StringStruct("ProductVersion", "1.2.0.0"),
                StringStruct("Comments", "Developed by ACHUTHTECH"),
            ])
        ]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
