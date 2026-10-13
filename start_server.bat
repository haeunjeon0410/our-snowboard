@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Our Snowboard 변환 서버를 시작합니다. (이 창을 닫으면 꺼집니다)
echo 주소: http://localhost:8790
python -m uvicorn server.main:app --host 127.0.0.1 --port 8790
pause
