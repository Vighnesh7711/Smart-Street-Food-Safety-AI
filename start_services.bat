@echo off
echo Starting Smart Street Food Safety AI Services...

echo Starting Backend (FastAPI)...
start "Backend (FastAPI)" cmd /k "cd backend && .\venv\Scripts\activate && uvicorn app.main:app --reload"

echo Starting Frontend (Next.js)...
start "Frontend (Next.js)" cmd /k "cd frontend && npm run dev"

echo Both services are starting up in separate windows.
echo Keep those windows open while developing.
pause
