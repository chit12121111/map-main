@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
set "ROOT=%cd%"
set "API_DIR=%ROOT%\api-laravel"
set "WEB_DIR=%ROOT%\web-ui-react"
set "LOG_DIR=%ROOT%\logs"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%I"
set "LOG=%LOG_DIR%\one_click_%TS%.log"
set "API8000_LOG=%LOG_DIR%\api_8000_%TS%.log"
set "API8010_LOG=%LOG_DIR%\api_8010_%TS%.log"
set "WEB_LOG=%LOG_DIR%\web_5173_%TS%.log"

call :log "==== one click start begin ===="
call :log "root: %ROOT%"
call :log "api dir: %API_DIR%"
call :log "web dir: %WEB_DIR%"

set "PHP_EXE="
where php >nul 2>nul
if %errorlevel% equ 0 (
  set "PHP_EXE=php"
  call :log "php found in PATH"
)

if not defined PHP_EXE (
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
  call :log "ERROR: php not found. run one_click_install.bat first, or install php/open laragon."
  goto :fail
)

where npx >nul 2>nul
if %errorlevel% neq 0 (
  call :log "ERROR: npx not found. run one_click_install.bat first, or install nodejs."
  goto :fail
)

if not exist "%API_DIR%\artisan" (
  call :log "ERROR: api-laravel/artisan not found."
  goto :fail
)
if not exist "%WEB_DIR%\package.json" (
  call :log "ERROR: web-ui-react/package.json not found."
  goto :fail
)

call :ensure_service 8010 "http://127.0.0.1:8010/health" API8010_OK
call :ensure_service 8000 "http://127.0.0.1:8000/health" API8000_OK
call :ensure_service 5173 "http://localhost:5173/" WEB5173_OK

call :wait_http "http://127.0.0.1:8010/health" 2 API8010_FINAL
call :wait_http "http://127.0.0.1:8000/health" 2 API8000_FINAL
call :wait_http "http://localhost:5173/" 2 WEB5173_FINAL

if "!API8010_FINAL!"=="1" (
  call :log "api 8010 healthy"
) else (
  call :log "ERROR: api 8010 did not become healthy."
)
if "!API8000_FINAL!"=="1" (
  call :log "api 8000 healthy"
) else (
  call :log "ERROR: api 8000 did not become healthy."
)
if "!WEB5173_FINAL!"=="1" (
  call :log "web 5173 healthy"
) else (
  call :log "ERROR: web 5173 did not become healthy."
)

start "" "http://localhost:5173/"
if %errorlevel% neq 0 (
  call :log "ERROR: browser did not open automatically. open this url manually: http://localhost:5173/"
) else (
  call :log "browser open command sent: http://localhost:5173/"
)

echo.
echo System start completed.
echo Main log: %LOG%
echo API 8000 log: %API8000_LOG%
echo API 8010 log: %API8010_LOG%
echo Web 5173 log: %WEB_LOG%
echo.
echo If something fails to open, check logs in %LOG_DIR%
call :log "==== one click start end ===="
exit /b 0

:ensure_service
set "PORT=%~1"
set "URL=%~2"
set "OUTVAR=%~3"
set "%OUTVAR%=0"

call :is_listening %PORT% LISTENING
if "%LISTENING%"=="1" (
  call :log "port %PORT% already listening"
) else (
  if "%PORT%"=="8000" (
    call :log "starting api on 8000"
    start "API-8000" cmd /c "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan serve --host=127.0.0.1 --port=8000 >> ""%API8000_LOG%"" 2>&1"
  ) else if "%PORT%"=="8010" (
    call :log "starting api on 8010 (internal pipeline api)"
    start "API-8010" cmd /c "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan serve --host=127.0.0.1 --port=8010 >> ""%API8010_LOG%"" 2>&1"
  ) else if "%PORT%"=="5173" (
    call :log "starting web on 5173"
    start "WEB-5173" cmd /c "cd /d ""%WEB_DIR%"" && npx vite --host=localhost --port=5173 >> ""%WEB_LOG%"" 2>&1"
  )
)

call :wait_http "%URL%" 25 READY
if "%READY%"=="1" set "%OUTVAR%=1"
exit /b 0

:wait_http
set "URL=%~1"
set "MAX_RETRY=%~2"
set "OUTVAR=%~3"
set "%OUTVAR%=0"
for /l %%N in (1,1,%MAX_RETRY%) do (
  for /f %%R in ('powershell -NoProfile -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Uri \"%URL%\" -TimeoutSec 3; if($r.StatusCode -ge 200 -and $r.StatusCode -lt 500){Write-Output 1} else {Write-Output 0} } catch { Write-Output 0 }"') do (
    if "%%R"=="1" (
      set "%OUTVAR%=1"
      call :log "health ok: %URL% (try %%N)"
      exit /b 0
    )
  )
  timeout /t 1 >nul
)
call :log "health check failed: %URL%"
exit /b 0

:is_listening
set "PORT=%~1"
set "OUTVAR=%~2"
for /f %%R in ('powershell -NoProfile -Command "$c=Get-NetTCPConnection -State Listen -LocalPort %PORT% -ErrorAction SilentlyContinue; if($c){Write-Output 1} else {Write-Output 0}"') do set "%OUTVAR%=%%R"
exit /b 0

:log
echo [%date% %time%] %~1>>"%LOG%"
echo %~1
exit /b 0

:fail
echo.
echo One click start failed.
echo Check log: %LOG%
call :log "==== one click start failed ===="
exit /b 1
