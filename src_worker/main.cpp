#include "d3d12_dlssnr.h"
#include "image_io.h"
#include <iostream>
#include <string>
#include <chrono>

std::string Utf8Encode(const std::wstring& wstr) {
    if (wstr.empty()) return std::string();
    int sizeNeeded = WideCharToMultiByte(CP_UTF8, 0, &wstr[0], (int)wstr.size(), NULL, 0, NULL, NULL);
    std::string strTo(sizeNeeded, 0);
    WideCharToMultiByte(CP_UTF8, 0, &wstr[0], (int)wstr.size(), &strTo[0], sizeNeeded, NULL, NULL);
    return strTo;
}

int wmain(int argc, wchar_t* argv[]) {
    try {
        std::wstring inputPath;
        std::wstring outputPath;
        std::wstring dllPath;
        std::wstring proxyPath;
        std::wstring driverPath;

        DLSSNRParams params;
        unsigned int explicitWidth = 0;
        unsigned int explicitHeight = 0;
        bool checkOnly = false;
        bool validateModel = false;

        // Parse CLI arguments
        for (int i = 1; i < argc; ++i) {
            std::wstring arg = argv[i];
            if (arg == L"--input" && i + 1 < argc) {
                inputPath = argv[++i];
            } else if (arg == L"--output" && i + 1 < argc) {
                outputPath = argv[++i];
            } else if (arg == L"--width" && i + 1 < argc) {
                explicitWidth = static_cast<unsigned int>(std::stoul(argv[++i]));
            } else if (arg == L"--height" && i + 1 < argc) {
                explicitHeight = static_cast<unsigned int>(std::stoul(argv[++i]));
            } else if (arg == L"--intensity" && i + 1 < argc) {
                params.intensity = std::stof(argv[++i]);
            } else if (arg == L"--style" && i + 1 < argc) {
                params.style = std::stoi(argv[++i]);
            } else if (arg == L"--local-tone" && i + 1 < argc) {
                params.localTone = std::stof(argv[++i]);
            } else if (arg == L"--local-struct" && i + 1 < argc) {
                params.localStruct = std::stof(argv[++i]);
            } else if (arg == L"--skin-struct" && i + 1 < argc) {
                params.skinStruct = std::stof(argv[++i]);
            } else if (arg == L"--shadow-struct" && i + 1 < argc) {
                params.shadowStruct = std::stof(argv[++i]);
            } else if (arg == L"--reflection-glow" && i + 1 < argc) {
                params.reflectionGlow = std::stof(argv[++i]);
            } else if (arg == L"--residual-mult" && i + 1 < argc) {
                params.residualMult = std::stof(argv[++i]);
            } else if (arg == L"--residual-sat" && i + 1 < argc) {
                params.residualSat = std::stof(argv[++i]);
            } else if (arg == L"--residual-light" && i + 1 < argc) {
                params.residualLight = std::stof(argv[++i]);
            } else if (arg == L"--auto-mask" && i + 1 < argc) {
                params.autoMask = std::stoi(argv[++i]);
            } else if (arg == L"--ui-correction" && i + 1 < argc) {
                params.uiCorrection = std::stoi(argv[++i]);
            } else if (arg == L"--dll-path" && i + 1 < argc) {
                dllPath = argv[++i];
            } else if (arg == L"--proxy-path" && i + 1 < argc) {
                proxyPath = argv[++i];
            } else if (arg == L"--driver-path" && i + 1 < argc) {
                driverPath = argv[++i];
            } else if (arg == L"--check") {
                checkOnly = true;
            } else if (arg == L"--validate-model") {
                validateModel = true;
            }
        }

        D3D12DLSSNRRunner runner;
        if (!runner.Initialize(dllPath, proxyPath, driverPath)) {
            std::cout << "{\"status\": \"error\", \"error\": \"" << runner.GetErrorMessage() << "\"}" << std::endl;
            return 1;
        }

        if (checkOnly) {
            if (validateModel) {
                std::string valErr;
                if (!runner.ValidateModel(&valErr)) {
                    std::cout << "{\"status\": \"error\", \"error\": \"" << valErr << "\", \"gpu\": \"" << Utf8Encode(runner.GetGpuName()) << "\"}" << std::endl;
                    std::cout.flush();
                    TerminateProcess(GetCurrentProcess(), 1);
                }
            }
            std::cout << "{\"status\": \"ok\", \"gpu\": \"" << Utf8Encode(runner.GetGpuName()) << "\"}" << std::endl;
            std::cout.flush();
            return 0;
        }

        if (inputPath.empty() || outputPath.empty()) {
            std::cout << "{\"status\": \"error\", \"error\": \"Missing --input or --output argument\"}" << std::endl;
            return 2;
        }

        auto startTime = std::chrono::high_resolution_clock::now();

        // 1. Load input image
        ImageBuffer inImg;
        if (!LoadImageFromFile(inputPath, inImg, explicitWidth, explicitHeight)) {
            std::cout << "{\"status\": \"error\", \"error\": \"Failed to load input image: " << Utf8Encode(inputPath) << "\"}" << std::endl;
            return 3;
        }

    params.width = inImg.width;
    params.height = inImg.height;

    ImageBuffer outImg;
    outImg.width = inImg.width;
    outImg.height = inImg.height;
    outImg.dataUint8.resize((size_t)inImg.width * inImg.height * 4);
    outImg.dataFloat.resize((size_t)inImg.width * inImg.height * 4);

    // 2. Execute on Tensor Core via D3D12
    if (!runner.Execute(inImg.dataUint8.data(), outImg.dataUint8.data(), params)) {
        std::cout << "{\"status\": \"error\", \"error\": \"" << runner.GetErrorMessage() << "\"}" << std::endl;
        return 4;
    }

    // Convert outUint8 to outFloat, preserving HDR dynamic range above 1.0
    size_t totalBytes = (size_t)outImg.width * outImg.height * 4;
    for (size_t i = 0; i < totalBytes; ++i) {
        float inVal = inImg.dataFloat[i];
        float outVal = static_cast<float>(outImg.dataUint8[i]) / 255.0f;
        if (inVal > 1.0f) {
            outVal += (inVal - 1.0f);
        }
        outImg.dataFloat[i] = outVal;
    }

    // 3. Apply residual controls (if configured)
    ApplyResidualControls(
        outImg,
        inImg,
        params.residualMult,
        params.residualSat,
        params.residualLight,
        params.shadowStruct,
        params.reflectionGlow
    );

    // 4. Save output image
    if (!SaveImageToFile(outputPath, outImg)) {
        std::cout << "{\"status\": \"error\", \"error\": \"Failed to save output image: " << Utf8Encode(outputPath) << "\"}" << std::endl;
        return 5;
    }

    auto endTime = std::chrono::high_resolution_clock::now();
    double elapsedMs = std::chrono::duration<double, std::milli>(endTime - startTime).count();

    std::cout << "{\"status\": \"ok\", \"gpu\": \"" << Utf8Encode(runner.GetGpuName()) 
              << "\", \"width\": " << params.width 
              << ", \"height\": " << params.height 
              << ", \"time_ms\": " << elapsedMs << "}" << std::endl;

    return 0;
    } catch (const std::exception& e) {
        std::cout << "{\"status\": \"error\", \"error\": \"Exception: " << e.what() << "\"}" << std::endl;
        return 99;
    } catch (...) {
        std::cout << "{\"status\": \"error\", \"error\": \"Unknown fatal exception in worker\"}" << std::endl;
        return 100;
    }
}
