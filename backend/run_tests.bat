@echo off
echo Running test suite...
.venv\Scripts\pytest tests/ -v
pause
