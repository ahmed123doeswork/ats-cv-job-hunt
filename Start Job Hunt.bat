@echo off
setlocal
title Job Hunt
cd /d "%~dp0"

echo.
echo   Job Hunt
echo   --------
echo.

rem ---- Find Python 3.10 or newer ------------------------------------------
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul && set "PY=python"
if not defined PY goto nopython

rem ---- First run: private Python environment + packages --------------------
if not exist ".venv\Scripts\python.exe" (
  echo   Setting up Job Hunt for the first time. This takes a minute or two...
  %PY% -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -c "import requests, bs4, docx, fpdf" >nul 2>nul
if errorlevel 1 (
  echo   Installing the parts Job Hunt needs...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt
  if errorlevel 1 goto fail
)

rem ---- Run --------------------------------------------------------------------
".venv\Scripts\python.exe" -m jobhunt.server
if errorlevel 1 (
  echo.
  echo   Job Hunt stopped with an error. The message above says why.
  pause
)
exit /b

:nopython
echo   Job Hunt needs Python 3.10 or newer, and it isn't installed yet.
echo.
where winget >nul 2>nul
if errorlevel 1 goto manual
choice /c YN /m "  Install Python now (about 30 MB)"
if errorlevel 2 goto manual
winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto manual
echo.
echo   Python is installed. Close this window and double-click "Start Job Hunt.bat" again.
pause
exit /b

:manual
echo.
echo   1. The Python download page will open. Download and run the installer.
echo   2. On the first screen, tick "Add python.exe to PATH", then click Install Now.
echo   3. Double-click "Start Job Hunt.bat" again.
start "" "https://www.python.org/downloads/"
pause
exit /b 1

:fail
echo.
echo   Setup didn't finish. Check your internet connection and try again.
echo   If it keeps failing, delete the ".venv" folder next to this file and retry.
pause
exit /b 1
