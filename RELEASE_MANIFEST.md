# DLSS5 for Blender 原生硬件加速插件 Release 分发清单

> **版本**: v3.0.0 (支持 Blender 3.6 LTS 及更高版本)  
> **发布生成时间**: 2026-09-22 14:53:20  
> **分发存储路径**: `D:\1\dlls5 for blender\`  

---

## 一、 架构分发包总览 (Release Packages)

本插件基于 NVIDIA DLSS-NR (Neural Rendering, Feature ID 18) 与原生 Direct3D 12 Tensor Core 硬件流水线打造。针对不同世代 NVIDIA RTX 显卡的微架构演进及 Tensor Core 指令集特性，分别装配了各架构专用的神经网络核心模型权重库，形成 4 款专有分发包：

| 分发压缩包文件名 | 适配显卡系列 | GPU 架构 | 压缩包大小 | 解压后模型大小 | 模型版本 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`dlss5_blender_rtx20.zip`** | NVIDIA GeForce RTX 20 系列 | Turing 架构 (第 1 代 Tensor Core) | **114.66 MB** | 158.15 MB | `310.8.SF.0` |
| **`dlss5_blender_rtx30.zip`** | NVIDIA GeForce RTX 30 系列 | Ampere 架构 (第 2 代 Tensor Core) | **114.43 MB** | 158.16 MB | `310.8.0.0` |
| **`dlss5_blender_rtx40.zip`** | NVIDIA GeForce RTX 40 系列 | Ada Lovelace 架构 (第 3 代 Tensor Core) | **102.45 MB** | 158.16 MB | `310.8.0.0` |
| **`dlss5_blender_rtx50.zip`** | NVIDIA GeForce RTX 50 系列 | Blackwell 架构 (第 4 代 Tensor Core) | **107.91 MB** | 158.16 MB | `310.8.0.0` |

---

## 二、 各分发包详细适配与校验规格

### 📦 1. dlss5_blender_rtx20.zip (NVIDIA GeForce RTX 20 系列)

- **目标微架构**: Turing 架构 (第 1 代 Tensor Core)
- **支持显卡型号**: GeForce RTX 2060, RTX 2060 Super, RTX 2070, RTX 2070 Super, RTX 2080, RTX 2080 Super, RTX 2080 Ti, TITAN RTX, Quadro RTX 3000/4000/5000/6000/8000 等
- **核心模型版本**: `310.8.SF.0`
- **架构适配说明**: 内置 310.8.SF.0 专有神经网络权重，专为 Turing 架构 Tensor Core 优化，兼容 FP16 与 INT8/INT4 深度计算加速。
- **压缩包大小**: 114.66 MB (120,232,965 字节)
- **ZIP 校验码 (SHA-256)**: `39DA53F439BB2A894EFFB19E481473E30A3458CBDCD3B175F63CE13B3AB66C4D`
- **内部包文件清单 (共 19 项)**:
  - `dlss5_blender/dlls/nvngx_dlssnr.dll` (158.15 MB) - SHA256: `6EB209E764F39872625DEBD6ABAF45E2BB6322F6F270F781F70C059AE30B3927`
  - `dlss5_blender/dlls/nvngx.dll_dlssnr.dll` (0.10 MB) - SHA256: `FA28D043587B72A5531F5F4A90E6F264D7E005654AF74F7F578C4722FA355F1C`
  - `dlss5_blender/dlls/nvngxruntime.dll` (0.08 MB) - SHA256: `FB09D0FB94EC49B3A33A9B8038209AF7B0C2257377C61AF2A19991F89C499215`
  - `dlss5_blender/bin/dlss5_worker.exe` (0.45 MB) - SHA256: `13F0A2796FFE1DD468088550882D9E76E419EAF38684C312245E481A88B2C631`
  - `dlss5_blender/__init__.py`, `handlers.py`, `preferences.py` 等 Blender 插件源码

### 📦 2. dlss5_blender_rtx30.zip (NVIDIA GeForce RTX 30 系列)

- **目标微架构**: Ampere 架构 (第 2 代 Tensor Core)
- **支持显卡型号**: GeForce RTX 3050, RTX 3060, RTX 3060 Ti, RTX 3070, RTX 3070 Ti, RTX 3080, RTX 3080 Ti, RTX 3090, RTX 3090 Ti, RTX A2000/A3000/A4000/A4500/A5000/A5500/A6000 等
- **核心模型版本**: `310.8.0.0`
- **架构适配说明**: 内置 310.8.0.0 专有神经网络权重，充分释放 Ampere 架构双倍 FP32/Tensor Core 计算吞吐量与稀疏化加速。
- **压缩包大小**: 114.43 MB (119,988,859 字节)
- **ZIP 校验码 (SHA-256)**: `3266B18CCAA27ADA19866DDA30C3B928B707AC7DFB040312787D2ABEA44E5301`
- **内部包文件清单 (共 19 项)**:
  - `dlss5_blender/dlls/nvngx_dlssnr.dll` (158.16 MB) - SHA256: `368911E6865534EDB9B82D803C1E5D3FA3292D9C832EE0A9EE3444AC58C96B82`
  - `dlss5_blender/dlls/nvngx.dll_dlssnr.dll` (0.10 MB) - SHA256: `FA28D043587B72A5531F5F4A90E6F264D7E005654AF74F7F578C4722FA355F1C`
  - `dlss5_blender/dlls/nvngxruntime.dll` (0.08 MB) - SHA256: `FB09D0FB94EC49B3A33A9B8038209AF7B0C2257377C61AF2A19991F89C499215`
  - `dlss5_blender/bin/dlss5_worker.exe` (0.45 MB) - SHA256: `13F0A2796FFE1DD468088550882D9E76E419EAF38684C312245E481A88B2C631`
  - `dlss5_blender/__init__.py`, `handlers.py`, `preferences.py` 等 Blender 插件源码

### 📦 3. dlss5_blender_rtx40.zip (NVIDIA GeForce RTX 40 系列)

- **目标微架构**: Ada Lovelace 架构 (第 3 代 Tensor Core)
- **支持显卡型号**: GeForce RTX 4060, RTX 4060 Ti, RTX 4070, RTX 4070 Super, RTX 4070 Ti, RTX 4070 Ti Super, RTX 4080, RTX 4080 Super, RTX 4090, RTX 4000/4500/5000 Ada Generation 等
- **核心模型版本**: `310.8.0.0`
- **架构适配说明**: 内置 310.8.0.0 专有神经网络权重，专为 Ada Lovelace 架构 FP8 Transformer 引擎与第 4 代 Tensor Core 高频微架构设计。
- **压缩包大小**: 102.45 MB (107,426,531 字节)
- **ZIP 校验码 (SHA-256)**: `DF71A65DD9914E4F9A7A8158889A620BEEFDA0BE9C211836ECF46EEABEDB2176`
- **内部包文件清单 (共 19 项)**:
  - `dlss5_blender/dlls/nvngx_dlssnr.dll` (158.16 MB) - SHA256: `28BDC080D28686DECDB63F6F4246B022274916B80AAFDAB266FE0FB63B2B9265`
  - `dlss5_blender/dlls/nvngx.dll_dlssnr.dll` (0.10 MB) - SHA256: `FA28D043587B72A5531F5F4A90E6F264D7E005654AF74F7F578C4722FA355F1C`
  - `dlss5_blender/dlls/nvngxruntime.dll` (0.08 MB) - SHA256: `FB09D0FB94EC49B3A33A9B8038209AF7B0C2257377C61AF2A19991F89C499215`
  - `dlss5_blender/bin/dlss5_worker.exe` (0.45 MB) - SHA256: `13F0A2796FFE1DD468088550882D9E76E419EAF38684C312245E481A88B2C631`
  - `dlss5_blender/__init__.py`, `handlers.py`, `preferences.py` 等 Blender 插件源码

### 📦 4. dlss5_blender_rtx50.zip (NVIDIA GeForce RTX 50 系列)

- **目标微架构**: Blackwell 架构 (第 4 代 Tensor Core)
- **支持显卡型号**: GeForce RTX 5070, RTX 5070 Ti, RTX 5080, RTX 5090 等最新 Blackwell 系列次世代显卡
- **核心模型版本**: `310.8.0.0`
- **架构适配说明**: 内置 310.8.0.0 专有神经网络权重，专为 Blackwell 架构微缩化计算单元与高显存带宽优化。
- **压缩包大小**: 107.91 MB (113,149,235 字节)
- **ZIP 校验码 (SHA-256)**: `4C906788B4D27A35FDBB5828CE4B71D87615BBAA744ACFCA94D55BA9FEC62496`
- **内部包文件清单 (共 19 项)**:
  - `dlss5_blender/dlls/nvngx_dlssnr.dll` (158.16 MB) - SHA256: `E16BCF15E16E13F527491CDF7845B2FE6521A738D8F7C9C721866A8496E1FC8E`
  - `dlss5_blender/dlls/nvngx.dll_dlssnr.dll` (0.10 MB) - SHA256: `FA28D043587B72A5531F5F4A90E6F264D7E005654AF74F7F578C4722FA355F1C`
  - `dlss5_blender/dlls/nvngxruntime.dll` (0.08 MB) - SHA256: `FB09D0FB94EC49B3A33A9B8038209AF7B0C2257377C61AF2A19991F89C499215`
  - `dlss5_blender/bin/dlss5_worker.exe` (0.45 MB) - SHA256: `13F0A2796FFE1DD468088550882D9E76E419EAF38684C312245E481A88B2C631`
  - `dlss5_blender/__init__.py`, `handlers.py`, `preferences.py` 等 Blender 插件源码

---

## 三、 规范的 Blender 插件根目录结构

所有分发包严格遵循 Blender 官方插件规范。用户无论使用 Blender 自带的“从磁盘安装”功能，还是手动解压到 `scripts/addons` 目录，均保持单层统一命名：

```text
dlss5_blender.zip
└── dlss5_blender/                     # 插件唯一顶层根目录
    ├── __init__.py                   # 插件入口与元数据注册
    ├── handlers.py                   # 渲染前/后流水线事件挂载器
    ├── preferences.py                # 偏好设置面板与硬件诊断
    ├── bin/
    │   └── dlss5_worker.exe          # C++ 原生 D3D12 Tensor Core 执行器
    ├── dlls/
    │   ├── nvngx_dlssnr.dll          # 对应 RTX 系列专有神经渲染大模型
    │   ├── nvngx.dll_dlssnr.dll      # NGX 运行时代理拦截器
    │   └── nvngxruntime.dll          # NVIDIA NGX 基础运行时支撑库
    ├── core/
    │   ├── dll_manager.py            # 核心组件就绪状态自检
    │   ├── dlssnr_bridge.py          # 硬件信息采集与调用中枢
    │   ├── image_processor.py        # EXR 浮点图像解析与写回
    │   └── worker_bridge.py          # 跨进程 Worker 调度与参数传递
    ├── nodes/
    │   └── dlss5_node.py             # 合成器原生 DLSS5 节点定义
    ├── operators/
    │   ├── op_execute.py             # 手动执行算子与批处理调度
    │   └── op_setup_compositor.py    # 合成器一键自动化搭建算子
    └── ui/
        └── panel_view3d.py           # 3D 视口 N 面板快捷控制
```

---

## 四、 Blender 安装与使用指南

### 1. 一键安装步骤
1. 根据个人显卡型号选择对应的 zip 压缩包（例如 RTX 3060 / 3070 / 3080 选择 `dlss5_blender_rtx30.zip`，RTX 4070 / 4080 / 4090 选择 `dlss5_blender_rtx40.zip`）。
2. 打开 Blender (推荐 3.6 LTS 及以上版本)。
3. 点击菜单栏 **编辑 (Edit) > 偏好设置 (Preferences) > 插件 (Add-ons)**。
4. 点击右上角 **从磁盘安装... (Install from Disk...)** 按钮，选中下载的 `dlss5_blender_rtxXX.zip` 并确认。
5. 在插件列表中勾选启用 **Node: DLSS5 神经渲染 (Neural Rendering)**。

### 2. 就绪自检验证
1. 展开插件偏好设置面板，查看组件状态：
   - **dlss5_worker.exe**: `✓ 已就绪`
   - **nvngx_dlssnr.dll**: `✓ 已就绪`
   - **nvngx.dll_dlssnr.dll**: `✓ 已就绪`
   - **Native D3D12 引擎**: `✓ 活跃 (显示检测到的本机 RTX 显卡型号)`
2. 在 3D 视口按键盘 `N` 键打开右侧面板，切换到 **DLSS5** 选项卡，状态栏将显示当前活跃的 GPU 与 D3D12 Worker 就绪标识。
3. 按 `F12` 渲染，渲染完成后 DLSS5 将自动在后台通过 Tensor Core 执行高精度神经重构，并刷新合成器画面！

---
*(本文档由自动化分发装配流水线自动生成)*
