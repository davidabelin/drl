@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

setlocal

rem Read-only status sweep for the DRL Google Cloud project.
rem Usage: scripts\drl_cloud_status.bat
rem Run this after configure/setup or whenever a deploy needs investigation.

call "%~dp0drl_cloud_env.bat"

echo.
echo ==== DRL Cloud Status ====
echo Project: %PROJECT_ID%
echo Region : %REGION%
echo Canon  : %CANONICAL_DRL_URL%
echo SA     : %SA_EMAIL%

echo.
echo ^> gcloud auth list
call gcloud auth list
if errorlevel 1 goto :fail
echo.
echo ^> gcloud config list
call gcloud config list
if errorlevel 1 goto :fail
echo.
echo ^> gcloud projects describe "%PROJECT_ID%"
call gcloud projects describe "%PROJECT_ID%"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud billing projects describe "%PROJECT_ID%"
call gcloud billing projects describe "%PROJECT_ID%"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud services list --enabled --project="%PROJECT_ID%"
call gcloud services list --enabled --project="%PROJECT_ID%"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud iam service-accounts list --project="%PROJECT_ID%"
call gcloud iam service-accounts list --project="%PROJECT_ID%"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud iam service-accounts keys list --iam-account="%SA_EMAIL%" --project="%PROJECT_ID%"
call gcloud iam service-accounts keys list --iam-account="%SA_EMAIL%" --project="%PROJECT_ID%"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud storage buckets list --project="%PROJECT_ID%" --format="table(name,location,locationType,storageClass)"
call gcloud storage buckets list --project="%PROJECT_ID%" --format="table(name,location,locationType,storageClass)"
if errorlevel 1 goto :fail
echo.
echo ^> gcloud artifacts repositories list --project="%PROJECT_ID%" --location=all
call gcloud artifacts repositories list --project="%PROJECT_ID%" --location=all
if errorlevel 1 goto :fail
echo.
echo ^> gcloud run services list --project="%PROJECT_ID%" --region="%REGION%"
call gcloud run services list --project="%PROJECT_ID%" --region="%REGION%"
if errorlevel 1 goto :fail

echo.
echo ^> gcloud app describe --project="%PROJECT_ID%"
call gcloud app describe --project="%PROJECT_ID%"
if errorlevel 1 (
  echo.
  echo [INFO] No App Engine app exists yet for %PROJECT_ID%.
)

echo.
echo ^> gcloud secrets list --project="%PROJECT_ID%"
call gcloud secrets list --project="%PROJECT_ID%"
if errorlevel 1 goto :fail

echo.
echo [OK] Status inspection finished.
endlocal
exit /b 0

:fail
echo.
echo [ERROR] One of the required gcloud commands failed.
endlocal
exit /b 1

:help
echo.
echo DRL Cloud Status
echo.
echo Usage:
echo   scripts\drl_cloud_status.bat
echo.
echo What it does:
echo   Runs a read-only inspection of auth, project config, billing, enabled APIs, IAM,
echo   service-account keys, buckets, Artifact Registry, Cloud Run, App Engine, and secrets.
echo.
echo When to use it:
echo   - Before deploying, to confirm the active account and project are correct.
echo   - After a setup or deploy failure, to see what cloud resources already exist.
echo.
echo Prerequisites:
echo   - gcloud is installed
echo   - You have valid auth, usually via scripts\drl_cloud_configure.bat
exit /b 0
