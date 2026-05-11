@echo off
if /i "%~1"=="--help" goto :help
if /i "%~1"=="-h" goto :help
if "%~1"=="/?" goto :help

setlocal
call "%~dp0drl_cloud_env.bat"

for %%I in ("%~dp0..") do set "DRL_ROOT=%%~fI"
for %%I in ("%~dp0..\..\rps") do set "RPS_ROOT=%%~fI"
for %%I in ("%~dp0..\..\c4") do set "C4_ROOT=%%~fI"

echo.
echo ==== DRL + Sister Labs Publish ====
echo Project : %PROJECT_ID%
echo DRL     : %DRL_ROOT%
echo RPS     : %RPS_ROOT%
echo C4      : %C4_ROOT%

if not exist "%RPS_ROOT%\app.drl.yaml" goto :missing_rps
if not exist "%C4_ROOT%\app.drl.yaml" goto :missing_c4

echo.
echo [1/3] Deploying RPS standalone service...
pushd "%RPS_ROOT%" >nul || goto :fail
call gcloud app deploy app.drl.yaml --project="%PROJECT_ID%" --quiet
if errorlevel 1 goto :fail_popd
popd >nul

echo.
echo [2/3] Deploying Connect4 standalone service...
pushd "%C4_ROOT%" >nul || goto :fail
call gcloud app deploy app.drl.yaml --project="%PROJECT_ID%" --quiet
if errorlevel 1 goto :fail_popd
popd >nul

echo.
echo [3/3] Deploying DRL default service...
pushd "%DRL_ROOT%" >nul || goto :fail
call gcloud app deploy app.yaml --project="%PROJECT_ID%" --quiet
if errorlevel 1 goto :fail_popd
popd >nul

echo.
echo [OK] DRL and sister lab publish finished.
echo DRL      https://deeprl-031026.wm.r.appspot.com/
echo RPS      https://rps-dot-deeprl-031026.wm.r.appspot.com/
echo Connect4 https://c4-dot-deeprl-031026.wm.r.appspot.com/
endlocal
exit /b 0

:missing_rps
echo.
echo [ERROR] Missing "%RPS_ROOT%\app.drl.yaml".
endlocal
exit /b 1

:missing_c4
echo.
echo [ERROR] Missing "%C4_ROOT%\app.drl.yaml".
endlocal
exit /b 1

:fail_popd
popd >nul

:fail
echo.
echo [ERROR] Publish failed.
echo Run scripts\drl_cloud_configure.bat first, then retry this script.
endlocal
exit /b 1

:help
echo.
echo DRL + Sister Labs Publish
echo.
echo Usage:
echo   scripts\drl_publish_with_sister_labs.bat
echo.
echo What it does:
echo   Deploys the standalone RPS and Connect4 App Engine services from sibling
echo   repos, then deploys DRL with buttons pointing to those service URLs.
echo.
echo Recommended order:
echo   1. scripts\drl_cloud_configure.bat
echo   2. scripts\drl_publish_with_sister_labs.bat
exit /b 0
