@echo off
echo ============================================================
echo Starting Label Printer Web Server
echo ============================================================
echo.
echo The web interface will be available at:
echo   Local:   http://127.0.0.1:5000
echo   Network: http://%COMPUTERNAME%:5000
echo.
echo Press Ctrl+C to stop the server
echo ============================================================
echo.

cd /d "%~dp0\Server"
python label_server.py

pause