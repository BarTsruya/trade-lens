@echo off
setlocal

set "DIR=%~dp0"
set "VENV=%DIR%.venv"
set "PYTHON=%VENV%\Scripts\python.exe"
set "STREAMLIT=%VENV%\Scripts\streamlit.exe"

:: Make trade_lens importable without installing it as a package
set "PYTHONPATH=%DIR%"

echo.
echo  Trade Lens
echo  ----------

:: First-time setup: create venv and install dependencies
if not exist "%PYTHON%" (
    echo  First run: setting up environment, this takes a minute...
    echo.
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo  ERROR: Python not found.
        echo  Please install Python 3.10+ from https://www.python.org/downloads/
        echo.
        pause
        exit /b 1
    )
    "%VENV%\Scripts\pip" install -r "%DIR%requirements.txt" --quiet
    if errorlevel 1 (
        echo.
        echo  ERROR: Failed to install dependencies.
        echo  Check your internet connection and try again.
        echo.
        pause
        exit /b 1
    )
    echo  Setup complete.
    echo.
)

echo  Starting app...
echo  Open your browser at http://localhost:8501
echo  Press Ctrl+C here to stop.
echo.

"%STREAMLIT%" run "%DIR%app_streamlit\Home.py" --server.headless false

endlocal
