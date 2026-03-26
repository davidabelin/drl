@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

setlocal
call "%~dp0drl_cloud_env.bat"

rem Resolve the repo root from the script location so the command works from any current directory.
for %%I in ("%~dp0..") do set "REPO_DIR=%%~fI"
set "FAILED_STEP=change to repo directory"
set "FAILED_COMMAND=pushd ""%REPO_DIR%"""
pushd "%REPO_DIR%" >nul 2>&1
if errorlevel 1 goto :fail

echo.
echo ==== DRL App Engine Publish ====
echo Project : %PROJECT_ID%
echo Region  : %APP_ENGINE_LOCATION%
echo URL     : %CANONICAL_DRL_URL%
echo Script  : %~f0
echo Repo Dir: %CD%

rem Probe first so an initial deploy can create the App Engine app instead of failing immediately.
echo.
echo [INFO] Checking whether the App Engine app already exists...
echo [INFO] This probe can take a minute if gcloud is refreshing auth or contacting App Engine.
echo.
set "FAILED_STEP=check App Engine application"
set "FAILED_COMMAND=gcloud app describe --project=""%PROJECT_ID%"""
echo ^> gcloud app describe --project="%PROJECT_ID%"
call gcloud app describe --project="%PROJECT_ID%" 1>nul
if errorlevel 1 (
  echo.
  echo [WARN] App Engine describe did not succeed.
  echo [WARN] If the message above says the app does not exist, the script will try to create it.
  echo [WARN] If the message above is auth, billing, API, or permission related, creation may fail too.
  echo.
  echo [INFO] Attempting create...
  set "FAILED_STEP=create App Engine application"
  set "FAILED_COMMAND=gcloud app create --project=""%PROJECT_ID%"" --region=""%APP_ENGINE_LOCATION%"""
  echo ^> gcloud app create --project="%PROJECT_ID%" --region="%APP_ENGINE_LOCATION%"
  call gcloud app create --project="%PROJECT_ID%" --region="%APP_ENGINE_LOCATION%"
  if errorlevel 1 goto :fail_popd
 ) else (
  echo [OK] App Engine app exists.
)

echo.
set "FAILED_STEP=publish app.yaml to App Engine"
set "FAILED_COMMAND=gcloud app deploy app.yaml --project=""%PROJECT_ID%"" --quiet"
echo ^> gcloud app deploy app.yaml --project="%PROJECT_ID%" --quiet
call gcloud app deploy app.yaml --project="%PROJECT_ID%" --quiet
if errorlevel 1 goto :fail_popd

echo.
set "FAILED_STEP=describe deployed App Engine application"
set "FAILED_COMMAND=gcloud app describe --project=""%PROJECT_ID%"" --format=""yaml(defaultHostname,locationId,serviceAccount)"""
echo ^> gcloud app describe --project="%PROJECT_ID%" --format="yaml(defaultHostname,locationId,serviceAccount)"
call gcloud app describe --project="%PROJECT_ID%" --format="yaml(defaultHostname,locationId,serviceAccount)"
if errorlevel 1 goto :fail_popd

echo.
set "FAILED_STEP=list deployed App Engine versions"
set "FAILED_COMMAND=gcloud app versions list --project=""%PROJECT_ID%"""
echo ^> gcloud app versions list --project="%PROJECT_ID%"
call gcloud app versions list --project="%PROJECT_ID%"
if errorlevel 1 goto :fail_popd

echo.
echo [OK] Canonical App Engine publish finished.
popd >nul
endlocal
exit /b 0

:fail_popd
set "FAILED_CODE=%errorlevel%"
popd >nul
goto :fail_report

:fail
set "FAILED_CODE=%errorlevel%"

:fail_report
echo.
echo [ERROR] App Engine publish failed.
echo [ERROR] Step   : %FAILED_STEP%
echo [ERROR] Command: %FAILED_COMMAND%
echo [ERROR] Exit   : %FAILED_CODE%
echo.
echo Suggested next checks:
echo   1. Run scripts\drl_cloud_configure.bat
echo   2. Run scripts\drl_legacy_cloud_setup.bat
echo   3. Run scripts\drl_cloud_status.bat
echo   4. Verify billing, enabled APIs, and App Engine permissions in %PROJECT_ID%
echo   5. Re-run the command above manually if you need the full gcloud error in isolation
endlocal
exit /b %FAILED_CODE%

:help
echo.
echo DRL App Engine Publish
echo.
echo Usage:
echo   scripts\drl_appengine_publish.bat
echo.
echo What it does:
echo   Deploys app.yaml to the canonical App Engine service for this repo, creating the
echo   App Engine application first if it does not already exist.
echo.
echo When to use it:
echo   - For the current canonical DRL web deploy.
echo   - After changing app code, static assets, or app.yaml for the App Engine target.
echo.
echo Recommended order:
echo   1. scripts\drl_cloud_configure.bat
echo   2. scripts\drl_legacy_cloud_setup.bat
echo   3. scripts\drl_appengine_publish.bat
echo   4. scripts\drl_cloud_status.bat
exit /b 0
