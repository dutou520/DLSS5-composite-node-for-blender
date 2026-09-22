@echo off
echo =======================================================
echo Building DLSS5 Worker for Blender 3.6 (RTX 3060 D3D12)
echo =======================================================

where cl >nul 2>nul
if %errorlevel% equ 0 goto COMPILE

if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" goto CALL_COMMUNITY
if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" goto CALL_PRO
if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" goto CALL_ENTERPRISE
goto CHECK_CL

:CALL_COMMUNITY
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
goto CHECK_CL

:CALL_PRO
call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat"
goto CHECK_CL

:CALL_ENTERPRISE
call "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat"
goto CHECK_CL

:CHECK_CL
where cl >nul 2>nul
if errorlevel 1 goto NO_CL
goto COMPILE

:NO_CL
echo Error: Failed to find MSVC compiler cl.exe. Please run from Developer Command Prompt or install Visual Studio with C++ tools.
exit /b 1

:COMPILE
cd /d "%~dp0"

if not exist "..\bin" mkdir "..\bin"
if not exist "..\dlss5_blender\bin" mkdir "..\dlss5_blender\bin"

cl /nologo /EHsc /O2 /std:c++20 main.cpp d3d12_dlssnr.cpp /link /nologo /out:"..\bin\dlss5_worker.exe" d3d12.lib dxgi.lib
if errorlevel 1 goto BUILD_FAIL

echo Build succeeded.
copy /Y "..\bin\dlss5_worker.exe" "..\dlss5_blender\bin\dlss5_worker.exe" >nul
if errorlevel 1 goto DEPLOY_FAIL

echo Binary deployed to dlss5_blender\bin\dlss5_worker.exe
exit /b 0

:BUILD_FAIL
echo Error: Build failed during cl compilation.
exit /b 1

:DEPLOY_FAIL
echo Error: Failed to copy binary to dlss5_blender\bin\dlss5_worker.exe. Please ensure the worker process is not currently running.
exit /b 1
