@echo off
rem cmd.exe wrapper for lai.py - lets `lai` work in Command Prompt too
rem (cmd cannot run .ps1 files; double-clicking one opens an editor instead)
setlocal
set "HERE=%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python "%HERE%lai.py" %*
    exit /b
)
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%HERE%lai.py" %*
    exit /b
)
echo Python 3.9+ not found. Install it with: winget install Python.Python.3.12
exit /b 1
