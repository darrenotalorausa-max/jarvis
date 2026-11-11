@echo off
rem Doomsday - lanzador para Windows. Doble clic para iniciar. Abre Doomsday en su propia ventana (puerto 8766, datos en doomsday_home).
setlocal EnableExtensions
cd /d "%~dp0"
title Doomsday

if not exist ".venv\Scripts\python.exe" goto setup
if not exist "frontend\dist-doomsday\doomsday.html" goto setup
goto run

:setup
call "%~dp0SETUP_JARVIS.cmd"
if errorlevel 1 goto setup_failed

:run
cd backend
"..\.venv\Scripts\python.exe" -m doomsday.launch --app %*
set "CODE=%ERRORLEVEL%"
cd ..
if "%CODE%"=="0" goto end
echo.
echo Doomsday se detuvo con codigo %CODE%. Revisa los mensajes de arriba y los archivos doomsday_home\logs\api.log y doomsday_home\logs\worker.out.log
pause
goto end

:setup_failed
echo.
echo No se pudo preparar Doomsday. Sigue las indicaciones de arriba y vuelve a intentarlo.
pause
set "CODE=1"

:end
endlocal & exit /b %CODE%
