@echo off
setlocal
call "%~dp0drl_cloud_env.bat"
set "SOURCE_DIR=%~dp0"

echo.
echo ==== DRL Cloud Deploy ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo Service : %SERVICE_NAME%
echo Source  : %SOURCE_DIR%

echo.
echo ^> gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source="%SOURCE_DIR%" --service-account="%SA_EMAIL%" --allow-unauthenticated --set-env-vars="AIX_HUB_URL=/,DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
gcloud run deploy %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --source="%SOURCE_DIR%" --service-account="%SA_EMAIL%" --allow-unauthenticated --set-env-vars="AIX_HUB_URL=/,DRL_LUNAR_JOBS_ROOT=/tmp/drl_lunar_jobs,DRL_LUNAR_MAX_WORKERS=1"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud run services describe %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --format="yaml(metadata.name,status.url,spec.template.spec.serviceAccountName,spec.template.spec.containers[0].env)"
gcloud run services describe %SERVICE_NAME% --project="%PROJECT_ID%" --region="%REGION%" --format="yaml(metadata.name,status.url,spec.template.spec.serviceAccountName,spec.template.spec.containers[0].env)"
if errorlevel 1 goto :fail

echo.
echo [OK] Deploy finished.
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Deploy failed.
endlocal
exit /b 1
