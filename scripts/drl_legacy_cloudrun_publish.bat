@echo off
setlocal
call "%~dp0drl_cloud_env.bat"
for %%I in ("%~dp0..") do set "REPO_DIR=%%~fI"
pushd "%REPO_DIR%" >nul 2>&1
if errorlevel 1 goto :fail
set "SOURCE_DIR=%CD%"

echo.
echo ==== DRL Cloud Run Publish ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo Service : %SERVICE_NAME%
echo Source  : %SOURCE_DIR%
echo Memory  : %RUN_MEMORY%
echo CPU     : %RUN_CPU%

echo.
echo ^> gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source . --service-account="%SA_EMAIL%" --allow-unauthenticated --memory="%RUN_MEMORY%" --cpu="%RUN_CPU%" --set-env-vars="AIX_HUB_URL=https://aix-labs.uw.r.appspot.com/,DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
call gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source . --service-account="%SA_EMAIL%" --allow-unauthenticated --memory="%RUN_MEMORY%" --cpu="%RUN_CPU%" --set-env-vars="AIX_HUB_URL=https://aix-labs.uw.r.appspot.com/,DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
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
