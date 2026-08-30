@echo off
REM Windows Task Scheduler runs this every 30 minutes.
REM cd to project root first so `-m src...` module imports and .env loading work.
cd /d "%~dp0.."
if not exist logs mkdir logs
"C:\Users\JIYOON\.pyenv\pyenv-win\versions\3.11.9\python.exe" -m src.collectors.foot_traffic.collect >> logs\foot_traffic.log 2>&1
