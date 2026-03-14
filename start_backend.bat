@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=%CD%
python api_server.py
