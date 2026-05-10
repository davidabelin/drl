@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

setlocal
call "%~dp0drl_cloud_env.bat"

rem Resolve repo root from the script path so deployment always uses this repo checkout.
for %%I in ("%~dp0..") do set "REPO_DIR=%%~fI"
pushd "%REPO_DIR%" >nul 2>&1
if errorlevel 1 goto :fail
set "SOURCE_DIR=%CD%"

rem This is the older Cloud Run deploy path kept for the legacy public URL and comparisons.
echo.
echo ==== DRL Cloud Run Publish ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo Service : %SERVICE_NAME%
echo Source  : %SOURCE_DIR%
echo Memory  : %RUN_MEMORY%
echo CPU     : %RUN_CPU%

echo.
echo ^> gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source . --service-account="%SA_EMAIL%" --allow-unauthenticated --memory="%RUN_MEMORY%" --cpu="%RUN_CPU%" --set-env-vars="DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
call gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source . --service-account="%SA_EMAIL%" --allow-unauthenticated --memory="%RUN_MEMORY%" --cpu="%RUN_CPU%" --set-env-vars="DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
if errorlevel 1 goto :fail_popd
echo.
echo ^> gcloud run services describe %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --format="yaml(metadata.name,status.url)"
call gcloud run services describe %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --format="yaml(metadata.name,status.url)"
if errorlevel 1 goto :fail_popd

echo.
echo [OK] Cloud Run publish finished.
popd >nul
endlocal
exit /b 0

:fail_popd
popd >nul

:fail
echo.
echo [ERROR] Cloud Run publish failed.
endlocal
exit /b 1

:help
echo.
echo DRL Legacy Cloud Run Publish
echo.
echo Usage:
echo   scripts\drl_legacy_cloudrun_publish.bat
echo.
echo What it does:
echo   Builds and deploys this repo to the older public Cloud Run service, currently drl-web.
echo.
echo When to use it:
echo   - Only when you intentionally want to refresh or compare against the legacy Cloud Run host.
echo   - Not for the canonical DRL deploy; use scripts\drl_appengine_publish.bat for that.
echo.
echo Prerequisites:
echo   - scripts\drl_cloud_configure.bat has been run in the current environment
echo   - Required APIs and resources already exist, usually via scripts\drl_legacy_cloud_setup.bat
exit /b 0
