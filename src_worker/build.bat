@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo Building DLSS5 Worker for Blender 3.6 (RTX 3060 D3D12)
echo =======================================================

call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
if errorlevel 1 (
    echo Error: Failed to initialize Visual Studio build environment!
    exit /b 1
)

cd /d "%~dp0"

if not exist "..\bin" mkdir "..\bin"
if not exist "..\dlss5_blender\bin" mkdir "..\dlss5_blender\bin"

cl /EHsc /O2 /std:c++20 main.cpp d3d12_dlssnr.cpp /link /out:"..\bin\dlss5_worker.exe" d3d12.lib dxgi.lib
if errorlevel 1 (
    echo Build failed!
    exit /b 1
)

echo Build succeeded!
copy /Y "..\bin\dlss5_worker.exe" "..\dlss5_blender\bin\dlss5_worker.exe"

echo Binary deployed to dlss5_blender\bin\dlss5_worker.exe
exit /b 0
