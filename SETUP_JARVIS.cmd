@echo off
rem Jarvis OS - preparacion idempotente para Windows.
rem No requiere administrador, no cambia politicas de PowerShell ni ajustes de seguridad.
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo === Jarvis OS: preparacion ===
echo.

set "PY="
py -3 scripts\check_python.py >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if defined PY goto have_python
python scripts\check_python.py >nul 2>nul
if not errorlevel 1 set "PY=python"
if defined PY goto have_python
echo [FALTA] Python 3.11 o superior.
echo         Instalalo desde https://www.python.org/downloads/  ^(marca "Add python.exe to PATH"^)
echo         o con:  winget install Python.Python.3.12
echo         Despues vuelve a ejecutar este archivo.
goto fail

:have_python
%PY% scripts\check_python.py
if exist ".venv\Scripts\python.exe" goto venv_ready
echo Creando el entorno de Python en .venv ...
%PY% -m venv .venv
if errorlevel 1 goto fail_venv

:venv_ready
echo Instalando dependencias de Python (versiones fijadas en backend\requirements.lock) ...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r backend\requirements.lock
if errorlevel 1 goto fail_pip

if /i "%~1"=="rebuild" goto need_frontend
if exist "frontend\dist\index.html" goto frontend_ready

:need_frontend
where node >nul 2>nul
if errorlevel 1 goto fail_node
node scripts\check_node.cjs
if errorlevel 1 goto fail_node
echo Instalando dependencias de la interfaz (frontend\package-lock.json) ...
pushd frontend
call npm ci --no-audit --no-fund
if errorlevel 1 goto fail_npm
echo Compilando la interfaz ...
call npm run build
if errorlevel 1 goto fail_npm
popd

:frontend_ready
where ffmpeg >nul 2>nul
if errorlevel 1 goto warn_ffmpeg
where ffprobe >nul 2>nul
if errorlevel 1 goto warn_ffmpeg
echo FFmpeg encontrado.
goto done

:warn_ffmpeg
echo.
echo [AVISO] FFmpeg no esta en el PATH. Jarvis funciona, pero el Editor audiovisual no podra leer ni exportar video.
echo         Instalalo con:  winget install Gyan.FFmpeg     ^(compilacion enlazada desde https://ffmpeg.org/download.html^)
echo         o indica su ruta en el archivo .env ^(JARVIS_FFMPEG y JARVIS_FFPROBE^). Luego reinicia Jarvis.

:done
echo.
echo Preparacion completada. Inicia Jarvis con START_JARVIS.cmd
endlocal
exit /b 0

:fail_venv
echo [ERROR] No se pudo crear el entorno de Python. Comprueba que Python esta instalado correctamente.
goto fail
:fail_pip
echo [ERROR] No se pudieron instalar las dependencias de Python. Comprueba tu conexion a internet y vuelve a intentarlo.
goto fail
:fail_node
echo [FALTA] Node.js 18 o superior, necesario una sola vez para compilar la interfaz.
echo         Instalalo desde https://nodejs.org/  o con:  winget install OpenJS.NodeJS.LTS
echo         Despues vuelve a ejecutar este archivo.
goto fail
:fail_npm
popd
echo [ERROR] No se pudo compilar la interfaz. Comprueba tu conexion a internet y vuelve a intentarlo.
goto fail
:fail
echo.
echo La preparacion no se completo.
endlocal
exit /b 1
