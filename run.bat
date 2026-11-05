@echo off
rem Run from sources without console window. Prebuilt version: SpiderPal.exe
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0spider.py"
