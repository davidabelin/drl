@echo off
setlocal
call "%~dp0drl_cloud_env.bat"

echo.
echo ==== DRL Cloud Configure ====
echo Project: %PROJECT_ID%
echo Region : %REGION%

echo.
echo ^> gcloud config set account %SA_EMAIL%
call gcloud config set account %SA_EMAIL%
call gcloud auth activate-service-account %SA_EMAIL% --key-file=%CREDS_PATH%\deeprl-031026-dc9a9d98c6c6.json --project=%PROJECT_ID%
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config set project %PROJECT_ID%
call gcloud config set project %PROJECT_ID%
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config set run/region %REGION%
call gcloud config set run/region %REGION%
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config set artifacts/location %REGION%
call gcloud config set artifacts/location %REGION%
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config set compute/region %REGION%
call gcloud config set compute/region %REGION%
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config set compute/zone %ZONE%
call gcloud config set compute/zone %ZONE%
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config list
call gcloud config list
if errorlevel 1 goto :fail

echo.
echo [OK] DRL gcloud configuration is ready.
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Configuration setup failed.
endlocal
exit /b 1
