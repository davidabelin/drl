@echo off
setlocal
call "%~dp0drl_cloud_env.bat"

echo.
echo ==== DRL Cloud Bootstrap ====
echo Project : %PROJECT_ID%
echo Region  : %REGION%
echo Repo    : %REPO_NAME%
echo Bucket  : %BUCKET_NAME%

echo.
echo ^> gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com logging.googleapis.com iam.googleapis.com iamcredentials.googleapis.com serviceusage.googleapis.com --project="%PROJECT_ID%"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com storage.googleapis.com logging.googleapis.com iam.googleapis.com iamcredentials.googleapis.com serviceusage.googleapis.com --project="%PROJECT_ID%"
if errorlevel 1 goto :fail

echo.
echo ^> gcloud artifacts repositories describe %REPO_NAME% --location="%REGION%" --project="%PROJECT_ID%"
gcloud artifacts repositories describe %REPO_NAME% --location="%REGION%" --project="%PROJECT_ID%" >nul 2>&1
if errorlevel 1 (
  echo.
  echo ^> gcloud artifacts repositories create %REPO_NAME% --project="%PROJECT_ID%" --location="%REGION%" --repository-format=docker --description="DRL web containers"
  gcloud artifacts repositories create %REPO_NAME% --project="%PROJECT_ID%" --location="%REGION%" --repository-format=docker --description="DRL web containers"
  if errorlevel 1 goto :fail
) else (
  echo [OK] Artifact Registry repository already exists: %REPO_NAME%
)

echo.
echo ^> gcloud storage buckets describe gs://%BUCKET_NAME%
gcloud storage buckets describe gs://%BUCKET_NAME% >nul 2>&1
if errorlevel 1 (
  echo.
  echo ^> gcloud storage buckets create gs://%BUCKET_NAME% --project="%PROJECT_ID%" --location="%REGION%" --uniform-bucket-level-access
  gcloud storage buckets create gs://%BUCKET_NAME% --project="%PROJECT_ID%" --location="%REGION%" --uniform-bucket-level-access
  if errorlevel 1 goto :fail
) else (
  echo [OK] Storage bucket already exists: gs://%BUCKET_NAME%
)

echo.
echo ^> gcloud artifacts repositories list --project="%PROJECT_ID%" --location=all
gcloud artifacts repositories list --project="%PROJECT_ID%" --location=all
if errorlevel 1 goto :fail
echo.
echo ^> gcloud storage buckets describe gs://%BUCKET_NAME% --format="yaml(name,location,locationType,storageClass,iamConfiguration)"
gcloud storage buckets describe gs://%BUCKET_NAME% --format="yaml(name,location,locationType,storageClass,iamConfiguration)"
if errorlevel 1 goto :fail

echo.
echo [OK] Bootstrap finished.
endlocal
exit /b 0

:fail
echo.
echo [ERROR] Bootstrap failed.
endlocal
exit /b 1
