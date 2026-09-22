# DLSS 5 Neural Rendering Composite Node for Blender

基于 NVIDIA DLSS 神经渲染与 Direct3D 12 原生硬件加速的 Blender 合成器节点插件。将离线降噪与超分辨率重构加速至毫秒级，真实调用 RTX Tensor Core 算力。

兼容 **Blender 3.6 LTS / 4.x / 5.x**，适配 NVIDIA RTX 20 / 30 / 40 / 50 全系列显卡。

---

## 效果预览

### 角色微观细节重构 (Null DLSS vs DLSS 5)
![角色微观细节重构对比](docs/images/preview_character_comparison.png)

### 场景光影与降噪对比 (null DLSS vs DLSS 5)
![复杂场景降噪与重建对比](docs/images/preview_scene_comparison.png)

---

## 快速开始

![DLSS5 合成器节点配置示意图](docs/images/quickstart_node_setup.png)

1. **下载与安装**：
   - 前往 [Releases 页面](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases) 下载与您显卡对应的 `.zip` 压缩包。
   - 打开 Blender，进入 **编辑 > 偏好设置 > 插件**，点击右上角 **从磁盘安装**，选择 zip 包并启用 **Node: DLSS5 神经渲染 (Neural Rendering)**。

2. **在合成器中连接节点**：
   - 进入合成器（Compositor），按 `Shift + A` 添加 **DLSS 5 神经渲染**（`DLSS5 Neural Rendering`）节点（或在 3D 视图侧边栏 DLSS5 面板点击“自动化配置合成器节点树”）。
   - 将 `渲染层`（或外部图像）的 **图像 (Image)** 插槽连接至 DLSS5 节点的 **Image**，再将 DLSS5 输出的 **Image** 端口连接至 **合成 (Composite)** 或下游调色节点。

3. **渲染**：
   - 节点默认开启 **渲染后自动执行 (Auto Run After Render)**。
   - 单帧渲染（`F12`）或动画渲染（`Ctrl + F12`）完成后，后台流水线将在毫秒内自动完成神经降噪与高保真画质重建。
   - 在 3D 视图中拖动时间线时也会自动进行防抖实时更新。

---

## 分发包选用指南（按显卡型号）

请前往 [GitHub Releases](https://github.com/dutou520/DLSS5-composite-node-for-blender/releases) 下载对应您显卡架构的分发包：

| 分发包文件名 | 适用 GPU 架构 | 支持显卡型号 | 核心模型版本 |
| :--- | :--- | :--- | :--- |
| **`dlss5_blender_rtx20.zip`** | **Turing** (第 1 代 Tensor Core) | RTX 2060, 2070, 2080, 2080 Ti, TITAN RTX, Quadro RTX 3000~8000 | `310.8.SF.0` |
| **`dlss5_blender_rtx30.zip`** | **Ampere** (第 2 代 Tensor Core) | RTX 3050, 3060, 3070, 3080, 3090, RTX A2000~A6000 | `310.8.0.0` |
| **`dlss5_blender_rtx40.zip`** | **Ada Lovelace** (第 3 代 Tensor Core) | RTX 4060, 4070, 4080, 4090 (含 Super/Ti), RTX 4000~5000 Ada | `310.8.0.0` |
| **`dlss5_blender_rtx50.zip`** | **Blackwell** (第 4 代 Tensor Core) | RTX 5070, 5080, 5090 等 Blackwell 次世代显卡 | `310.8.0.0` |

---

## 核心特性

- **⚡ 硬件级物理加速**：纯 C++20 原生 Direct3D 12 Worker，直接调度 NVIDIA 显卡物理 Tensor Core，严禁 CPU 滤镜冒充。
- **🎨 纯净单节点架构**：作为标准原生合成器节点无缝级联下游调色、眩光与输出节点，杜绝篡改用户节点树连线。
- **🎬 全流程模式兼容**：完美支持 3D 渲染（F12）、动画序列渲染（Ctrl+F12）、视频序列处理，以及时间线拖动防抖实时更新。
- **🛡️ 架构安全互锁**：针对各代 RTX 显卡进行专属模型微调编译，并在启动时智能校验 GPU 架构兼容性。

---

## 二次开发与编译 (可选)

如需自行编译 `dlss5_worker.exe`，源码位于 `src_worker/`：
```cmd
cd src_worker
build.bat
```
*(环境要求：Windows 10/11 64-bit、Visual Studio 2022 C++20 与 Windows SDK)*

---

## 开源许可
- 插件源码遵循 [Apache License 2.0](LICENSE) 许可协议。
- NVIDIA, GeForce, RTX, DLSS 均为 NVIDIA Corporation 的注册商标。
