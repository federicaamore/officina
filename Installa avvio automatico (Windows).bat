@echo off
title Installa avvio automatico - Gestionale Officina
cd /d "%~dp0"
setlocal

rem --- trova pythonw (Python senza finestra) ---
set "PYW="
for /f "delims=" %%i in ('where pyw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW for /f "delims=" %%i in ('where pythonw 2^>nul') do if not defined PYW set "PYW=%%i"
if not defined PYW (
  echo Python non trovato. Installalo da https://www.python.org/downloads/
  echo e durante l'installazione spunta "Add Python to PATH".
  pause
  exit /b 1
)

set "CARTELLA=%~dp0"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

rem --- 1. avvio automatico all'accensione, senza finestra ---
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%STARTUP%\Gestionale Officina.lnk');" ^
  "$s.TargetPath='%PYW%'; $s.Arguments='\"%CARTELLA%app.py\" --silenzioso';" ^
  "$s.WorkingDirectory='%CARTELLA%'; $s.WindowStyle=7; $s.Save()"

rem --- 2. icona sul desktop che apre il gestionale (e lo avvia se fosse spento) ---
powershell -NoProfile -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut(\"$d\Gestionale Officina.lnk\");" ^
  "$s.TargetPath='%PYW%'; $s.Arguments='\"%CARTELLA%app.py\"';" ^
  "$s.WorkingDirectory='%CARTELLA%'; $s.IconLocation='%SystemRoot%\System32\shell32.dll,165'; $s.Save()"

rem --- 3. lo avvio subito ---
start "" "%PYW%" "%CARTELLA%app.py"

echo.
echo Fatto!
echo  - Il gestionale ora parte da solo quando accendi il PC (senza finestre).
echo  - Sul desktop c'e' l'icona "Gestionale Officina" per aprirlo.
echo  - Indirizzo fisso, salvabile nei preferiti: http://127.0.0.1:8765
echo.
echo Per togliere l'avvio automatico usa "Rimuovi avvio automatico (Windows).bat".
pause
