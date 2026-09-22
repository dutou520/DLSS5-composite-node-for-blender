#pragma once

#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <algorithm>
#include <cmath>
#include <filesystem>

#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include "stb_image_write.h"

struct ImageBuffer {
    unsigned int width = 0;
    unsigned int height = 0;
    // RGBA float32 in range [0.0, 1.0+]
    std::vector<float> dataFloat;
    // RGBA uint8 in range [0, 255]
    std::vector<uint8_t> dataUint8;
};

inline bool EndsWithCaseInsensitive(const std::wstring& str, const std::wstring& suffix) {
    if (str.length() < suffix.length()) return false;
    std::wstring s1 = str.substr(str.length() - suffix.length());
    std::wstring s2 = suffix;
    std::transform(s1.begin(), s1.end(), s1.begin(), ::towlower);
    std::transform(s2.begin(), s2.end(), s2.begin(), ::towlower);
    return s1 == s2;
}

inline bool LoadImageFromFile(const std::wstring& path, ImageBuffer& img, unsigned int reqWidth = 0, unsigned int reqHeight = 0) {
    if (EndsWithCaseInsensitive(path, L".raw") || EndsWithCaseInsensitive(path, L".bin")) {
        if (reqWidth == 0 || reqHeight == 0) {
            std::cerr << "Raw binary image requires explicit width and height!" << std::endl;
            return false;
        }
        std::ifstream file(path.c_str(), std::ios::binary);
        if (!file.is_open()) {
            std::cerr << "Cannot open raw input file" << std::endl;
            return false;
        }
        img.width = reqWidth;
        img.height = reqHeight;
        size_t numFloats = (size_t)reqWidth * reqHeight * 4;
        img.dataFloat.resize(numFloats);
        file.read(reinterpret_cast<char*>(img.dataFloat.data()), numFloats * sizeof(float));
        if (!file) {
            std::cerr << "Failed to read expected bytes from raw file" << std::endl;
            return false;
        }
        img.dataUint8.resize(numFloats);
        for (size_t i = 0; i < numFloats; ++i) {
            float val = std::clamp(img.dataFloat[i], 0.0f, 1.0f);
            img.dataUint8[i] = static_cast<uint8_t>(val * 255.0f + 0.5f);
        }
        return true;
    }

    FILE* f = _wfopen(path.c_str(), L"rb");
    if (!f) {
        std::cerr << "Cannot open image file" << std::endl;
        return false;
    }
    int w = 0, h = 0, channels = 0;
    stbi_uc* pixels = stbi_load_from_file(f, &w, &h, &channels, 4);
    fclose(f);
    if (!pixels) {
        std::cerr << "stbi_load_from_file failed: " << stbi_failure_reason() << std::endl;
        return false;
    }

    img.width = static_cast<unsigned int>(w);
    img.height = static_cast<unsigned int>(h);
    size_t totalBytes = (size_t)w * h * 4;
    img.dataUint8.assign(pixels, pixels + totalBytes);
    stbi_image_free(pixels);

    img.dataFloat.resize(totalBytes);
    for (size_t i = 0; i < totalBytes; ++i) {
        img.dataFloat[i] = static_cast<float>(img.dataUint8[i]) / 255.0f;
    }
    return true;
}

inline bool SaveImageToFile(const std::wstring& path, const ImageBuffer& img) {
    if (EndsWithCaseInsensitive(path, L".raw") || EndsWithCaseInsensitive(path, L".bin")) {
        std::ofstream file(path.c_str(), std::ios::binary);
        if (!file.is_open()) {
            std::cerr << "Cannot open raw output file" << std::endl;
            return false;
        }
        file.write(reinterpret_cast<const char*>(img.dataFloat.data()), img.dataFloat.size() * sizeof(float));
        return true;
    }

    FILE* f = _wfopen(path.c_str(), L"wb");
    if (!f) {
        std::cerr << "Cannot create output image file" << std::endl;
        return false;
    }
    struct FileContext {
        FILE* fp;
    } ctx = { f };
    auto writeFunc = [](void* context, void* data, int size) {
        fwrite(data, 1, size, static_cast<FileContext*>(context)->fp);
    };

    int res = 0;
    if (EndsWithCaseInsensitive(path, L".bmp")) {
        res = stbi_write_bmp_to_func(writeFunc, &ctx, static_cast<int>(img.width), static_cast<int>(img.height), 4, img.dataUint8.data());
    } else if (EndsWithCaseInsensitive(path, L".tga")) {
        res = stbi_write_tga_to_func(writeFunc, &ctx, static_cast<int>(img.width), static_cast<int>(img.height), 4, img.dataUint8.data());
    } else {
        // Default to PNG
        res = stbi_write_png_to_func(writeFunc, &ctx, static_cast<int>(img.width), static_cast<int>(img.height),
                                    4, img.dataUint8.data(), static_cast<int>(img.width * 4));
    }
    fclose(f);
    return res != 0;
}

// Magpie aligned residual blend:
// residual = dlssnr_output - original_input
// adjusted_residual = residual * residual_mult
// saturation / lightness / shadow structure
inline void ApplyResidualControls(
    ImageBuffer& outImg,
    const ImageBuffer& inImg,
    float residualMult,
    float residualSat,
    float residualLight,
    float shadowStruct,
    float reflectionGlow
) {
    if (residualMult == 1.0f && residualSat == 1.0f && residualLight == 1.0f &&
        shadowStruct == 1.0f && reflectionGlow == 1.0f) {
        return;
    }

    size_t numPixels = (size_t)outImg.width * outImg.height;
    for (size_t i = 0; i < numPixels; ++i) {
        size_t idx = i * 4;
        float inR = inImg.dataFloat[idx + 0];
        float inG = inImg.dataFloat[idx + 1];
        float inB = inImg.dataFloat[idx + 2];
        float inA = inImg.dataFloat[idx + 3];

        float outR = outImg.dataFloat[idx + 0];
        float outG = outImg.dataFloat[idx + 1];
        float outB = outImg.dataFloat[idx + 2];

        float resR = outR - inR;
        float resG = outG - inG;
        float resB = outB - inB;

        // Apply residual multiplier
        resR *= residualMult;
        resG *= residualMult;
        resB *= residualMult;

        // Apply saturation & lightness on residual
        float resLum = 0.2126f * resR + 0.7152f * resG + 0.0722f * resB;
        resR = resLum * residualLight + (resR - resLum) * residualSat;
        resG = resLum * residualLight + (resG - resLum) * residualSat;
        resB = resLum * residualLight + (resB - resLum) * residualSat;

        // Shadow / reflection control based on input luminance
        float inLum = 0.2126f * inR + 0.7152f * inG + 0.0722f * inB;
        float shadowWeight = std::clamp(1.0f - inLum, 0.0f, 1.0f) * (shadowStruct - 1.0f);
        float glowWeight = std::clamp(inLum, 0.0f, 1.0f) * (reflectionGlow - 1.0f);
        float toneFactor = 1.0f + shadowWeight + glowWeight;

        float finalR = inR <= 1.0f ? std::clamp(inR + resR * toneFactor, 0.0f, 1.0f) : (inR + resR * toneFactor);
        float finalG = inG <= 1.0f ? std::clamp(inG + resG * toneFactor, 0.0f, 1.0f) : (inG + resG * toneFactor);
        float finalB = inB <= 1.0f ? std::clamp(inB + resB * toneFactor, 0.0f, 1.0f) : (inB + resB * toneFactor);

        outImg.dataFloat[idx + 0] = finalR;
        outImg.dataFloat[idx + 1] = finalG;
        outImg.dataFloat[idx + 2] = finalB;
        outImg.dataFloat[idx + 3] = inA;

        outImg.dataUint8[idx + 0] = static_cast<uint8_t>(finalR * 255.0f + 0.5f);
        outImg.dataUint8[idx + 1] = static_cast<uint8_t>(finalG * 255.0f + 0.5f);
        outImg.dataUint8[idx + 2] = static_cast<uint8_t>(finalB * 255.0f + 0.5f);
        outImg.dataUint8[idx + 3] = static_cast<uint8_t>(inA * 255.0f + 0.5f);
    }
}
