#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
依赖包预下载工具
用于将所有依赖库下载到本地，便于离线安装
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def print_header(title):
    """打印带格式的标题"""
    divider = "=" * 70
    print(f"\n{divider}")
    print(f"{title}".center(70))
    print(f"{divider}")

def run_command(command):
    """运行命令并返回结果"""
    print(f"执行命令: {' '.join(command)}")
    try:
        process = subprocess.run(command, check=True, 
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True)
        return True, process.stdout
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False, e.stderr
    except Exception as e:
        print(f"命令执行错误: {e}")
        return False, str(e)

def main():
    # 获取当前脚本所在目录
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    
    # 设置下载目录
    download_dir = project_root / "pip_packages"
    download_dir.mkdir(exist_ok=True)
    
    print_header("视频混剪工具 - 依赖包下载工具")
    print(f"所有依赖包将下载到: {download_dir}")
    
    # 检查requirements.txt是否存在
    req_file = project_root / "requirements.txt"
    if not req_file.exists():
        print(f"错误: 未找到requirements.txt文件")
        sys.exit(1)
    
    # 确认下载
    confirm = input("准备下载所有依赖包，这可能需要较长时间，是否继续? (y/n): ").strip().lower()
    if confirm != 'y':
        print("操作已取消")
        sys.exit(0)
    
    # 开始下载
    print_header("开始下载依赖包")
    success, output = run_command([
        sys.executable, "-m", "pip", "download",
        "-r", str(req_file),
        "-d", str(download_dir),
        "--prefer-binary"
    ])
    
    if success:
        print("\n依赖包下载完成!")
        print(f"所有包已保存至: {download_dir}")
        print("\n在离线环境安装时，请使用以下命令:")
        print(f"pip install --no-index --find-links={download_dir} -r requirements.txt")
    else:
        print("\n依赖包下载过程中出现错误，请检查网络连接后重试")
    
    # 下载PyTorch CUDA版本(可选)
    print_header("PyTorch CUDA版本下载(可选)")
    download_pytorch = input("是否下载带CUDA支持的PyTorch? (y/n): ").strip().lower()
    if download_pytorch == 'y':
        print("开始下载PyTorch CUDA版本...")
        pytorch_cmd = [
            sys.executable, "-m", "pip", "download",
            "torch==2.0.1+cu118", 
            "torchvision==0.15.2+cu118",
            "torchaudio==2.0.2+cu118",
            "--index-url", "https://download.pytorch.org/whl/cu118",
            "-d", str(download_dir)
        ]
        run_command(pytorch_cmd)
        print("PyTorch CUDA版本下载完成")
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main() 