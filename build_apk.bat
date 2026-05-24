@echo off
echo ========================================
echo   Building Lazy Boy APK
echo ========================================
echo.
echo Buildozer requires Linux. Choose method:
echo.
echo   1. WSL (Windows Subsystem for Linux)
echo   2. Docker
echo   3. Exit
echo.
set /p choice="Select (1/2/3): "

if "%choice%"=="1" goto wsl
if "%choice%"=="2" goto docker
exit /b

:wsl
echo.
echo [*] Building via WSL...
wsl bash -c "cd /mnt/c/Users/AriaS/Desktop/Lazy-Boy-thptpcc-phone-to-PC-controller/android && pip install buildozer cython && buildozer android debug"
echo.
echo [*] APK should be in android/bin/
pause
exit /b

:docker
echo.
echo [*] Building via Docker...
docker run --rm -v "%cd%\android:/home/user/hostcwd" -v "%USERPROFILE%\.buildozer:/home/user/.buildozer" kivy/buildozer android debug
echo.
echo [*] APK should be in android/bin/
pause
exit /b
