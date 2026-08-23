@echo off
rem Launch Character Check with no console window.
rem
rem Why this file exists: `python` on a stock Windows install is often the
rem Microsoft Store alias, which ALWAYS creates a console window and then
rem re-launches the real interpreter as a child. pythonw.exe is the
rem console-less twin, and this finds it without relying on .py/.pyw file
rem associations -- which are frequently not registered at all.

setlocal
set "APP=%~dp0main.pyw"

rem 1. The launcher that ships with python.org installs.
where pyw.exe >nul 2>&1 && (start "" pyw.exe "%APP%" & goto :eof)

rem 2. pythonw.exe next to whichever python is on PATH.
for /f "delims=" %%P in ('where python 2^>nul') do (
    if exist "%%~dpPpythonw.exe" (start "" "%%~dpPpythonw.exe" "%APP%" & goto :eof)
)

rem 3. Last resort: pythonw on PATH in its own right.
where pythonw.exe >nul 2>&1 && (start "" pythonw.exe "%APP%" & goto :eof)

echo Python not found. Install Python 3.11+ from python.org and try again.
pause
