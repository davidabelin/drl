@echo off
setlocal
call "%~dp0drl_cloud_env.bat"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto :fail
set "SOURCE_DIR=%CD%"

echo.
echo ==== DRL Legacy Cloud Run Deploy ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo Service : %SERVICE_NAME%
echo Source  : %SOURCE_DIR%
echo Memory  : %RUN_MEMORY%
echo CPU     : %RUN_CPU%

echo.
echo ^> gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source . --service-account="%SA_EMAIL%" --allow-unauthenticated --memory="%RUN_MEMORY%" --cpu="%RUN_CPU%" --set-env-vars="AIX_HUB_URL=https://aix-labs.uw.r.appspot.com/,DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source . --service-account="%SA_EMAIL%" --allow-unauthenticated --memory="%RUN_MEMORY%" --cpu="%RUN_CPU%" --set-env-vars="AIX_HUB_URL=https://aix-labs.uw.r.appspot.com/,DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
if errorlevel 1 goto :fail_popd
echo.
echo ^> gcloud run services describe %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --format="yaml(metadata.name,status.url)"
gcloud run services describe %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --format="yaml(metadata.name,status.url)"
if errorlevel 1 goto :fail_popd

echo.
echo [OK] Legacy Cloud Run deploy finished.
popd >nul
endlocal
exit /b 0

:fail_popd
popd >nul

:fail
echo.
echo [ERROR] Legacy Cloud Run deploy failed.
endlocal
exit /b 1
