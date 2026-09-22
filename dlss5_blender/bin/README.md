# DLSS5 Worker 运行时二进制目录 (Worker Binary Directory)

本目录用于存放编译后的 Native Direct3D 12 Worker 执行程序：`dlss5_worker.exe`。

## 编译与获取方式

- **终端用户**：直接使用 GitHub Releases 发布的 Release ZIP 压缩包，已内置预编译好的 `dlss5_worker.exe`。
- **开发者编译**：
  进入 `src_worker/` 目录运行 `build.bat` 或使用 CMake 构建。编译脚本会自动将编译完成的 `dlss5_worker.exe` 复制到此目录。
