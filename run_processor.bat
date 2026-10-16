@echo off
REM Convenience script to run the processor on Windows

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Activate virtual environment if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM Run the processor
python processor.py --config config/gmail_config.json

pause
