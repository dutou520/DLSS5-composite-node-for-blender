#include "d3d12_dlssnr.h"
#include <filesystem>
#include <iostream>

#pragma comment(lib, "d3d12.lib")
#pragma comment(lib, "dxgi.lib")

namespace fs = std::filesystem;

D3D12DLSSNRRunner::D3D12DLSSNRRunner() {
    wchar_t tempDir[MAX_PATH] = {};
    GetTempPathW(MAX_PATH, tempDir);
    m_appDataPath = tempDir;
}

D3D12DLSSNRRunner::~D3D12DLSSNRRunner() {
    if (m_params && m_pfnDestroyParams) {
        try {
            m_pfnDestroyParams(m_params);
        } catch (...) {}
        m_params = nullptr;
    }
    if (m_fenceEvent) {
        CloseHandle(m_fenceEvent);
        m_fenceEvent = nullptr;
    }
    m_cmdList.Reset();
    m_allocator.Reset();
    m_fence.Reset();
    m_queue.Reset();
    m_device.Reset();

    // Do not call FreeLibrary on driver/proxy DLLs during worker process exit.
    // NVIDIA NGX driver maintains internal worker threads and TLS hooks;
    // explicit FreeLibrary after failed feature creation triggers access violations in driver teardown.
    // The OS safely reclaims all DLLs upon process exit.
    m_hProxyDll = nullptr;
    m_hDriverNvngx = nullptr;
}

std::wstring D3D12DLSSNRRunner::FindDriverNvngxPath() {
    // 1. Direct path on this system
    const wchar_t* primary = L"C:\\Windows\\System32\\DriverStore\\FileRepository\\nvami.inf_amd64_97bcbdbdb2ab507c\\nvngx.dll";
    if (fs::exists(primary)) return primary;

    // 2. Search DriverStore
    try {
        const std::wstring base = L"C:\\Windows\\System32\\DriverStore\\FileRepository";
        if (fs::exists(base)) {
            for (const auto& entry : fs::directory_iterator(base)) {
                if (entry.is_directory()) {
                    std::wstring candidate = entry.path().wstring() + L"\\nvngx.dll";
                    if (fs::exists(candidate)) {
                        return candidate;
                    }
                }
            }
        }
    } catch (...) {}

    // 3. System32 fallback
    const wchar_t* sys32 = L"C:\\Windows\\System32\\nvngx.dll";
    if (fs::exists(sys32)) return sys32;

    return L"";
}

std::wstring D3D12DLSSNRRunner::FindDlssnrDllPath() {
    wchar_t exePath[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    fs::path dir = fs::path(exePath).parent_path();

    std::vector<fs::path> candidates = {
        dir / L"nvngx_dlssnr.dll",
        dir / L"dlls" / L"nvngx_dlssnr.dll",
        dir.parent_path() / L"dlls" / L"nvngx_dlssnr.dll",
        L"D:\\Download\\Other\\Magpie-Experimental-x64\\Magpie-Experimental-x64\\nvngx_dlssnr.dll"
    };

    for (const auto& p : candidates) {
        if (fs::exists(p)) return p.wstring();
    }
    return L"";
}

std::wstring D3D12DLSSNRRunner::FindProxyDllPath() {
    wchar_t exePath[MAX_PATH] = {};
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    fs::path dir = fs::path(exePath).parent_path();

    std::vector<fs::path> candidates = {
        dir / L"nvngx.dll_dlssnr.dll",
        dir / L"dlls" / L"nvngx.dll_dlssnr.dll",
        dir.parent_path() / L"dlls" / L"nvngx.dll_dlssnr.dll",
        L"D:\\Download\\Other\\Magpie-Experimental-x64\\Magpie-Experimental-x64\\nvngx.dll_dlssnr.dll"
    };

    for (const auto& p : candidates) {
        if (fs::exists(p)) return p.wstring();
    }
    return L"";
}

bool D3D12DLSSNRRunner::FindNvidiaAdapter(IDXGIFactory4* factory, IDXGIAdapter1** outAdapter) {
    IDXGIAdapter1* adapter = nullptr;
    IDXGIAdapter1* nvidiaAdapter = nullptr;

    for (UINT i = 0; factory->EnumAdapters1(i, &adapter) != DXGI_ERROR_NOT_FOUND; ++i) {
        DXGI_ADAPTER_DESC1 desc;
        adapter->GetDesc1(&desc);
        if (wcsstr(desc.Description, L"NVIDIA") || wcsstr(desc.Description, L"RTX")) {
            m_gpuName = desc.Description;
            nvidiaAdapter = adapter;
            break;
        }
        adapter->Release();
    }

    if (nvidiaAdapter) {
        *outAdapter = nvidiaAdapter;
        return true;
    }
    return false;
}

bool D3D12DLSSNRRunner::Initialize(
    const std::wstring& customDlssnrPath,
    const std::wstring& customProxyPath,
    const std::wstring& customDriverPath
) {
    // 1. Locate libraries
    m_dlssnrDllPath = customDlssnrPath.empty() ? FindDlssnrDllPath() : customDlssnrPath;
    m_proxyDllPath = customProxyPath.empty() ? FindProxyDllPath() : customProxyPath;
    std::wstring driverPath = customDriverPath.empty() ? FindDriverNvngxPath() : customDriverPath;

    if (m_dlssnrDllPath.empty() || !fs::exists(m_dlssnrDllPath)) {
        m_lastError = "Cannot find nvngx_dlssnr.dll!";
        return false;
    }
    if (m_proxyDllPath.empty() || !fs::exists(m_proxyDllPath)) {
        m_lastError = "Cannot find proxy nvngx.dll_dlssnr.dll!";
        return false;
    }
    if (driverPath.empty() || !fs::exists(driverPath)) {
        m_lastError = "Cannot find NVIDIA driver nvngx.dll!";
        return false;
    }

    // 2. Load driver nvngx.dll for parameter management
    m_hDriverNvngx = LoadLibraryW(driverPath.c_str());
    if (!m_hDriverNvngx) {
        m_lastError = "Failed to load driver nvngx.dll (error: " + std::to_string(GetLastError()) + ")";
        return false;
    }
    m_pfnAllocateParams = (int(*)(void**))GetProcAddress(m_hDriverNvngx, "NVSDK_NGX_D3D12_AllocateParameters");
    m_pfnDestroyParams = (int(*)(void*))GetProcAddress(m_hDriverNvngx, "NVSDK_NGX_D3D12_DestroyParameters");
    if (!m_pfnAllocateParams) {
        m_lastError = "Driver nvngx.dll missing NVSDK_NGX_D3D12_AllocateParameters";
        return false;
    }

    int allocRes = m_pfnAllocateParams(&m_params);
    if (allocRes != 1 || !m_params) {
        m_lastError = "NVSDK_NGX_D3D12_AllocateParameters failed (result: " + std::to_string(allocRes) + ")";
        return false;
    }

    // 3. Load proxy DLL
    m_hProxyDll = LoadLibraryW(m_proxyDllPath.c_str());
    if (!m_hProxyDll) {
        m_lastError = "Failed to load proxy DLL (error: " + std::to_string(GetLastError()) + ")";
        return false;
    }

    m_pfnCreate = (decltype(m_pfnCreate))GetProcAddress(m_hProxyDll, "dlssnr_call_create");
    m_pfnEvaluate = (decltype(m_pfnEvaluate))GetProcAddress(m_hProxyDll, "dlssnr_call_evaluate");
    m_pfnRelease = (decltype(m_pfnRelease))GetProcAddress(m_hProxyDll, "dlssnr_call_release");
    m_pfnSetFloatSlot = (decltype(m_pfnSetFloatSlot))GetProcAddress(m_hProxyDll, "dlssnr_call_set_float_slot");
    m_pfnLastInit = (int*)GetProcAddress(m_hProxyDll, "dlssnr_call_last_init");
    m_pfnLastCreate = (int*)GetProcAddress(m_hProxyDll, "dlssnr_call_last_create");

    if (!m_pfnCreate || !m_pfnEvaluate || !m_pfnRelease) {
        m_lastError = "Proxy DLL exports are incomplete!";
        return false;
    }

    if (m_pfnSetFloatSlot) {
        m_pfnSetFloatSlot(2);
    }

    // 4. Initialize D3D12 Device on NVIDIA GPU
    ComPtr<IDXGIFactory4> factory;
    HRESULT hr = CreateDXGIFactory1(IID_PPV_ARGS(&factory));
    if (FAILED(hr)) {
        m_lastError = "CreateDXGIFactory1 failed (HRESULT: " + std::to_string(hr) + ")";
        return false;
    }

    IDXGIAdapter1* adapter = nullptr;
    if (!FindNvidiaAdapter(factory.Get(), &adapter)) {
        m_lastError = "No NVIDIA RTX GPU found!";
        return false;
    }

    hr = D3D12CreateDevice(adapter, D3D_FEATURE_LEVEL_12_0, IID_PPV_ARGS(&m_device));
    adapter->Release();
    if (FAILED(hr)) {
        m_lastError = "D3D12CreateDevice failed (HRESULT: " + std::to_string(hr) + ")";
        return false;
    }

    // 5. Create Command Queue & Allocator & List
    D3D12_COMMAND_QUEUE_DESC queueDesc = {};
    queueDesc.Type = D3D12_COMMAND_LIST_TYPE_DIRECT;
    hr = m_device->CreateCommandQueue(&queueDesc, IID_PPV_ARGS(&m_queue));
    if (FAILED(hr)) {
        m_lastError = "CreateCommandQueue failed";
        return false;
    }

    hr = m_device->CreateCommandAllocator(D3D12_COMMAND_LIST_TYPE_DIRECT, IID_PPV_ARGS(&m_allocator));
    if (FAILED(hr)) {
        m_lastError = "CreateCommandAllocator failed";
        return false;
    }

    hr = m_device->CreateCommandList(0, D3D12_COMMAND_LIST_TYPE_DIRECT, m_allocator.Get(), nullptr, IID_PPV_ARGS(&m_cmdList));
    if (FAILED(hr)) {
        m_lastError = "CreateCommandList failed";
        return false;
    }

    hr = m_device->CreateFence(0, D3D12_FENCE_FLAG_NONE, IID_PPV_ARGS(&m_fence));
    if (FAILED(hr)) {
        m_lastError = "CreateFence failed";
        return false;
    }

    m_fenceEvent = CreateEventW(nullptr, FALSE, FALSE, nullptr);
    if (!m_fenceEvent) {
        m_lastError = "CreateEventW failed";
        return false;
    }

    return true;
}

void D3D12DLSSNRRunner::WaitForGpu() {
    m_fenceValue++;
    m_queue->Signal(m_fence.Get(), m_fenceValue);
    m_fence->SetEventOnCompletion(m_fenceValue, m_fenceEvent);
    WaitForSingleObject(m_fenceEvent, INFINITE);
}

bool D3D12DLSSNRRunner::Execute(
    const uint8_t* inRGBA,
    uint8_t* outRGBA,
    const DLSSNRParams& params
) {
    if (!m_device || !m_pfnCreate || !m_pfnEvaluate) {
        m_lastError = "D3D12DLSSNRRunner not properly initialized";
        return false;
    }

    const UINT W = params.width;
    const UINT H = params.height;

    // Reset allocator and command list
    m_allocator->Reset();
    m_cmdList->Reset(m_allocator.Get(), nullptr);

    // Call dlssnr_call_create
    void* handle = m_pfnCreate(
        m_dlssnrDllPath.c_str(),
        m_appDataPath.c_str(),
        m_device.Get(),
        m_cmdList.Get(),
        m_params,
        W, H,
        0, // preset
        params.intensity,
        params.style,
        params.localStruct,
        params.localTone,
        params.skinStruct,
        params.autoMask,
        params.uiCorrection
    );

    if (!handle) {
        int initErr = m_pfnLastInit ? *m_pfnLastInit : 0;
        int createErr = m_pfnLastCreate ? *m_pfnLastCreate : 0;
        m_lastError = "dlssnr_call_create returned null! lastInit=0x" + std::to_string(initErr) +
                      " lastCreate=0x" + std::to_string(createErr);
        return false;
    }

    D3D12_HEAP_PROPERTIES defaultHeap = {};
    defaultHeap.Type = D3D12_HEAP_TYPE_DEFAULT;

    D3D12_HEAP_PROPERTIES uploadHeap = {};
    uploadHeap.Type = D3D12_HEAP_TYPE_UPLOAD;

    D3D12_HEAP_PROPERTIES readbackHeap = {};
    readbackHeap.Type = D3D12_HEAP_TYPE_READBACK;

    // Create 2D Color Texture
    D3D12_RESOURCE_DESC texDesc = {};
    texDesc.Dimension = D3D12_RESOURCE_DIMENSION_TEXTURE2D;
    texDesc.Width = W;
    texDesc.Height = H;
    texDesc.DepthOrArraySize = 1;
    texDesc.MipLevels = 1;
    texDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
    texDesc.SampleDesc.Count = 1;
    texDesc.Flags = D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS | D3D12_RESOURCE_FLAG_ALLOW_RENDER_TARGET;

    ComPtr<ID3D12Resource> colorTex;
    m_device->CreateCommittedResource(&defaultHeap, D3D12_HEAP_FLAG_NONE, &texDesc,
        D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&colorTex));

    ComPtr<ID3D12Resource> outTex;
    m_device->CreateCommittedResource(&defaultHeap, D3D12_HEAP_FLAG_NONE, &texDesc,
        D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&outTex));

    D3D12_RESOURCE_DESC mvecDesc = texDesc;
    mvecDesc.Format = DXGI_FORMAT_R16G16_FLOAT;
    ComPtr<ID3D12Resource> mvecTex;
    m_device->CreateCommittedResource(&defaultHeap, D3D12_HEAP_FLAG_NONE, &mvecDesc,
        D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&mvecTex));

    D3D12_RESOURCE_DESC depthDesc = texDesc;
    depthDesc.Format = DXGI_FORMAT_R32_FLOAT;
    ComPtr<ID3D12Resource> depthTex;
    m_device->CreateCommittedResource(&defaultHeap, D3D12_HEAP_FLAG_NONE, &depthDesc,
        D3D12_RESOURCE_STATE_COMMON, nullptr, IID_PPV_ARGS(&depthTex));

    // Upload & Readback Buffers
    D3D12_PLACED_SUBRESOURCE_FOOTPRINT footprint = {};
    UINT numRows = 0;
    UINT64 rowSizeInBytes = 0;
    UINT64 totalBytes = 0;
    m_device->GetCopyableFootprints(&texDesc, 0, 1, 0, &footprint, &numRows, &rowSizeInBytes, &totalBytes);

    D3D12_RESOURCE_DESC bufferDesc = {};
    bufferDesc.Dimension = D3D12_RESOURCE_DIMENSION_BUFFER;
    bufferDesc.Width = totalBytes;
    bufferDesc.Height = 1;
    bufferDesc.DepthOrArraySize = 1;
    bufferDesc.MipLevels = 1;
    bufferDesc.SampleDesc.Count = 1;
    bufferDesc.Layout = D3D12_TEXTURE_LAYOUT_ROW_MAJOR;

    ComPtr<ID3D12Resource> uploadBuf;
    m_device->CreateCommittedResource(&uploadHeap, D3D12_HEAP_FLAG_NONE, &bufferDesc,
        D3D12_RESOURCE_STATE_GENERIC_READ, nullptr, IID_PPV_ARGS(&uploadBuf));

    ComPtr<ID3D12Resource> readbackBuf;
    m_device->CreateCommittedResource(&readbackHeap, D3D12_HEAP_FLAG_NONE, &bufferDesc,
        D3D12_RESOURCE_STATE_COPY_DEST, nullptr, IID_PPV_ARGS(&readbackBuf));

    // Copy input pixels to upload buffer row-by-row
    uint8_t* pUploadData = nullptr;
    uploadBuf->Map(0, nullptr, (void**)&pUploadData);
    for (UINT y = 0; y < H; ++y) {
        uint8_t* dstRow = pUploadData + footprint.Offset + y * footprint.Footprint.RowPitch;
        const uint8_t* srcRow = inRGBA + y * (W * 4);
        memcpy(dstRow, srcRow, W * 4);
    }
    uploadBuf->Unmap(0, nullptr);

    // Record copy from upload buffer to color texture
    D3D12_TEXTURE_COPY_LOCATION srcLoc = {};
    srcLoc.pResource = uploadBuf.Get();
    srcLoc.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    srcLoc.PlacedFootprint = footprint;

    D3D12_TEXTURE_COPY_LOCATION dstLoc = {};
    dstLoc.pResource = colorTex.Get();
    dstLoc.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    dstLoc.SubresourceIndex = 0;

    m_cmdList->CopyTextureRegion(&dstLoc, 0, 0, 0, &srcLoc, nullptr);

    // Transition colorTex to COMMON state
    D3D12_RESOURCE_BARRIER barrier = {};
    barrier.Type = D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;
    barrier.Transition.pResource = colorTex.Get();
    barrier.Transition.Subresource = D3D12_RESOURCE_BARRIER_ALL_SUBRESOURCES;
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COPY_DEST;
    barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COMMON;
    m_cmdList->ResourceBarrier(1, &barrier);

    // Evaluate DLSSNR on Tensor Core
    int evalRes = m_pfnEvaluate(
        m_cmdList.Get(),
        handle,
        m_params,
        colorTex.Get(),
        depthTex.Get(),
        mvecTex.Get(),
        outTex.Get(),
        W, H,
        W, H,
        0, // depthInverted
        1, // reset
        params.intensity,
        params.style,
        params.localStruct,
        params.localTone,
        params.skinStruct,
        params.autoMask,
        1.0f, 1.0f
    );

    if (evalRes != 1) {
        m_lastError = "dlssnr_call_evaluate failed with code 0x" + std::to_string(evalRes);
        m_pfnRelease(handle);
        return false;
    }

    // Transition outTex to COPY_SOURCE
    barrier.Transition.pResource = outTex.Get();
    barrier.Transition.StateBefore = D3D12_RESOURCE_STATE_COMMON;
    barrier.Transition.StateAfter = D3D12_RESOURCE_STATE_COPY_SOURCE;
    m_cmdList->ResourceBarrier(1, &barrier);

    // Copy outTex to readback buffer
    D3D12_TEXTURE_COPY_LOCATION readSrcLoc = {};
    readSrcLoc.pResource = outTex.Get();
    readSrcLoc.Type = D3D12_TEXTURE_COPY_TYPE_SUBRESOURCE_INDEX;
    readSrcLoc.SubresourceIndex = 0;

    D3D12_TEXTURE_COPY_LOCATION readDstLoc = {};
    readDstLoc.pResource = readbackBuf.Get();
    readDstLoc.Type = D3D12_TEXTURE_COPY_TYPE_PLACED_FOOTPRINT;
    readDstLoc.PlacedFootprint = footprint;

    m_cmdList->CopyTextureRegion(&readDstLoc, 0, 0, 0, &readSrcLoc, nullptr);

    // Close and execute command list
    m_cmdList->Close();
    ID3D12CommandList* ppCommandLists[] = { m_cmdList.Get() };
    m_queue->ExecuteCommandLists(1, ppCommandLists);

    WaitForGpu();

    // Readback pixels row-by-row
    uint8_t* pReadbackData = nullptr;
    readbackBuf->Map(0, nullptr, (void**)&pReadbackData);
    for (UINT y = 0; y < H; ++y) {
        const uint8_t* srcRow = pReadbackData + footprint.Offset + y * footprint.Footprint.RowPitch;
        uint8_t* dstRow = outRGBA + y * (W * 4);
        memcpy(dstRow, srcRow, W * 4);
    }
    readbackBuf->Unmap(0, nullptr);

    // Release feature handle
    m_pfnRelease(handle);

    return true;
}

bool D3D12DLSSNRRunner::ValidateModel(std::string* outError) {
    if (!m_device || !m_pfnCreate || !m_pfnRelease) {
        if (outError) *outError = "Worker not initialized";
        return false;
    }
    m_allocator->Reset();
    m_cmdList->Reset(m_allocator.Get(), nullptr);

    void* handle = m_pfnCreate(
        m_dlssnrDllPath.c_str(),
        m_appDataPath.c_str(),
        m_device.Get(),
        m_cmdList.Get(),
        m_params,
        128, 128,
        0, // preset
        1.0f,
        0,
        1.0f,
        1.0f,
        0.0f,
        0,
        1
    );

    if (!handle) {
        int initErr = m_pfnLastInit ? *m_pfnLastInit : 0;
        int createErr = m_pfnLastCreate ? *m_pfnLastCreate : 0;
        std::string desc;
        if (createErr == -1160773630 || createErr == -1160773631 || (unsigned int)createErr == 0xBAE00002 || (unsigned int)createErr == 0xBAE00001) {
            desc = "Model DLL is not compatible with current GPU (FeatureNotSupported: requires newer generation RTX Tensor Core architecture)";
        } else {
            desc = "dlssnr_call_create returned null! lastInit=0x" + std::to_string(initErr) +
                   " lastCreate=0x" + std::to_string(createErr);
        }
        if (outError) *outError = desc;
        m_lastError = desc;
        return false;
    }

    m_pfnRelease(handle);
    return true;
}
