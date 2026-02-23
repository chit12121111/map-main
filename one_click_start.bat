@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

cd /d "%~dp0"
set "ROOT=%cd%"
set "API_DIR=%ROOT%\api-laravel"
set "WEB_DIR=%ROOT%\web-ui-react"
set "LOG_DIR=%ROOT%\logs"
set "API_ENV=%API_DIR%\.env"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%I"
set "LOG=%LOG_DIR%\one_click_%TS%.log"
set "API8000_LOG=%LOG_DIR%\api_8000_%TS%.log"
set "API8010_LOG=%LOG_DIR%\api_8010_%TS%.log"
set "WEB_LOG=%LOG_DIR%\web_5173_%TS%.log"
set "QUEUE_LOG=%LOG_DIR%\queue_worker_%TS%.log"

echo [!date! !time!] ==== one click start begin ====>>"%LOG%"
echo ==== one click start begin ====
echo [!date! !time!] root: %ROOT%>>"%LOG%"
echo root: %ROOT%
echo [!date! !time!] api dir: %API_DIR%>>"%LOG%"
echo api dir: %API_DIR%
echo [!date! !time!] web dir: %WEB_DIR%>>"%LOG%"
echo web dir: %WEB_DIR%

set "PHP_EXE="
where php >nul 2>nul
if !errorlevel! equ 0 set "PHP_EXE=php"

if not defined PHP_EXE (
  for /d %%D in ("C:\laragon\bin\php\php-*") do (
    if exist "%%D\php.exe" set "PHP_EXE=%%D\php.exe"
  )
)
if not defined PHP_EXE (
  echo [!date! !time!] ERROR: php not found>>"%LOG%"
  goto FAIL
)

where npx >nul 2>nul
if !errorlevel! neq 0 (
  echo [!date! !time!] ERROR: npx not found>>"%LOG%"
  goto FAIL
)

where curl >nul 2>nul
if !errorlevel! neq 0 (
  echo [!date! !time!] ERROR: curl not found>>"%LOG%"
  goto FAIL
)

if not exist "%API_DIR%\artisan" (
  echo [!date! !time!] ERROR: api-laravel/artisan not found>>"%LOG%"
  goto FAIL
)
if not exist "%WEB_DIR%\package.json" (
  echo [!date! !time!] ERROR: web-ui-react/package.json not found>>"%LOG%"
  goto FAIL
)

set "QUEUE_CONNECTION=sync"
if exist "%API_ENV%" (
  for /f "usebackq tokens=1* delims==" %%A in ("%API_ENV%") do (
    if /I "%%A"=="QUEUE_CONNECTION" set "QUEUE_CONNECTION=%%B"
  )
)

netstat -ano | findstr /I "LISTENING" | findstr /I ":8010 " >nul
if !errorlevel! neq 0 (
  echo [!date! !time!] starting api on 8010>>"%LOG%"
  echo starting api on 8010
  start "API-8010" cmd /c "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan serve --host=127.0.0.1 --port=8010 >> ""%API8010_LOG%"" 2>&1"
) else (
  echo [!date! !time!] port 8010 already listening>>"%LOG%"
)

netstat -ano | findstr /I "LISTENING" | findstr /I ":8000 " >nul
if !errorlevel! neq 0 (
  echo [!date! !time!] starting api on 8000>>"%LOG%"
  echo starting api on 8000
  start "API-8000" cmd /c "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan serve --host=127.0.0.1 --port=8000 >> ""%API8000_LOG%"" 2>&1"
) else (
  echo [!date! !time!] port 8000 already listening>>"%LOG%"
)

netstat -ano | findstr /I "LISTENING" | findstr /I ":5173 " >nul
if !errorlevel! neq 0 (
  echo [!date! !time!] starting web on 5173>>"%LOG%"
  echo starting web on 5173
  start "WEB-5173" cmd /c "cd /d ""%WEB_DIR%"" && npx vite --host=localhost --port=5173 >> ""%WEB_LOG%"" 2>&1"
) else (
  echo [!date! !time!] port 5173 already listening>>"%LOG%"
)

if /I not "!QUEUE_CONNECTION!"=="sync" (
  echo [!date! !time!] starting queue worker (!QUEUE_CONNECTION!)>>"%LOG%"
  echo starting queue worker (!QUEUE_CONNECTION!)
  start "QUEUE-WORKER" cmd /c "cd /d ""%API_DIR%"" && ""%PHP_EXE%"" artisan queue:work --tries=3 --sleep=1 --timeout=120 >> ""%QUEUE_LOG%"" 2>&1"
) else (
  echo [!date! !time!] queue connection is sync (worker not required)>>"%LOG%"
)

set "API8010_FINAL=0"
set /a TRY8010=0
:WAIT_8010
set /a TRY8010+=1
set "HTTP_CODE=000"
for /f %%S in ('curl.exe -L -s -o NUL -w "%%{http_code}" "http://127.0.0.1:8010/health"') do set "HTTP_CODE=%%S"
if not "!HTTP_CODE!"=="000" if !HTTP_CODE! lss 500 set "API8010_FINAL=1"
if "!API8010_FINAL!"=="1" goto WAIT_8010_DONE
if !TRY8010! geq 25 goto WAIT_8010_DONE
timeout /t 1 >nul
goto WAIT_8010
:WAIT_8010_DONE

set "API8000_FINAL=0"
set /a TRY8000=0
:WAIT_8000
set /a TRY8000+=1
set "HTTP_CODE=000"
for /f %%S in ('curl.exe -L -s -o NUL -w "%%{http_code}" "http://127.0.0.1:8000/health"') do set "HTTP_CODE=%%S"
if not "!HTTP_CODE!"=="000" if !HTTP_CODE! lss 500 set "API8000_FINAL=1"
if "!API8000_FINAL!"=="1" goto WAIT_8000_DONE
if !TRY8000! geq 25 goto WAIT_8000_DONE
timeout /t 1 >nul
goto WAIT_8000
:WAIT_8000_DONE

set "WEB5173_FINAL=0"
set /a TRY5173=0
:WAIT_5173
set /a TRY5173+=1
set "HTTP_CODE=000"
for /f %%S in ('curl.exe -L -s -o NUL -w "%%{http_code}" "http://localhost:5173/"') do set "HTTP_CODE=%%S"
if not "!HTTP_CODE!"=="000" if !HTTP_CODE! lss 500 set "WEB5173_FINAL=1"
if "!WEB5173_FINAL!"=="1" goto WAIT_5173_DONE
if !TRY5173! geq 25 goto WAIT_5173_DONE
timeout /t 1 >nul
goto WAIT_5173
:WAIT_5173_DONE

if "!API8010_FINAL!"=="1" (
  echo [!date! !time!] api 8010 healthy>>"%LOG%"
  echo api 8010 healthy
) else (
  echo [!date! !time!] ERROR: api 8010 did not become healthy>>"%LOG%"
  echo ERROR: api 8010 did not become healthy
)
if "!API8000_FINAL!"=="1" (
  echo [!date! !time!] api 8000 healthy>>"%LOG%"
  echo api 8000 healthy
) else (
  echo [!date! !time!] ERROR: api 8000 did not become healthy>>"%LOG%"
  echo ERROR: api 8000 did not become healthy
)
if "!WEB5173_FINAL!"=="1" (
  echo [!date! !time!] web 5173 healthy>>"%LOG%"
  echo web 5173 healthy
) else (
  echo [!date! !time!] ERROR: web 5173 did not become healthy>>"%LOG%"
  echo ERROR: web 5173 did not become healthy
)

start "" "http://localhost:5173/"
echo [!date! !time!] browser open command sent>>"%LOG%"

echo.
echo System start completed.
echo Main log: %LOG%
echo API 8000 log: %API8000_LOG%
echo API 8010 log: %API8010_LOG%
echo Web 5173 log: %WEB_LOG%
if /I not "!QUEUE_CONNECTION!"=="sync" echo Queue worker log: %QUEUE_LOG%
echo.
echo If something fails to open, check logs in %LOG_DIR%
echo [!date! !time!] ==== one click start end ====>>"%LOG%"
exit /b 0

:FAIL
echo.
echo One click start failed.
echo Check log: %LOG%
echo [!date! !time!] ==== one click start failed ====>>"%LOG%"
exit /b 1
