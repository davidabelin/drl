@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

setlocal
call "%~dp0drl_cloud_env.bat"

rem Idempotent project bootstrap for the DRL cloud resources used by deploy scripts.
rem Usage: scripts\drl_legacy_cloud_setup.bat
rem Safe to re-run when you need to confirm APIs, App Engine, Artifact Registry, and bucket state.

echo.
echo ==== DRL Cloud Setup ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo AE Loc  : %APP_ENGINE_LOCATION%
echo Repo    : %REPO_NAME%
echo Bucket  : %BUCKET_NAME%

rem Enable the APIs required by both the App Engine and Cloud Run workflows.
echo.
echo ^> gcloud services enable appengine.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com logging.googleapis.com iam.googleapis.com iamcredentials.googleapis.com serviceusage.googleapis.com compute.googleapis.com run.googleapis.com --project="%PROJECT_ID%"
call gcloud services enable appengine.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com logging.googleapis.com iam.googleapis.com iamcredentials.googleapis.com serviceusage.googleapis.com compute.googleapis.com run.googleapis.com --project="%PROJECT_ID%"
if errorlevel 1 goto :fail

rem Create long-lived resources only if they are missing so the script stays repeatable.
echo.
echo ^> gcloud app describe --project="%PROJECT_ID%"
call gcloud app describe --project="%PROJECT_ID%" >nul 2>&1
if errorlevel 1 (
  echo.
  echo ^> gcloud app create --project="%PROJECT_ID%" --region="%APP_ENGINE_LOCATION%"
  call gcloud app create --project="%PROJECT_ID%" --region="%APP_ENGINE_LOCATION%"
  if errorlevel 1 goto :fail
) else (
  echo [OK] App Engine app already exists for %PROJECT_ID%
)

echo.
echo ^> gcloud artifacts repositories describe %REPO_NAME% --location="%REGION%" --project="%PROJECT_ID%"
call gcloud artifacts repositories describe %REPO_NAME% --location="%REGION%" --project="%PROJECT_ID%" >nul 2>&1
if errorlevel 1 (
  echo.
  echo ^> gcloud artifacts repositories create %REPO_NAME% --project="%PROJECT_ID%" --location="%REGION%" --repository-format=docker --description="DRL web containers"
  call gcloud artifacts repositories create %REPO_NAME% --project="%PROJECT_ID%" --location="%REGION%" --repository-format=docker --description="DRL web containers"
  if errorlevel 1 goto :fail
) else (
  echo [OK] Artifact Registry repository already exists: %REPO_NAME%
)

echo.
echo ^> gcloud storage buckets describe gs://%BUCKET_NAME%
call gcloud storage buckets describe gs://%BUCKET_NAME% >nul 2>&1
if errorlevel 1 (
  echo.
  echo ^> gcloud storage buckets create gs://%BUCKET_NAME% --project="%PROJECT_ID%" --location="%REGION%" --uniform-bucket-level-access
  call gcloud storage buckets create gs://%BUCKET_NAME% --project="%PROJECT_ID%" --location="%REGION%" --uniform-bucket-level-access
  if errorlevel 1 goto :fail
) else (
  echo [OK] Storage bucket already exists: gs://%BUCKET_NAME%
)

echo.
echo ^> gcloud artifacts repositories list --project="%PROJECT_ID%" --location=all
call gcloud artifacts repositories list --project="%PROJECT_ID%" --location=all
if errorlevel 1 goto :fail
echo.
echo ^> gcloud storage buckets describe gs://%BUCKET_NAME% --format="yaml(name,location,locationType,storageClass,iamConfiguration)"
call gcloud storage buckets describe gs://%BUCKET_NAME% --format="yaml(name,location,locationType,storageClass,iamConfiguration)"
if errorlevel 1 goto :fail

echo.
echo [OK] Cloud setup finished.
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Cloud setup failed.
endlocal
exit /b 1

:help
echo.
echo DRL Cloud Setup
echo.
echo Usage:
echo   scripts\drl_legacy_cloud_setup.bat
echo.
echo What it does:
echo   Enables the required Google Cloud APIs and makes sure the App Engine app,
echo   Artifact Registry repo, and storage bucket exist for this project.
echo.
echo When to use it:
echo   - During initial project bootstrap.
echo   - After changing projects or when a deploy fails because a cloud resource is missing.
echo.
echo Recommended order:
echo   1. scripts\drl_cloud_configure.bat
echo   2. scripts\drl_legacy_cloud_setup.bat
echo   3. scripts\drl_appengine_publish.bat or scripts\drl_legacy_cloudrun_publish.bat
exit /b 0
