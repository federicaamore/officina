@echo off
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Gestionale Officina.lnk" 2>nul
taskkill /f /fi "WINDOWTITLE eq Gestionale Officina*" >nul 2>nul
for /f "tokens=5" %%p in ('netstat -ano ^| findstr "127.0.0.1:8765" ^| findstr LISTENING') do taskkill /f /pid %%p >nul 2>nul
echo Avvio automatico rimosso e gestionale chiuso. I dati non sono stati toccati.
pause
