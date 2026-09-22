# DLSS 5 Neural Rendering Composite Node for Blender

<div align="center">

[![Blender 3.6+](https://img.shields.io/badge/Blender-3.6%20LTS%20%7C%204.x-orange.svg?logo=blender)](https://www.blender.org/)
[![NVIDIA RTX](https://img.shields.io/badge/NVIDIA%20RTX-20%20%7C%2030%20%7C%2040%20%7C%2050%20Series-76B900.svg?logo=nvidia)](https://www.nvidia.com/geforce/rtx/)
[![Direct3D 12](https://img.shields.io/badge/DirectX-Direct3D%2012%20Native-blue.svg?logo=windows)](https://microsoft.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v3.0.0-brightgreen.svg)](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases)

**原生 Direct3D 12 Tensor Core 硬件级神经渲染加速节点**  
*Native Direct3D 12 Tensor Core Hardware-Accelerated Neural Rendering Node for Blender*

[English](#english) | [中文说明](#chinese)

</div>

---

<a name="chinese"></a>
## 🇨🇳 中文说明 (Chinese)

### 1. 项目简介 (Overview)
**DLSS5 Composite Node for Blender** 是一款专为 Blender 打造的原生硬件级深度学习超分辨率与神经重建（Neural Rendering）插件。基于 NVIDIA 深度学习神经渲染（DLSS-NR, Feature ID 18）与原生 Direct3D 12 Tensor Core 硬件流水线，将原本耗时数十分钟的离线光线追踪降噪与画质重构过程缩短至毫秒级别，实现极致的逼真渲染与生产力提升。

### 2. 核心特性 (Key Features)
- **⚡ 原生 Direct3D 12 Tensor Core 硬件推理 (Native Hardware Inference)**:  
  采用纯 C++20 打造独立高并发 Worker 进程，直接调度 NVIDIA GPU 内部的物理 Tensor Core 单元，零中间解释层，性能损耗趋近于 0。
- **🎨 原生合成器节点单节点无缝级联 (Seamless Single Compositor Node)**:  
  提供标准的 `DLSS 5 神经渲染`（`CompositorNodeDLSS5`）原生合成器节点。自动装配 `Image`、`Depth`、`Vector (Motion)` 与 `Normal` 输入通道，与下游调色、色彩平衡（Color Balance）、眩光（Glare）及 Composite 输出节点无缝串联。
- **🎯 专有微架构优化 (Per-Architecture Tuning for RTX 20/30/40/50)**:  
  针对 Turing (RTX 20)、Ampere (RTX 30)、Ada Lovelace (RTX 40) 和 Blackwell (RTX 50) 架构进行独立模型调校与编译，释放每一代 Tensor Core（FP16/INT8/FP8/稀疏化）的最大物理算力。
- **🛡️ 跨架构硬件安全防护 (Cross-Architecture Safety Guard)**:  
  内置自检诊断模块。若用户安装了非匹配架构的分发包，系统将精准提示并优雅拦截，绝不发生崩溃或闪退。
- **🚫 零假冒软件模拟 (Zero Fake Emulation)**:  
  坚决杜绝任何使用 OpenCV 仿造模拟神经渲染的伪装方案，百分之百依托 Direct3D 12 硬件管道与 NVIDIA NGX 神经权重。

---

### 3. 分发包选用与显卡型号对照表 (Release Packages)

请根据您的 NVIDIA 显卡型号，前往 [GitHub Releases](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases) 下载对应的分发包：

| 分发包文件名 | 适用 GPU 架构 | 支持显卡型号 | 核心模型版本 |
| :--- | :--- | :--- | :--- |
| **`dlss5_blender_rtx20.zip`** | **Turing** (第 1 代 Tensor Core) | GeForce RTX 2060, 2070, 2080, 2080 Ti, TITAN RTX, Quadro RTX 3000~8000 | `310.8.SF.0` |
| **`dlss5_blender_rtx30.zip`** | **Ampere** (第 2 代 Tensor Core) | GeForce RTX 3050, 3060, 3070, 3080, 3090, RTX A2000~A6000 | `310.8.0.0` |
| **`dlss5_blender_rtx40.zip`** | **Ada Lovelace** (第 3 代 Tensor Core) | GeForce RTX 4060, 4070, 4080, 4090 (含 Super/Ti 系列), RTX 4000~5000 Ada | `310.8.0.0` |
| **`dlss5_blender_rtx50.zip`** | **Blackwell** (第 4 代 Tensor Core) | GeForce RTX 5070, 5080, 5090 等 Blackwell 次世代显卡 | `310.8.0.0` |

---

### 4. 安装与使用指引 (Installation & Usage)

#### 4.1 安装步骤
1. 从 [Releases 页面](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases) 下载对应您显卡的 `.zip` 压缩包（例如 RTX 3060 用户下载 `dlss5_blender_rtx30.zip`）。
2. 打开 Blender (推荐 3.6 LTS 或更高版本)。
3. 进入 **编辑 (Edit) > 偏好设置 (Preferences) > 插件 (Add-ons)**。
4. 点击右上角 **从磁盘安装... (Install from Disk...)**，选择下载的压缩包。
5. 在列表中找到并勾选启用 **Node: DLSS5 神经渲染 (Neural Rendering)**。

#### 4.2 验证就绪状态
1. 在插件偏好设置展开 **DLSS5 神经渲染硬件配置**：
   - 检查 `dlss5_worker.exe`、`nvngx_dlssnr.dll`、`nvngx.dll_dlssnr.dll` 状态是否为 `✓ 已就绪`。
   - 检查 D3D12 引擎状态是否正常识别出您的 RTX 显卡型号。
2. 在 3D 视图窗口按键盘 `N` 键展开右侧控制面板，切换到 **DLSS5** 选项卡，确认硬件引擎已处于活跃状态。

#### 4.3 合成器配置与一键渲染
1. 在 3D 视图 DLSS5 面板中点击 **自动化配置合成器节点树**，插件将自动在合成器中构建：
   `渲染层 (Render Layers)` ➔ `DLSS 5 神经渲染` ➔ `复合 (Composite)` 与 `预览 (Viewer)`。
2. 按 `F12` 执行常规渲染，渲染完成后 DLSS5 将自动在后台启动 Direct3D 12 Tensor Core 神经推理流水线，并在毫秒级完成超分辨率与画面重建！

---

### 5. C++ Worker 编译与二次开发 (C++ Worker Build Guide)

本项目将 C++ Direct3D 12 硬件 Worker 与 Python 插件解耦。源码位于 `src_worker/` 目录。

#### 5.1 环境要求
- Windows 10 / 11 64-bit
- Visual Studio 2022 (MSVC v143, 支持 C++20) 或 CMake 3.20+
- Windows SDK (包含 Direct3D 12 与 DXGI 头文件与静态库)

#### 5.2 编译方式

**方式一：使用一键批处理构建（推荐）**
直接在终端或 Visual Studio 开发者命令行中运行：
```cmd
cd src_worker
build.bat
```
编译脚本将自动检测 Visual Studio 环境并调用 MSVC 编译器：
```cmd
cl /nologo /EHsc /O2 /std:c++20 main.cpp d3d12_dlssnr.cpp /link /nologo /out:"..\bin\dlss5_worker.exe" d3d12.lib dxgi.lib
```
并自动将生成的 `dlss5_worker.exe` 部署至 `dlss5_blender/bin/` 供插件调用。

**方式二：使用 CMake 构建**
```cmd
cmake -B build -S src_worker
cmake --build build --config Release
copy /Y build\Release\dlss5_worker.exe dlss5_blender\bin\dlss5_worker.exe
```

---

<a name="english"></a>
## 🌐 English Description

### 1. Overview
**DLSS5 Composite Node for Blender** brings native hardware-accelerated Deep Learning Super Sampling and Neural Rendering (DLSS-NR, Feature ID 18) directly to Blender's compositor. Leveraging Direct3D 12 and dedicated NVIDIA Tensor Cores, it delivers ultra-low latency, photorealistic offline rendering reconstruction in milliseconds.

### 2. Key Features
- **⚡ Native Direct3D 12 Tensor Core Execution**: Pure C++20 asynchronous worker architecture directly orchestrates GPU physical Tensor Cores with near-zero runtime overhead.
- **🎨 Seamless Single Compositor Node Integration**: Single `CompositorNodeDLSS5` node connecting Color, Depth, Vector (Motion), and Normal passes, smoothly feeding into downstream color grading, glares, and output nodes.
- **🎯 Architecture-Specific Model Optimization**: Dedicated builds for Turing (RTX 20), Ampere (RTX 30), Ada Lovelace (RTX 40), and Blackwell (RTX 50) architectures to fully saturate each generation's compute units.
- **🛡️ Cross-Architecture Safety Interlock**: Intelligently verifies host GPU architecture against loaded weights, preventing driver-level crashes when incompatible packages are used.
- **🚫 Zero Fake Emulation**: 100% genuine D3D12 hardware pipeline—no CPU software filters or counterfeit image effects.

---

### 3. Release Package Selection

Download the release archive corresponding to your NVIDIA GPU from [GitHub Releases](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases):

| Package Name | Architecture | Supported Hardware | Weight Version |
| :--- | :--- | :--- | :--- |
| **`dlss5_blender_rtx20.zip`** | **Turing** (1st Gen Tensor Core) | GeForce RTX 2060 / 2070 / 2080 / 2080 Ti, TITAN RTX, Quadro RTX | `310.8.SF.0` |
| **`dlss5_blender_rtx30.zip`** | **Ampere** (2nd Gen Tensor Core) | GeForce RTX 3050 / 3060 / 3070 / 3080 / 3090, RTX A-Series | `310.8.0.0` |
| **`dlss5_blender_rtx40.zip`** | **Ada Lovelace** (3rd Gen Tensor Core) | GeForce RTX 4060 / 4070 / 4080 / 4090 (Super / Ti), RTX Ada | `310.8.0.0` |
| **`dlss5_blender_rtx50.zip`** | **Blackwell** (4th Gen Tensor Core) | GeForce RTX 5070 / 5080 / 5090 Series | `310.8.0.0` |

---

### 4. Installation & Quick Start

#### 4.1 One-Click Installation
1. Download the appropriate `.zip` package for your GPU from the [Releases](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases) page (e.g. `dlss5_blender_rtx30.zip` for RTX 3060/3070/3080).
2. Open Blender (3.6 LTS or newer recommended).
3. Navigate to **Edit > Preferences > Add-ons**.
4. Click **Install from Disk...** and select the downloaded zip file.
5. Check the box to enable **Node: DLSS5 神经渲染 (Neural Rendering)**.

#### 4.2 Verify Component Readiness
1. Expand the add-on preferences under **DLSS5 Neural Rendering Configuration**:
   - Confirm `dlss5_worker.exe`, `nvngx_dlssnr.dll`, and `nvngx.dll_dlssnr.dll` report `✓ Ready`.
   - Confirm the Native D3D12 engine detects your RTX GPU model.
2. In the 3D Viewport, press `N` to open the sidebar, select the **DLSS5** tab, and confirm the hardware engine is active.

#### 4.3 Compositor Pipeline & Rendering
1. In the 3D Viewport DLSS5 sidebar panel, click **Auto Setup Compositor**. The add-on creates:
   `Render Layers` ➔ `DLSS 5 Neural Rendering` ➔ `Composite` & `Viewer`.
2. Connect downstream nodes (Color Balance, Glare, Curves) directly after the DLSS5 node output.
3. Press `F12` to render. DLSS 5 will reconstruct the image via Tensor Cores automatically upon completion.

---

### 5. Compiling the C++ Worker

The high-performance Direct3D 12 worker binary can be compiled independently from source in `src_worker/`:

#### Option A: Build with Batch Script (Recommended)
```cmd
cd src_worker
build.bat
```
This detects the MSVC environment, compiles `dlss5_worker.exe` using C++20, and deploys it to `dlss5_blender/bin/`.

#### Option B: Build with CMake
```cmd
cmake -B build -S src_worker
cmake --build build --config Release
copy /Y build\Release\dlss5_worker.exe dlss5_blender\bin\dlss5_worker.exe
```

---

## 📜 License & Acknowledgements
- Blender Add-on scripts and source code licensed under [Apache License 2.0](LICENSE).
- NVIDIA, GeForce, RTX, and DLSS are registered trademarks of NVIDIA Corporation.
