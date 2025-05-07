#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
全面修复临时文件位置脚本
- 修改软件配置文件
- 修改系统环境变量
- 强制清理旧临时文件
"""

import os
import sys
import json
import shutil
import time
import winreg
import subprocess
from pathlib import Path

def create_d_drive_temp_dir():
    """创建D盘临时目录"""
    d_drive_path = "D:\\VideoMixTool_Temp"
    try:
        os.makedirs(d_drive_path, exist_ok=True)
        print(f"已创建D盘临时目录: {d_drive_path}")
        return d_drive_path
    except Exception as e:
        print(f"创建D盘临时目录失败: {e}")
        return None

def update_software_config(new_temp_dir):
    """更新软件配置文件"""
    # 配置文件路径
    config_dir = Path.home() / "VideoMixTool"
    config_file = config_dir / "cache_config.json"
    
    # 确保目录存在
    config_dir.mkdir(exist_ok=True, parents=True)
    
    # 读取现有配置(如果存在)
    config = {"cache_dir": new_temp_dir}
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            print(f"读取配置时出错: {e}")
    
    # 更新缓存目录
    config["cache_dir"] = new_temp_dir
    
    # 保存配置
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"已成功更新软件配置文件，缓存目录设置为: {new_temp_dir}")
        return True
    except Exception as e:
        print(f"保存配置时出错: {e}")
        return False

def set_environment_variables(new_temp_dir):
    """设置系统环境变量"""
    try:
        # 使用subprocess调用SETX命令设置系统环境变量
        subprocess.run(["setx", "TEMP", new_temp_dir, "/M"], check=True, capture_output=True)
        subprocess.run(["setx", "TMP", new_temp_dir, "/M"], check=True, capture_output=True)
        print(f"已成功设置系统环境变量TEMP和TMP为: {new_temp_dir}")
        return True
    except Exception as e:
        print(f"设置系统环境变量失败: {e}")
        return False

def clean_old_temp_files():
    """彻底清理旧的临时文件"""
    # 项目内temp目录
    local_temp_dir = Path("temp")
    if local_temp_dir.exists():
        try:
            print(f"正在清理本地temp目录: {local_temp_dir}")
            # 尝试删除temp目录下的所有内容
            for item in local_temp_dir.glob("*"):
                try:
                    if item.is_file():
                        item.unlink()
                        print(f"已删除文件: {item}")
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                        print(f"已删除目录: {item}")
                except Exception as e:
                    print(f"无法删除 {item}: {e}")
            print("本地temp目录清理完成")
        except Exception as e:
            print(f"清理本地temp目录时出错: {e}")
    
    # 将项目目录中的temp设为只读，防止创建新的临时文件
    try:
        if not local_temp_dir.exists():
            local_temp_dir.mkdir(exist_ok=True)
        readme_file = local_temp_dir / "README.txt"
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write("此目录已不再用于存放临时文件。\n")
            f.write(f"所有临时文件现在存放在: D:\\VideoMixTool_Temp\n")
            f.write("请不要在此目录中创建文件。\n")
        print("已在原temp目录中创建提示文件")
    except Exception as e:
        print(f"创建提示文件时出错: {e}")

def create_registry_script():
    """创建一个注册表脚本来修改注册表中的临时目录设置"""
    reg_file_path = "set_temp_dir.reg"
    d_drive_path = "D:\\\\VideoMixTool_Temp"
    
    reg_content = f"""Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Environment]
"TEMP"="{d_drive_path}"
"TMP"="{d_drive_path}"

[HKEY_CURRENT_USER\\Environment]
"TEMP"="{d_drive_path}"
"TMP"="{d_drive_path}"
"""
    
    try:
        with open(reg_file_path, 'w', encoding='utf-8') as f:
            f.write(reg_content)
        print(f"已创建注册表脚本: {reg_file_path}")
        print("请右键点击该文件并选择'合并'来更新系统注册表")
        return True
    except Exception as e:
        print(f"创建注册表脚本时出错: {e}")
        return False

def create_complete_cleanup_batch():
    """创建一个完整的清理批处理文件"""
    batch_file = "完全清理临时文件.bat"
    
    batch_content = """@echo off
echo 正在全面清理临时文件...

rem 清理系统临时目录中的大文件
echo 正在清理系统临时目录...
forfiles /P "%TEMP%" /S /M *.* /C "cmd /c if @fsize GTR 10485760 (echo 删除大文件: @path && del /F /Q @path)" 2>nul

rem 清理项目temp目录
echo 正在清理项目temp目录...
cd /d "%~dp0"
if exist "temp" (
    rmdir /S /Q temp
    mkdir temp
    echo 已重建temp目录
)

rem 清理D盘临时目录中的大文件
echo 正在清理D盘临时目录...
if exist "D:\\VideoMixTool_Temp" (
    forfiles /P "D:\\VideoMixTool_Temp" /S /M *.* /C "cmd /c if @fsize GTR 10485760 (echo 删除大文件: @path && del /F /Q @path)" 2>nul
)

echo.
echo 临时文件清理完成!
echo 临时文件将存放在: D:\\VideoMixTool_Temp
echo.
pause
"""
    
    try:
        with open(batch_file, 'w', encoding='utf-8') as f:
            f.write(batch_content)
        print(f"已创建完整清理批处理文件: {batch_file}")
        return True
    except Exception as e:
        print(f"创建批处理文件时出错: {e}")
        return False

def main():
    print("===== 全面修复临时文件位置 =====")
    
    # 创建D盘临时目录
    new_temp_dir = create_d_drive_temp_dir()
    if not new_temp_dir:
        print("创建D盘临时目录失败，无法继续！")
        return False
    
    # 更新软件配置
    if not update_software_config(new_temp_dir):
        print("警告: 更新软件配置失败！")
    
    # 设置环境变量
    if not set_environment_variables(new_temp_dir):
        print("警告: 设置环境变量失败！")
    
    # 清理旧临时文件
    clean_old_temp_files()
    
    # 创建注册表脚本
    create_registry_script()
    
    # 创建完整清理批处理
    create_complete_cleanup_batch()
    
    print("\n===== 操作完成 =====")
    print(f"1. 已设置临时目录到: {new_temp_dir}")
    print("2. 已创建完全清理批处理文件，可以定期运行")
    print("3. 已创建注册表脚本，请右键点击并选择'合并'来更新系统设置")
    print("\n注意: 某些应用可能需要重启系统才能正确使用新的临时目录")
    
    return True

if __name__ == "__main__":
    main()
    input("按回车键退出...") 