@echo off
rem Jarvis OS - lanzador para Windows. Doble clic para iniciar; Ctrl+C en esta ventana para detener.
setlocal EnableExtensions
cd /d "%~dp0"
title Jarvis OS

if not exist ".venv\Scripts\python.exe" goto setup
if not exist "frontend\dist\index.html" goto setup
goto run

:setup
call "%~dp0SETUP_JARVIS.cmd"
if errorlevel 1 goto setup_failed

:run
cd backend
"..\.venv\Scripts\python.exe" -m jarvis.launch
set "CODE=%ERRORLEVEL%"
cd ..
if "%CODE%"=="0" goto end
echo.
echo Jarvis se detuvo con codigo %CODE%. Revisa los mensajes de arriba y los archivos logs\api.log y logs\worker.out.log
pause
goto end

:setup_failed
echo.
echo No se pudo preparar Jarvis. Sigue las indicaciones de arriba y vuelve a intentarlo.
pause
set "CODE=1"

:end
endlocal & exit /b %CODE%
