# -*- coding: utf-8 -*-
"""
DLSS5 / DLSS-NR 原生硬件加速引擎调度器
仅支持 Native C++ Worker (D3D12 Tensor Core) 原生硬件执行，彻底移除软件模拟
"""

import os
import subprocess
import numpy as np
from .worker_bridge import get_worker_bridge

ENGINE_NATIVE = "Native D3D12 (Tensor Core)"
ENGINE_NONE = "未就绪"


class DLSS5SystemInfo:
    """系统 GPU、驱动与 DLSS-NR 库状态诊断"""

    def __init__(self):
        self.gpu_name = "未知显卡"
        self.driver_version = "未知驱动"
        self.cuda_version = "未知"
        self.has_nvidia_gpu = False
        self.is_rtx = False
        self.status_message = ""
        self._detect_gpu()

    def _detect_gpu(self):
        """通过 nvidia-smi 检测 GPU 信息"""
        try:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            cmd = ["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3,
                                 startupinfo=startupinfo)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split("\n")[0].split(",")]
                self.gpu_name = parts[0]
                if len(parts) > 1:
                    self.driver_version = parts[1]
                self.has_nvidia_gpu = True
                self.is_rtx = "RTX" in self.gpu_name.upper()

            res2 = subprocess.run(["nvidia-smi"], capture_output=True, text=True,
                                  timeout=3, startupinfo=startupinfo)
            if "CUDA Version:" in res2.stdout:
                idx = res2.stdout.find("CUDA Version:")
                self.cuda_version = res2.stdout[idx:idx + 25].split(":")[1].strip().split()[0]
        except Exception:
            self.has_nvidia_gpu = False

        if not self.has_nvidia_gpu:
            self.status_message = "未检测到 NVIDIA GPU"
        else:
            self.status_message = f"{self.gpu_name} (驱动 {self.driver_version}, CUDA {self.cuda_version})"

    def to_dict(self) -> dict:
        return {
            "gpu_name": self.gpu_name,
            "driver_version": self.driver_version,
            "cuda_version": self.cuda_version,
            "has_nvidia_gpu": self.has_nvidia_gpu,
            "is_rtx": self.is_rtx,
            "status_message": self.status_message,
        }


class DLSS5Engine:
    """
    DLSS5 引擎调度器
    优先使用 C++ D3D12 Worker 在 NVIDIA RTX Tensor Core 上执行
    """

    def __init__(self):
        self._system_info = None
        self._worker_bridge = get_worker_bridge()

    @property
    def system_info(self) -> DLSS5SystemInfo:
        if self._system_info is None:
            self._system_info = DLSS5SystemInfo()
        return self._system_info

    @property
    def native_available(self) -> bool:
        return self._worker_bridge.is_ready

    @property
    def native_error(self) -> str:
        if not self.native_available:
            err = getattr(self._worker_bridge, 'error_message', "")
            return err if err else "C++ D3D12 Worker 或 nvngx_dlssnr.dll 未就绪"
        return ""

    def get_engine_status(self) -> dict:
        return {
            "native_available": self.native_available,
            "native_error": self.native_error,
            "worker_gpu": self._worker_bridge.gpu_name,
            "system_info": self.system_info.to_dict(),
        }

    def process(
        self,
        rgba: np.ndarray,
        depth: np.ndarray = None,
        vector: np.ndarray = None,
        params: dict = None,
        **kwargs
    ) -> tuple:
        """
        执行 DLSS5 原生 D3D12 神经渲染处理
        仅支持 Native D3D12 (NVIDIA RTX Tensor Core) 硬件执行，坚决不向软件模拟回退。

        参数:
            rgba: shape=(H, W, 4), dtype=float32
            depth: 可选深度通道
            vector: 可选运动矢量
            params: 14 个 DLSS-NR 参数字典

        返回:
            (result_rgba, engine_name)
        """
        if params is None:
            params = {}

        if not self.native_available:
            err = self.native_error or "D3D12 Worker 缺失或未就绪"
            raise RuntimeError(f"错误: D3D12 Worker 缺失 ({err})")

        try:
            out_rgba, engine_name = self._worker_bridge.process(rgba, params)
            if out_rgba is None or (out_rgba.max() == 0.0 and rgba.max() > 0.0):
                raise RuntimeError("错误: 硬件推理失败 (Worker 未能生成有效画面)")
            return out_rgba, engine_name
        except Exception as e:
            print(f"[DLSS5] 原生硬件推理异常: {e}")
            raise e

    def shutdown(self):
        pass


_global_engine = None


def get_engine() -> DLSS5Engine:
    global _global_engine
    if _global_engine is None:
        _global_engine = DLSS5Engine()
    return _global_engine


def shutdown_engine():
    global _global_engine
    if _global_engine is not None:
        _global_engine.shutdown()
        _global_engine = None
