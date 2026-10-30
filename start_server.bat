@echo off
cd /d "%~dp0"
echo Our Snowboard server starting. Closing this window stops the server.
echo Address: http://localhost:8790
python -m uvicorn server.main:app --host 127.0.0.1 --port 8790
pause
