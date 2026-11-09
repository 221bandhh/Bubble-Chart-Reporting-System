@echo off
setlocal
cd /d "%~dp0"
echo Step 1: Set Directory OK.
echo Step 2: Checking Python...
python --version >nul 2>&1
if not errorlevel 1 (
    set "RUN_CMD=python"
    goto RUN_SCRIPT
)
py --version >nul 2>&1
if not errorlevel 1 (
    set "RUN_CMD=py"
    goto RUN_SCRIPT
)
echo [ERROR] Python not found! Install Python 3 and dependencies first.
pause
exit /b 1

:RUN_SCRIPT
echo Found Python! Using command: %RUN_CMD%
echo Step 3: Running baobiao.py...
echo ========================================
%RUN_CMD% baobiao.py
set "APP_EXIT_CODE=%errorlevel%"
echo ========================================
echo [INFO] Script finished. Exit code: %APP_EXIT_CODE%
pause
exit /b %APP_EXIT_CODE%
