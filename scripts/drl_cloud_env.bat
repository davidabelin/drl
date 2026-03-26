@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

rem Shared DRL Google Cloud settings.
rem Usage: call "%~dp0drl_cloud_env.bat" from another batch file or CMD session.
rem This file intentionally does not use setlocal so the caller keeps the vars.

set "PROJECT_ID=deeprl-031026"
set "PROJECT_NAME=DeepRL"
set "REGION=us-west3"
set "ZONE=us-west3-a"
set "APP_ENGINE_LOCATION=us-west"
set "SA_EMAIL=administrator@deeprl-031026.iam.gserviceaccount.com"
set "REPO_NAME=drl-web"
set "BUCKET_NAME=deeprl-031026-drl-data"
set "SERVICE_NAME=drl-web"
set "CANONICAL_DRL_URL=https://deeprl-031026.wm.r.appspot.com"
set "CREDS_PATH=C:\Users\David\Documents\Local_Data\creds"
set "RUN_MEMORY=1Gi"
set "RUN_CPU=1"
exit /b 0

:help
echo.
echo DRL Cloud Environment Variables
echo.
echo Usage:
echo   call scripts\drl_cloud_env.bat
echo.
echo What it does:
echo   Sets the shared project, region, service, and credential variables used by the other DRL scripts.
echo.
echo Typical use:
echo   call scripts\drl_cloud_env.bat
echo   echo %%PROJECT_ID%%
echo.
echo Notes:
echo   - Use CALL so the variables remain available in the current CMD session or calling batch file.
echo   - Running this file directly only affects that one CMD process.
exit /b 0
