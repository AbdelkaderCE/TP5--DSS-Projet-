@echo off
setlocal ENABLEDELAYEDEXPANSION

:: Flask App Start Script (Batch)
:: Usage examples:
::   start_app.bat
::   start_app.bat -Host 0.0.0.0 -Port 8000
::   start_app.bat -RecreateVenv -SkipInstall
:: Supported flags:
::   -RecreateVenv   Recreate the virtual environment
::   -Host <host>     Host to bind (default 127.0.0.1)
::   -Port <port>     Port to bind (default 5000)
::   -SkipInstall     Skip requirements installation
::   -NoDebug         (Reserved; app.py currently forces debug=True)
::   -Help            Show this help

set HOST=127.0.0.1
set PORT=5000
set RECREATE=
set SKIPINSTALL=
set NODEBUG=

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="-Host" (
  shift
  if "%~1"=="" (echo Missing value for -Host & goto :fail)
  set HOST=%~1
  shift
  goto parse_args
)
if /I "%~1"=="-Port" (
  shift
  if "%~1"=="" (echo Missing value for -Port & goto :fail)
  set PORT=%~1
  shift
  goto parse_args
)
if /I "%~1"=="-RecreateVenv" (
  set RECREATE=1
  shift
  goto parse_args
)
if /I "%~1"=="-SkipInstall" (
  set SKIPINSTALL=1
  shift
  goto parse_args
)
if /I "%~1"=="-NoDebug" (
  set NODEBUG=1
  shift
  goto parse_args
)
if /I "%~1"=="-Help" (
  goto :help
)
if /I "%~1"=="/?" (
  goto :help
)
:: Unknown argument
echo Unknown argument: %~1
shift
goto parse_args

:args_done

:: Determine Python launcher (prefer py)
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set PY_CMD=py
) else (
  where python >nul 2>nul
  if %ERRORLEVEL%==0 (
    set PY_CMD=python
  ) else (
    echo Python not found in PATH.
    goto :fail
  )
)

set VENV_DIR=.venv
if defined RECREATE if exist "%VENV_DIR%" (
  echo Removing existing virtual environment...
  rmdir /s /q "%VENV_DIR%"
)

if not exist "%VENV_DIR%" (
  echo Creating virtual environment...
  %PY_CMD% -m venv "%VENV_DIR%"
  if %ERRORLEVEL% NEQ 0 (echo Failed to create virtual environment.& goto :fail)
)

call "%VENV_DIR%\Scripts\activate.bat"
if %ERRORLEVEL% NEQ 0 (echo Failed to activate virtual environment.& goto :fail)

echo Upgrading pip...
python -m pip install --upgrade pip --quiet

if not defined SKIPINSTALL (
  if exist requirements.txt (
    echo Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (echo Dependency installation failed.& goto :fail)
  ) else (
    echo requirements.txt not found; skipping install.
  )
) else (
  echo Skipping dependency installation.
)

if not defined FLASK_SECRET_KEY (
  set FLASK_SECRET_KEY=dev-secret-key
)

set FLASK_RUN_HOST=%HOST%
set FLASK_RUN_PORT=%PORT%

if not exist app.py (
  echo app.py not found.
  goto :fail
)

echo Starting application on http://%HOST%:%PORT% (Debug forced True in app.py)
python app.py
set EXITCODE=%ERRORLEVEL%
if %EXITCODE% NEQ 0 (
  echo Application exited with code %EXITCODE%.
  goto :fail
)

echo Application closed normally.
endlocal
exit /b 0

:help
echo.
echo Start Flask App Script
findstr /B /C:":: " "%~f0"
exit /b 0

:fail
endlocal
exit /b 1
