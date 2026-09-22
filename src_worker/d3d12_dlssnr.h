#pragma once

#include <windows.h>
#include <d3d12.h>
#include <dxgi1_6.h>
#include <wrl/client.h>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;

struct DLSSNRParams {
    unsigned int width = 1920;
    unsigned int height = 1080;
    float intensity = 1.0f;
    int style = 0;
    float localTone = 1.0f;
    float localStruct = 1.0f;
    float skinStruct = 0.0f;
    float shadowStruct = 1.0f;
    float reflectionGlow = 1.0f;
    float residualMult = 1.0f;
    float residualSat = 1.0f;
    float residualLight = 1.0f;
    int autoMask = 0;
    int uiCorrection = 0;
};

class D3D12DLSSNRRunner {
public:
    D3D12DLSSNRRunner();
    ~D3D12DLSSNRRunner();

    bool Initialize(
        const std::wstring& customDlssnrPath = L"",
        const std::wstring& customProxyPath = L"",
        const std::wstring& customDriverPath = L""
    );

    bool Execute(
        const uint8_t* inRGBA,
        uint8_t* outRGBA,
        const DLSSNRParams& params
    );

    bool ValidateModel(std::string* outError = nullptr);

    const std::string& GetErrorMessage() const { return m_lastError; }
    const std::wstring& GetGpuName() const { return m_gpuName; }

private:
    std::string m_lastError;
    std::wstring m_gpuName;

    HMODULE m_hDriverNvngx = nullptr;
    HMODULE m_hProxyDll = nullptr;

    ComPtr<ID3D12Device> m_device;
    ComPtr<ID3D12CommandQueue> m_queue;
    ComPtr<ID3D12CommandAllocator> m_allocator;
    ComPtr<ID3D12GraphicsCommandList> m_cmdList;
    ComPtr<ID3D12Fence> m_fence;
    HANDLE m_fenceEvent = nullptr;
    UINT64 m_fenceValue = 0;

    void* m_params = nullptr;

    void (*m_pfnSetFloatSlot)(unsigned int slot) = nullptr;
    void* (*m_pfnCreate)(
        const wchar_t* dllPath,
        const wchar_t* appDataPath,
        ID3D12Device* device,
        ID3D12GraphicsCommandList* cmdList,
        void* params,
        unsigned int width,
        unsigned int height,
        int preset,
        float intensity,
        int style,
        float localStruct,
        float localTone,
        float skinStruct,
        int autoMask,
        int uiCorrection
    ) = nullptr;

    int (*m_pfnEvaluate)(
        ID3D12GraphicsCommandList* cmdList,
        void* handle,
        void* params,
        ID3D12Resource* colorResource,
        ID3D12Resource* depthResource,
        ID3D12Resource* mvecResource,
        ID3D12Resource* outputResource,
        unsigned int width,
        unsigned int height,
        unsigned int mvecSubrectWidth,
        unsigned int mvecSubrectHeight,
        int depthInverted,
        int reset,
        float intensity,
        int style,
        float localStruct,
        float localTone,
        float skinStruct,
        int autoMask,
        float mvecScaleX,
        float mvecScaleY
    ) = nullptr;

    int (*m_pfnRelease)(void* handle) = nullptr;
    int* m_pfnLastInit = nullptr;
    int* m_pfnLastCreate = nullptr;
    int (*m_pfnAllocateParams)(void** outParams) = nullptr;
    int (*m_pfnDestroyParams)(void* params) = nullptr;

    std::wstring m_dlssnrDllPath;
    std::wstring m_proxyDllPath;
    std::wstring m_appDataPath;

    bool FindNvidiaAdapter(IDXGIFactory4* factory, IDXGIAdapter1** outAdapter);
    std::wstring FindDriverNvngxPath();
    std::wstring FindDlssnrDllPath();
    std::wstring FindProxyDllPath();
    void WaitForGpu();
};
