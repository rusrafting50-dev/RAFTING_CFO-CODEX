@echo off
cd /d "D:\Projects Claude Code\RAFTING_CFO"
echo [1/3] Git pull...
git pull origin main
echo [2/3] pip install...
pip install -r requirements.txt --quiet
echo [3/3] Start Flask...
start http://localhost:5003
python app.py
pause