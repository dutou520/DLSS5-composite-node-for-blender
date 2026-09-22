# -*- coding: utf-8 -*-
"""
DLSS5 Worker 桥接模块
负责调用 C++ 无头 GPU 执行器 (bin/dlss5_worker.exe)
在 NVIDIA RTX Tensor Core 硬件上真正运行神经网络模型
"""

import os
import sys
import json
import time
import tempfile
import subprocess
import numpy as np

# 引擎常量
ENGINE_NATIVE = "Native D3D12 (Tensor Core)"
ENGINE_NONE = "未就绪"


def _get_addon_dir() -> str:
    """获取插件根目录"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resize_rgba(arr: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    """双线性插值缩放图像"""
    h, w, c = arr.shape
    if w == target_w and h == target_h:
        return arr
    y_indices = np.linspace(0, h - 1, target_h)
    x_indices = np.linspace(0, w - 1, target_w)
    y_floor = np.floor(y_indices).astype(int)
    y_ceil = np.clip(y_floor + 1, 0, h - 1)
    x_floor = np.floor(x_indices).astype(int)
    x_ceil = np.clip(x_floor + 1, 0, w - 1)

    y_weight = (y_indices - y_floor)[:, None, None]
    x_weight = (x_indices - x_floor)[None, :, None]

    top_left = arr[y_floor[:, None], x_floor[None, :]]
    top_right = arr[y_floor[:, None], x_ceil[None, :]]
    bot_left = arr[y_ceil[:, None], x_floor[None, :]]
    bot_right = arr[y_ceil[:, None], x_ceil[None, :]]

    top = top_left * (1.0 - x_weight) + top_right * x_weight
    bot = bot_left * (1.0 - x_weight) + bot_right * x_weight
    return (top * (1.0 - y_weight) + bot * y_weight).astype(np.float32)


class DLSS5WorkerBridge:
    """管理与 dlss5_worker.exe 的通信与推理调用"""

    def __init__(self):
        self.addon_dir = _get_addon_dir()
        self.bin_dir = os.path.join(self.addon_dir, "bin")
        self.dlls_dir = os.path.join(self.addon_dir, "dlls")

        self.worker_exe = os.path.join(self.bin_dir, "dlss5_worker.exe")
        self.dlssnr_dll = os.path.join(self.dlls_dir, "nvngx_dlssnr.dll")
        self.proxy_dll = os.path.join(self.dlls_dir, "nvngx.dll_dlssnr.dll")

        # 检查候选路径 (开发调试环境兼容)
        if not os.path.exists(self.worker_exe):
            workspace_worker = r"D:\1\dlls5 for blender\bin\dlss5_worker.exe"
            if os.path.exists(workspace_worker):
                self.worker_exe = workspace_worker

        self._gpu_name = ""
        self._is_ready = False
        self._error_message = ""
        self._check_worker()

    def _check_worker(self):
        """执行 worker health check 及模型硬件兼容性自检"""
        self._error_message = ""
        if not os.path.exists(self.worker_exe):
            self._is_ready = False
            self._error_message = f"dlss5_worker.exe 未找到 ({self.worker_exe})"
            return

        if not os.path.exists(self.dlssnr_dll):
            self._is_ready = False
            self._error_message = f"nvngx_dlssnr.dll 未找到 ({self.dlssnr_dll})"
            return

        cmd = [
            self.worker_exe,
            "--check",
            "--validate-model",
            "--dll-path", self.dlssnr_dll,
            "--proxy-path", self.proxy_dll,
        ]

        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                startupinfo=startupinfo
            )
            out = res.stdout.strip()
            data = {}
            if out:
                try:
                    data = json.loads(out)
                except Exception:
                    pass

            if res.returncode == 0 and data.get("status") == "ok":
                self._gpu_name = data.get("gpu", "NVIDIA RTX GPU")
                self._is_ready = True
                self._error_message = ""
                return
            else:
                self._is_ready = False
                if data.get("gpu"):
                    self._gpu_name = data.get("gpu")
                err = data.get("error", "")
                if "not compatible with current GPU" in err or "FeatureNotSupported" in err:
                    gpu_hint = f"当前检测到显卡: {self._gpu_name}" if self._gpu_name else "当前显卡"
                    self._error_message = f"模型与显卡架构不兼容（{gpu_hint}，请下载匹配本显卡系列的 Release 分发包）"
                else:
                    self._error_message = err or res.stderr.strip() or f"Worker 退出码: {res.returncode}"
        except Exception as e:
            print(f"[DLSS5 Bridge] Worker check error: {e}")
            self._error_message = str(e)
            self._is_ready = False

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def gpu_name(self) -> str:
        return self._gpu_name

    def process(self, rgba: np.ndarray, params: dict = None) -> tuple:
        """
        调用 dlss5_worker.exe 处理图像

        参数:
            rgba: shape=(H, W, 4), dtype=float32
            params: 参数字典

        返回:
            (out_rgba, engine_name)
        """
        if params is None:
            params = {}

        if not os.path.exists(self.worker_exe):
            raise FileNotFoundError(f"dlss5_worker.exe not found at {self.worker_exe}")

        h, w = rgba.shape[:2]
        orig_h, orig_w = h, w

        # 处理输入分辨率缩放选项
        scaled_w, scaled_h = w, h
        in_rgba_proc = rgba
        if params.get("enable_input_scaling", False):
            pct = max(25, min(100, int(params.get("input_resolution_percent", 100))))
            if pct < 100:
                scaled_w = max(64, int(w * pct / 100))
                scaled_h = max(64, int(h * pct / 100))
                in_rgba_proc = _resize_rgba(rgba, scaled_w, scaled_h)

        # NVIDIA DLSS-NR 神经网络要求输入尺寸至少为 128x128
        # 当尺寸过小时，双线性上采样到至少 128x128 供 Worker 处理，随后下采样还原
        needs_pad = (scaled_w < 128 or scaled_h < 128)
        proc_w = max(128, scaled_w) if needs_pad else scaled_w
        proc_h = max(128, scaled_h) if needs_pad else scaled_h
        if needs_pad:
            in_rgba_proc = _resize_rgba(in_rgba_proc, proc_w, proc_h)

        temp_dir = tempfile.gettempdir()
        temp_in = os.path.join(temp_dir, f"dlss5_in_{os.getpid()}_{time.time_ns()}.raw")
        temp_out = os.path.join(temp_dir, f"dlss5_out_{os.getpid()}_{time.time_ns()}.raw")

        try:
            # 1. 写入临时 float32 二进制图像 (执行垂直翻转对齐 Blender 底起坐标与 D3D12 顶起坐标)
            in_float = np.ascontiguousarray(np.flipud(in_rgba_proc), dtype=np.float32)
            in_float.tofile(temp_in)

            # 2. 构建 CLI 命令
            cmd = [
                self.worker_exe,
                "--input", temp_in,
                "--output", temp_out,
                "--width", str(proc_w),
                "--height", str(proc_h),

                "--intensity", str(params.get("intensity", 1.0)),
                "--style", str(params.get("style", 0)),
                "--local-tone", str(params.get("local_tone_strength", 1.0)),
                "--local-struct", str(params.get("local_structure_strength", 1.0)),
                "--skin-struct", str(params.get("skin_structure_strength", 0.0)),
                "--shadow-struct", str(params.get("shadow_structure_multiplier", 1.0)),
                "--reflection-glow", str(params.get("reflection_glow_multiplier", 1.0)),
                "--residual-mult", str(params.get("residual_multiplier", 1.0)),
                "--residual-sat", str(params.get("residual_saturation", 1.0)),
                "--residual-light", str(params.get("residual_lightness", 1.0)),
                "--auto-mask", "1" if params.get("auto_mask", False) else "0",
                "--ui-correction", "1" if params.get("ui_correction", True) else "0",
                "--dll-path", self.dlssnr_dll,
                "--proxy-path", self.proxy_dll,
            ]

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                startupinfo=startupinfo
            )

            if res.returncode != 0:
                err_msg = res.stderr or res.stdout
                raise RuntimeError(f"dlss5_worker.exe exited with code {res.returncode}: {err_msg}")

            # 解析结果
            stdout_str = res.stdout.strip()
            log_info = {}
            if stdout_str:
                try:
                    log_info = json.loads(stdout_str)
                except Exception:
                    pass

            if not os.path.exists(temp_out) or os.path.getsize(temp_out) == 0:
                raise RuntimeError("dlss5_worker.exe did not produce output file!")

            # 3. 读取处理完成的像素并垂直翻转回 Blender 坐标
            raw_data = np.fromfile(temp_out, dtype=np.float32).reshape((proc_h, proc_w, 4))
            out_rgba = np.ascontiguousarray(np.flipud(raw_data), dtype=np.float32)

            # 若进行了输入缩放或最小尺寸填充，双线性插值恢复到原始输出分辨率
            if proc_w != orig_w or proc_h != orig_h:
                out_rgba = _resize_rgba(out_rgba, orig_w, orig_h)

            time_ms = log_info.get("time_ms", 0.0)
            gpu_str = log_info.get("gpu", self._gpu_name or "NVIDIA RTX GPU")
            print(f"[DLSS5] Tensor Core 神经渲染完成 ({orig_w}x{orig_h}, {time_ms:.1f}ms on {gpu_str})")

            return out_rgba, f"Native D3D12 ({gpu_str})"

        finally:
            # 清理临时文件
            try:
                if os.path.exists(temp_in):
                    os.remove(temp_in)
                if os.path.exists(temp_out):
                    os.remove(temp_out)
            except Exception:
                pass


# ─── 单例实例 ───
_global_bridge = None


def get_worker_bridge() -> DLSS5WorkerBridge:
    global _global_bridge
    if _global_bridge is None:
        _global_bridge = DLSS5WorkerBridge()
    return _global_bridge
