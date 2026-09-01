@echo off
REM Builds Lably.exe as a single shareable file, straight onto the Desktop.
cd /d "%~dp0"
echo Building Lably.exe ... this takes a minute.
python -m PyInstaller --noconfirm --distpath "%USERPROFILE%\Desktop" Lably.spec
if errorlevel 1 (
  echo.
  echo BUILD FAILED
  pause
  exit /b 1
)
echo.
echo Done.  Lably.exe is on your Desktop - send that one file to anyone.
pause
