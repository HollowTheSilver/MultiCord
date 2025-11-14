@echo off
REM MultiCord CLI - PyPI Publishing Script for Windows
REM This script builds and publishes the MultiCord CLI to PyPI

echo ==========================================
echo MultiCord CLI - PyPI Publishing Script
echo ==========================================
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    exit /b 1
)

REM Install/update build tools
echo [INFO] Installing/updating build tools...
pip install --upgrade build twine

REM Clean previous builds
echo [INFO] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist multicord.egg-info rmdir /s /q multicord.egg-info

REM Build the package
echo [INFO] Building the package...
python -m build

if not exist dist (
    echo [ERROR] Build failed - no distribution files created
    exit /b 1
)

echo [INFO] Package built successfully!
dir dist

REM Check the package
echo [INFO] Checking the package with twine...
twine check dist\*

REM Upload options
echo.
set /p testpypi="Upload to Test PyPI first? (recommended) [y/n]: "
if /i "%testpypi%"=="y" (
    echo [INFO] Uploading to Test PyPI...
    twine upload --repository testpypi dist\*

    echo.
    echo [INFO] Package uploaded to Test PyPI!
    echo Test installation with:
    echo   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ multicord
    echo.

    set /p continue="Continue with production PyPI upload? [y/n]: "
    if /i not "%continue%"=="y" (
        echo [INFO] Stopping here. Test your package and run this script again for production upload.
        exit /b 0
    )
)

REM Upload to PyPI
echo.
echo [WARNING] Ready to upload to PyPI. This action cannot be undone!
echo.
echo Please ensure:
echo   1. You have a PyPI account
echo   2. You have configured your PyPI API token
echo   3. The version number is correct
echo   4. You have tested the package
echo.
set /p confirm="Continue with upload to PyPI? (type 'yes' to confirm): "

if /i "%confirm%"=="yes" (
    echo [INFO] Uploading to PyPI...
    twine upload dist\*

    echo.
    echo ==========================================
    echo [SUCCESS] Package uploaded to PyPI!
    echo ==========================================
    echo.
    echo Users can now install with:
    echo   pip install multicord
    echo.
    echo View your package at:
    echo   https://pypi.org/project/multicord/
    echo.
) else (
    echo [INFO] Upload cancelled
    exit /b 0
)

echo Post-upload recommendations:
echo.
echo 1. Create a GitHub release with the same version number
echo 2. Update the documentation
echo 3. Announce the release on Discord communities
echo 4. Monitor for issues at GitHub
echo.

pause