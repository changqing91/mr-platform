@echo off
REM ============================================================
REM Qwen2.5-7B Windows 环境安装脚本
REM 需要 Python 3.10+ 和 CUDA 12.x 已安装
REM ============================================================

echo [1/3] 升级 pip...
python -m pip install --upgrade pip

echo.
echo [2/3] 安装 PyTorch (CUDA 12.1)...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

echo.
echo [3/3] 安装项目依赖...
pip install -r requirements.txt

echo.
echo [验证] 检查安装结果...
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA:', torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'No GPU found ')"

echo.
echo ============================================================
echo  安装完成！请运行 run_rtx6000.bat 开始训练。
echo ============================================================
pause
