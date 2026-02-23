@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
set "ROOT=%cd%"
set "API_DIR=%ROOT%\api-laravel"
set "WEB_DIR=%ROOT%\web-ui-react"
set "LOG_DIR=%ROOT%\logs"
set "API_ENV=%API_DIR%\.env"
set "MAIL_OK=1"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%I"
set "LOG=%LOG_DIR%\one_click_install_%TS%.log"
set "LAST_ERROR="

call :log "==== one click install begin ===="
call :log "root: %ROOT%"
call :log "api dir: %API_DIR%"
call :log "web dir: %WEB_DIR%"

if not exist "%API_DIR%\artisan" (
  call :log "ERROR: missing api-laravel/artisan"
  goto :fail
)
if not exist "%WEB_DIR%\package.json" (
  call :log "ERROR: missing web-ui-react/package.json"
  goto :fail
)

set "PY_CMD="
py -3.12 --version >nul 2>&1
if %errorlevel% equ 0 (
  set "PY_CMD=py -3.12"
  call :log "python selected: py -3.12"
) else (
  python --version >nul 2>&1
  if %errorlevel% equ 0 (
    set "PY_CMD=python"
    call :log "python selected: python"
  ) else (
    call :log "ERROR: python not found"
    goto :fail
  )
)

set "PHP_EXE="
where php >nul 2>nul
if %errorlevel% equ 0 (
  set "PHP_EXE=php"
  call :log "php found in PATH"
) else (
  for /d %%D in ("C:\laragon\bin\php\php-*") do (
    if exist "%%D\php.exe" (
      set "PHP_EXE=%%D\php.exe"
      call :log "php found in laragon: %%D\php.exe"
      goto :php_ok
    )
  )
)

:php_ok
if not defined PHP_EXE (
  call :log "ERROR: php not found"
  goto :fail
)

where composer >nul 2>nul
if %errorlevel% neq 0 (
  call :log "ERROR: composer not found"
  goto :fail
)

where npx >nul 2>nul
if %errorlevel% neq 0 (
  call :log "ERROR: npx not found"
  goto :fail
)

call :run "Upgrade pip" "%PY_CMD% -m pip install --upgrade pip"
if errorlevel 1 goto :fail

call :run "Install python requirements" "%PY_CMD% -m pip install -r ""%ROOT%\requirements.txt"""
if errorlevel 1 goto :fail

if exist "%ROOT%\requirements_stage2.txt" (
  call :run "Install stage2 requirements" "%PY_CMD% -m pip install -r ""%ROOT%\requirements_stage2.txt"""
  if errorlevel 1 goto :fail
)

call :run "Install Playwright Chromium" "%PY_CMD% -m playwright install chromium"
if errorlevel 1 goto :fail

if not exist "%API_DIR%\.env" (
  if exist "%API_DIR%\.env.example" (
    call :run "Copy api .env" "copy /Y ""%API_DIR%\.env.example"" ""%API_DIR%\.env"""
    if errorlevel 1 goto :fail
  ) else (
    call :log "ERROR: api .env and .env.example not found"
    goto :fail
  )
)
set "MAIL_MAILER="
set "MAIL_HOST="
set "MAIL_PORT="
set "MAIL_USERNAME="
set "MAIL_PASSWORD="
set "MAIL_ENCRYPTION="
set "MAIL_FROM_ADDRESS="
set "MAIL_FROM_NAME="
for /f "usebackq tokens=1* delims==" %%A in ("%API_ENV%") do (
  if /I "%%A"=="MAIL_MAILER" set "MAIL_MAILER=%%B"
  if /I "%%A"=="MAIL_HOST" set "MAIL_HOST=%%B"
  if /I "%%A"=="MAIL_PORT" set "MAIL_PORT=%%B"
  if /I "%%A"=="MAIL_USERNAME" set "MAIL_USERNAME=%%B"
  if /I "%%A"=="MAIL_PASSWORD" set "MAIL_PASSWORD=%%B"
  if /I "%%A"=="MAIL_ENCRYPTION" set "MAIL_ENCRYPTION=%%B"
  if /I "%%A"=="MAIL_FROM_ADDRESS" set "MAIL_FROM_ADDRESS=%%B"
  if /I "%%A"=="MAIL_FROM_NAME" set "MAIL_FROM_NAME=%%B"
)

call :run "Composer install (api)" "cd /d ""%API_DIR%"" && composer install"
if errorlevel 1 goto :fail

call :run "Laravel key generate" "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan key:generate --force"
if errorlevel 1 goto :fail

call :run "Laravel cache clear" "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan optimize:clear"
if errorlevel 1 goto :fail

call :run "Laravel migrate" "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan migrate --force"
if errorlevel 1 goto :fail

call :run "Install web dependencies" "cd /d ""%WEB_DIR%"" && npm install"
if errorlevel 1 goto :fail

if not defined MAIL_MAILER set "MAIL_OK=0"
if not defined MAIL_HOST set "MAIL_OK=0"
if not defined MAIL_PORT set "MAIL_OK=0"
if not defined MAIL_USERNAME set "MAIL_OK=0"
if not defined MAIL_PASSWORD set "MAIL_OK=0"
if not defined MAIL_ENCRYPTION set "MAIL_OK=0"
if not defined MAIL_FROM_ADDRESS set "MAIL_OK=0"
if not defined MAIL_FROM_NAME set "MAIL_OK=0"
if "%MAIL_OK%"=="0" (
  call :log "WARNING: mail config is incomplete in api-laravel/.env"
  call :log "         Required: MAIL_MAILER, MAIL_HOST, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_ENCRYPTION, MAIL_FROM_ADDRESS, MAIL_FROM_NAME"
)

call :log "==== one click install success ===="
echo.
echo Installation completed successfully.
echo Log file: %LOG%
echo.
echo Next step: run one_click_start.bat
exit /b 0

:run
set "STEP=%~1"
set "CMD=%~2"
call :log "RUN: %STEP%"
cmd /c "%CMD%" >> "%LOG%" 2>&1
if errorlevel 1 (
  set "LAST_ERROR=%STEP%"
  call :log "ERROR: %STEP% failed"
  exit /b 1
)
call :log "OK: %STEP%"
exit /b 0

:log
echo [%date% %time%] %~1>>"%LOG%"
echo %~1
exit /b 0

:fail
call :log "==== one click install failed ===="
echo.
echo Installation failed.
if defined LAST_ERROR echo Failed step: %LAST_ERROR%
echo Check log: %LOG%
exit /b 1
