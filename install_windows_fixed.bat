@echo off
chcp 65001 >nul
REM Roben Trading AI Bot - Windows Installer

echo.
echo ========================================
echo    Roben Trading AI Bot Installer
echo ========================================
echo.

REM Check Python
echo [1/5] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.8+ from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo SUCCESS: Python found

REM Check pip
echo [2/5] Checking pip installation...
pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip not found!
    pause
    exit /b 1
)
echo SUCCESS: pip found

REM Create installation directory
set INSTALL_DIR=%USERPROFILE%\RobenTradingBot
echo [3/5] Creating installation directory: %INSTALL_DIR%
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

REM Copy files
echo [4/5] Copying system files...
if exist "src" xcopy /E /I /Y src "%INSTALL_DIR%"
if exist "config" xcopy /E /I /Y config "%INSTALL_DIR%"
if exist "docs" xcopy /E /I /Y docs "%INSTALL_DIR%"
if exist "*.py" copy /Y *.py "%INSTALL_DIR%"
if exist "*.env" copy /Y *.env "%INSTALL_DIR%"
if exist "*.json" copy /Y *.json "%INSTALL_DIR%"

REM Install requirements
echo [5/5] Installing required packages...
pip install python-dotenv flask flask-cors requests pandas numpy

REM Create startup script
echo Creating startup script...
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%%~dp0"
echo echo Starting Roben Trading AI Bot...
echo python roben_enhanced_trading_system.py
echo pause
) > "%INSTALL_DIR%\start_roben_bot.bat"

REM Create desktop shortcut
echo Creating desktop shortcut...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\Roben Trading AI Bot.lnk'); $Shortcut.TargetPath = '%INSTALL_DIR%\start_roben_bot.bat'; $Shortcut.WorkingDirectory = '%INSTALL_DIR%'; $Shortcut.Description = 'Roben Trading AI Bot'; $Shortcut.Save()"

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo Installation Directory: %INSTALL_DIR%
echo Desktop Shortcut: Created
echo.
echo Next Steps:
echo 1. Edit .env file and add your API keys
echo 2. Double-click desktop shortcut to start
echo 3. Open browser: http://localhost:8082
echo.
echo Support: support@robentrading.ai
echo.
echo WARNING: Start with small amounts for testing!
echo.
pause

