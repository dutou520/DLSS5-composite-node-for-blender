# DLSS-NR 神经渲染与 NGX 运行时 DLL 存放规范 (DLL Directory Guide)

本目录供 Blender DLSS5 插件在运行时加载 NVIDIA DLSS 神经渲染驱动及模型库。  
由于大模型权重文件（约 158 MB）体积庞大且包含 NVIDIA 专有模型版权，**源码仓库不包含也不追踪任何 `.dll` 二进制文件**。

---

## 必需组件清单 (Required Components)

要启用 Native Direct3D 12 硬件加速推理，本目录下需具备以下组件：

1. **`nvngx_dlssnr.dll`** (核心神经渲染模型，~158 MB)
   - 对应目标 GPU 架构（Turing / Ampere / Ada Lovelace / Blackwell）的专用神经网络模型权重。
   - 模型 Feature ID: `18 (DLSS-NR)`.
2. **`nvngx.dll_dlssnr.dll`** (NGX 驱动级运行时交互库)
   - 负责与 NVIDIA 驱动及 D3D12 流水线交互。
3. **`nvngxruntime.dll`** (NVIDIA NGX 基础支持库)
   - 提供底层 NGX 基础设施运行时支持。

---

## 获取与安装方式 (How to Obtain)

- **Blender 终端用户**：
  直接从 [GitHub Releases](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases) 下载匹配您显卡型号的预打包 Release 压缩包（如 `dlss5_blender_rtx30.zip`、`dlss5_blender_rtx40.zip` 等），解压即可使用，包内已包含所有必需 DLL 与预编译 Worker。
- **开发者源码编译**：
  从匹配的 Release ZIP 包中提取上述 3 个 DLL，放入此 `dlls/` 目录即可。
