@echo off
echo Building log-intelligence-api with Podman...

REM Clean up any existing containers/images
podman rmi -f localhost/log-intelligence-api:latest >nul 2>&1
podman rmi -f localhost/log-intelligence-worker:latest >nul 2>&1

REM Create a temporary build directory with only necessary files
echo Preparing build context...
set TEMP_BUILD_DIR=%TEMP%\log-intelligence-build-%RANDOM%
mkdir "%TEMP_BUILD_DIR%"
mkdir "%TEMP_BUILD_DIR%\src"
mkdir "%TEMP_BUILD_DIR%\docker"

REM Copy only necessary files
copy requirements.txt "%TEMP_BUILD_DIR%\" >nul
copy pyproject.toml "%TEMP_BUILD_DIR%\" >nul
copy README.md "%TEMP_BUILD_DIR%\" >nul
copy LICENSE "%TEMP_BUILD_DIR%\" >nul 2>&1
xcopy /E /I src\* "%TEMP_BUILD_DIR%\src\" >nul
copy docker\Dockerfile.api "%TEMP_BUILD_DIR%\Dockerfile" >nul

REM Build from the temporary directory
echo Building from optimized context...
cd /d "%TEMP_BUILD_DIR%"
podman build -t localhost/log-intelligence-api:latest -f Dockerfile .

REM Cleanup
cd /d "%~dp0"
rmdir /S /Q "%TEMP_BUILD_DIR%"

echo Build completed!
podman images | findstr log-intelligence
