@echo off
setlocal
echo =========================================
echo Building Facturar App Executable
echo =========================================

:: 1. Check if Python is available
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in the PATH.
    echo Please install Python to build the executable.
    pause
    exit /b 1
)

:: 2. Install PyInstaller if not present
pyinstaller --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo PyInstaller not found. Installing PyInstaller via pip...
    pip install pyinstaller
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to install PyInstaller. Please check your pip configuration.
        pause
        exit /b 1
    )
)

:: 3. Run PyInstaller
echo.
echo Running PyInstaller...
:: Adjust --add-data if you have specific templates, icons or images.
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "Facturar" ^
    --hidden-import pandas ^
    --hidden-import openpyxl ^
    --hidden-import csv ^
    --clean ^
    facturar_app.py

:: 4. Check result
if %ERRORLEVEL% EQU 0 (
    echo.
    echo =========================================
    echo SUCCESS: Build completed successfully!
    echo Your executable is located in: %CD%\dist\Facturar.exe
    echo =========================================
) else (
    echo.
    echo =========================================
    echo ERROR: Build failed. Check the logs above.
    echo =========================================
)

:: 5. Pause at the end
pause
endlocal
