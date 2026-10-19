@echo off
setlocal
cd /d "%~dp0"
set "OUT=%USERPROFILE%\Desktop\Job Hunt.zip"
echo.
echo   Packing Job Hunt for someone else, without your CV, settings or saved jobs...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$tmp = Join-Path $env:TEMP ('jobhunt-share-' + [guid]::NewGuid()); $dst = Join-Path $tmp 'Job Hunt';" ^
  "robocopy . $dst /E /XD .venv data assets __pycache__ .git /XF *.pyc | Out-Null;" ^
  "Compress-Archive -Path $dst -DestinationPath $env:OUT -Force; Remove-Item $tmp -Recurse -Force"
if errorlevel 1 (
  echo   Couldn't create the zip.
) else (
  echo   Done: "%OUT%"
  echo   Send that file. The other person unzips it and double-clicks "Start Job Hunt.bat".
)
echo.
pause
