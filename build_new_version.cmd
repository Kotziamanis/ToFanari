@echo off
cd /d "%~dp0"
python build_new_version.py
if "%1"=="" pause
