# Label Printer Web Server Startup Script
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Starting Label Printer Web Server" -ForegroundColor Cyan  
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "The web interface will be available at:" -ForegroundColor Green
Write-Host "  Local:   http://127.0.0.1:5000" -ForegroundColor Yellow
Write-Host "  Network: http://$env:COMPUTERNAME:5000" -ForegroundColor Yellow
Write-Host ""
Write-Host "Features:" -ForegroundColor Green
Write-Host "  - Quick Print with smart font sizing" -ForegroundColor White
Write-Host "  - Template management" -ForegroundColor White
Write-Host "  - Activity logs with real-time updates" -ForegroundColor White
Write-Host "  - Settings and printer configuration" -ForegroundColor White
Write-Host "  - Mobile-friendly responsive design" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Change to the server directory
Set-Location -Path "$PSScriptRoot\Server"

# Start the Python server
try {
    python label_server.py
} catch {
    Write-Host "Error starting server: $_" -ForegroundColor Red
    Write-Host "Make sure Python is installed and in your PATH" -ForegroundColor Yellow
    Write-Host "Also ensure Flask is installed: pip install flask" -ForegroundColor Yellow
}

# Pause to keep window open if there was an error
Read-Host "Press Enter to continue..."