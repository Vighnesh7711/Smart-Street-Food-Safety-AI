@echo off
echo Stopping Smart Street Food Safety AI Services...

echo Closing service windows...
taskkill /FI "WINDOWTITLE eq Backend (FastAPI)*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Frontend (Next.js)*" /T /F >nul 2>&1

echo Cleaning up any lingering processes on ports 3000 and 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3000') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do taskkill /F /PID %%a >nul 2>&1

echo Services stopped successfully.
pause
