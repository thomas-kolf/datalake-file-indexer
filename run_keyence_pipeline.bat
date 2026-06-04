@echo off
setlocal

cd /d "C:\Users\uiv51287\datalake-file-indexer"

python "C:\Users\uiv51287\datalake-file-indexer\keyence_orchestrator.py"

exit /b %ERRORLEVEL%