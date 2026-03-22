@echo off
setlocal
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
