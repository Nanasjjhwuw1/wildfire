@echo off
REM ===== Wildfire MVP launcher (double-click this file) =====
cd /d "%~dp0"

echo Starting BACKEND (FastAPI :8000)...
start "wildfire-backend" cmd /k ".venv\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000"

echo Starting FRONTEND (Vite :5173)...
start "wildfire-frontend" cmd /k "npm --prefix frontend run dev"

echo Waiting a few seconds for servers to boot...
timeout /t 7 /nobreak >nul

echo Opening the app in your browser...
start "" "http://localhost:5173"

echo.
echo ==========================================================
echo  App:     http://localhost:5173
echo  API:     http://localhost:8000/api/area
echo  Two windows opened (backend + frontend).
echo  To STOP the app: close those two windows.
echo ==========================================================
echo You can close THIS window.
pause
