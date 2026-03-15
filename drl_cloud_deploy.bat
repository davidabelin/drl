@echo off
setlocal
call "%~dp0drl_cloud_env.bat"
pushd "%~dp0" >nul 2>&1
if errorlevel 1 goto :fail

echo.
echo ==== DRL App Engine Deploy ====
echo Project : %PROJECT_ID%
echo Region  : %APP_ENGINE_LOCATION%
echo URL     : %CANONICAL_DRL_URL%

echo.
echo ^> gcloud app describe --project="%PROJECT_ID%"
gcloud app describe --project="%PROJECT_ID%" >nul 2>&1
if errorlevel 1 (
  echo.
  echo ^> gcloud app create --project="%PROJECT_ID%" --region="%APP_ENGINE_LOCATION%"
  gcloud app create --project="%PROJECT_ID%" --region="%APP_ENGINE_LOCATION%"
  if errorlevel 1 goto :fail_popd
)

echo.
echo ^> gcloud app deploy app.yaml --project="%PROJECT_ID%" --quiet
gcloud app deploy app.yaml --project="%PROJECT_ID%" --quiet
if errorlevel 1 goto :fail_popd

echo.
echo ^> gcloud app describe --project="%PROJECT_ID%" --format="yaml(defaultHostname,locationId,serviceAccount)"
gcloud app describe --project="%PROJECT_ID%" --format="yaml(defaultHostname,locationId,serviceAccount)"
if errorlevel 1 goto :fail_popd

echo.
echo ^> gcloud app versions list --project="%PROJECT_ID%"
gcloud app versions list --project="%PROJECT_ID%"
if errorlevel 1 goto :fail_popd

echo.
echo [OK] Canonical App Engine deploy finished.
popd >nul
endlocal
exit /b 0

:fail_popd
popd >nul

:fail
echo.
echo [ERROR] Deploy failed.
endlocal
exit /b 1
