@echo off
title Login to DeepSeek Web
cd /d "%~dp0"

echo ====================================================================
echo                LOGIN TO DEEPSEEK WEB (ONE-TIME SETUP)
echo ====================================================================
echo.
echo Opening Google Chrome for DeepSeek login...
echo.
echo 1. Login to your DeepSeek account in the browser window that opens.
echo 2. Once logged in, simply close that Chrome window.
echo.

.venv\Scripts\python.exe -c "from deepseek_web import open_login_window; open_login_window()"

echo.
echo Setup complete! Your login session is now saved permanently.
pause
