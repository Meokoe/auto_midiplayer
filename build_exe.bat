@echo off
chcp 65001 >nul
echo ========================================
echo   MIDI Player — Pack to EXE
echo ========================================
echo.

set PYTHON=e:\anacondaaaa\python.exe

echo [1/2] Cleaning old builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist "MIDI自动演奏.spec" del /q "MIDI自动演奏.spec"

echo [2/2] PyInstaller packaging...
"%PYTHON%" -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name="MIDI自动演奏" ^
    --add-data="e:/anacondaaaa/Lib/site-packages/customtkinter;customtkinter" ^
    --hidden-import=mido ^
    --hidden-import=customtkinter ^
    --hidden-import=darkdetect ^
    --collect-submodules=pynput ^
    main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo   Build success!
    echo   Output: dist\MIDI自动演奏.exe
    echo ========================================
) else (
    echo.
    echo Build failed, check error messages.
)

pause
