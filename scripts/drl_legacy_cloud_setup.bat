@echo off
setlocal
call "%~dp0drl_cloud_env.bat"

echo.
echo ==== DRL Cloud Setup ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo AE Loc  : %APP_ENGINE_LOCATION%
echo Repo    : %REPO_NAME%
echo Bucket  : %BUCKET_NAME%

echo.
echo ^> gcloud services enable appengine.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com logging.googleapis.com iam.googleapis.com iamcredentials.googleapis.com serviceusage.googleapis.com compute.googleapis.com run.googleapis.com --project="%PROJECT_ID%"
call gcloud services enable appengine.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com logging.googleapis.com iam.googleapis.com iamcredentials.googleapis.com serviceusage.googleapis.com compute.googleapis.com run.googleapis.com --project="%PROJECT_ID%"
if errorlevel 1 goto :fail

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
