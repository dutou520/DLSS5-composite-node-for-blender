# -*- coding: utf-8 -*-
"""
DLSS5 文件与依赖管理
负责管理 dlss5_worker.exe、nvngx_dlssnr.dll 及 nvngx.dll_dlssnr.dll
"""

import os
import shutil
import subprocess
import ctypes
from ctypes import wintypes


class DLLManager:
    """管理 DLSS5 神经渲染所需执行器与 DLL 文件"""

    def __init__(self):
        self.core_dir = os.path.dirname(os.path.abspath(__file__))
        self.addon_dir = os.path.dirname(self.core_dir)
        self._dlls_dir = os.path.join(self.addon_dir, "dlls")
        self._bin_dir = os.path.join(self.addon_dir, "bin")

        if not os.path.exists(self._dlls_dir):
            try:
                os.makedirs(self._dlls_dir)
            except Exception:
                pass

        if not os.path.exists(self._bin_dir):
            try:
                os.makedirs(self._bin_dir)
            except Exception:
                pass

    @property
    def dlls_dir(self) -> str:
        return self._dlls_dir

    @property
    def bin_dir(self) -> str:
        return self._bin_dir

    @property
    def worker_path(self) -> str:
        p = os.path.join(self._bin_dir, "dlss5_worker.exe")
        if not os.path.exists(p):
            alt = r"D:\1\dlls5 for blender\bin\dlss5_worker.exe"
            if os.path.exists(alt):
                return alt
        return p

    @property
    def main_dll_path(self) -> str:
        return os.path.join(self._dlls_dir, "nvngx_dlssnr.dll")

    @property
    def bridge_dll_path(self) -> str:
        return os.path.join(self._dlls_dir, "nvngx.dll_dlssnr.dll")

    @property
    def runtime_dll_path(self) -> str:
        return os.path.join(self._dlls_dir, "nvngxruntime.dll")

    def _get_file_info(self, path: str) -> dict:
        exists = os.path.exists(path)
        size_mb = 0.0
        if exists:
            try:
                size_mb = round(os.path.getsize(path) / (1024 * 1024), 2)
            except Exception:
                pass
        return {
            "exists": exists,
            "size_mb": size_mb,
            "path": path
        }

    def check_all(self) -> dict:
        worker_info = self._get_file_info(self.worker_path)
        main_info = self._get_file_info(self.main_dll_path)
        bridge_info = self._get_file_info(self.bridge_dll_path)
        runtime_info = self._get_file_info(self.runtime_dll_path)

        all_present = (worker_info["exists"] and main_info["exists"] and 
                       bridge_info["exists"] and runtime_info["exists"])

        if all_present:
            status_message = "C++ Worker 与核心模型 DLL 均已就绪。"
        else:
            missing = []
            if not worker_info["exists"]:
                missing.append("dlss5_worker.exe")
            if not main_info["exists"]:
                missing.append("nvngx_dlssnr.dll")
            if not bridge_info["exists"]:
                missing.append("nvngx.dll_dlssnr.dll")
            if not runtime_info["exists"]:
                missing.append("nvngxruntime.dll")
            status_message = f"缺少以下文件: {', '.join(missing)}"

        return {
            "all_present": all_present,
            "worker": worker_info,
            "main_dll": main_info,
            "bridge_dll": bridge_info,
            "runtime_dll": runtime_info,
            "status_message": status_message
        }
