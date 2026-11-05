@echo off
title Gestionale Officina
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py app.py
  goto fine
)
where python >nul 2>nul
if %errorlevel%==0 (
  python app.py
  goto fine
)
echo Python non trovato.
echo Installalo da https://www.python.org/downloads/
echo e durante l'installazione spunta "Add Python to PATH".
:fine
pause
