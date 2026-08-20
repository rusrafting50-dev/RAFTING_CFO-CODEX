@echo off
set GIT_MERGE_AUTOEDIT=no
cd /d "%~dp0"
echo [1/3] Git pull...
git pull origin main
echo [2/3] pip install...
pip install -r requirements.txt --quiet
echo [3/3] Start Flask...
start http://localhost:5003
python app.py
pause
