@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

setlocal

rem Sets the active gcloud account, project, region, and zone for DRL work.
rem Usage: scripts\drl_cloud_configure.bat
rem Run this before any setup or deploy script when opening a fresh shell.

call "%~dp0drl_cloud_env.bat"

echo.
echo ==== DRL Cloud Configure ====
echo Project: %PROJECT_ID%
echo Region : %REGION%

rem Switch to the DRL service account and then pin the common gcloud defaults.
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

:help
echo.
echo DRL Cloud Configure
echo.
echo Usage:
echo   scripts\drl_cloud_configure.bat
echo.
echo What it does:
echo   Activates the DRL service account key configured for this repo and sets the active
echo   gcloud account, project, Cloud Run region, Artifact Registry location, and compute region/zone.
echo.
echo When to use it:
echo   - At the start of a new shell session.
echo   - Before running scripts that create resources or deploy the app.
echo.
echo Prerequisites:
echo   - gcloud is installed
echo   - The key file deeprl-031026-dc9a9d98c6c6.json exists in the credential directory from scripts\drl_cloud_env.bat
exit /b 0
