#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
阻止原位置创建临时文件
该脚本创建一个空的只读目录，阻止应用在原位置创建临时文件
"""

import os
import stat
import sys
import time
from pathlib import Path
import ctypes

def is_admin():
    """检查当前用户是否具有管理员权限"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def make_directory_protected(dir_path):
    """将目录设置为只读，防止写入"""
    try:
        # 确保目录存在
        os.makedirs(dir_path, exist_ok=True)
        
        # 创建警告文件
        warning_file = os.path.join(dir_path, "WARNING_DO_NOT_USE.txt")
        with open(warning_file, "w", encoding="utf-8") as f:
            f.write("警告：此目录已被保护，不应用于存放临时文件。\n")
            f.write("所有临时文件应该存放在：D:\\VideoMixTool_Temp\n")
            f.write("如果您看到此消息，说明某些应用程序仍在尝试使用旧的临时目录。\n")
            f.write(f"创建时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 设置目录为只读
        if os.name == 'nt':  # Windows
            os.system(f'attrib +R "{dir_path}"')
            print(f"已将目录设为只读: {dir_path}")
            
            # 设置文件为只读
            os.system(f'attrib +R "{warning_file}"')
        else:  # Unix/Linux/Mac
            os.chmod(dir_path, stat.S_IREAD | stat.S_IXUSR)
            os.chmod(warning_file, stat.S_IREAD)
    
        print(f"已保护目录: {dir_path}")
        return True
    except Exception as e:
        print(f"保护目录时出错: {e}")
        return False

def protect_temp_directories():
    """保护各种可能被用作临时目录的位置"""
    # 项目目录中的temp
    local_temp = Path("temp")
    
    # 保护项目内的temp目录
    if make_directory_protected(local_temp):
        print("成功保护项目内temp目录")
    
    # 检查是否有管理员权限
    if is_admin():
        # 如果有管理员权限，尝试保护系统临时目录
        system_temp = os.environ.get("TEMP") or os.environ.get("TMP")
        if system_temp and os.path.exists(system_temp):
            # 创建一个VideoMixTool子目录并保护它
            video_mix_temp = os.path.join(system_temp, "VideoMixTool")
            if make_directory_protected(video_mix_temp):
                print(f"成功保护系统临时目录下的VideoMixTool目录")
    else:
        print("警告：没有管理员权限，无法保护系统临时目录")
        print("请以管理员身份运行此脚本以获得完整的保护")

def redirect_temp_directories():
    """创建符号链接将旧的临时目录重定向到新的D盘临时目录"""
    if not is_admin():
        print("警告：需要管理员权限来创建符号链接")
        return False
    
    # 确保目标目录存在
    d_drive_temp = "D:\\VideoMixTool_Temp"
    os.makedirs(d_drive_temp, exist_ok=True)
    
    # 旧的临时目录位置
    old_temp_locations = [
        "temp",  # 项目目录中的temp
    ]
    
    # 获取系统临时目录下的VideoMixTool目录
    system_temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if system_temp and os.path.exists(system_temp):
        old_temp_locations.append(os.path.join(system_temp, "VideoMixTool"))
    
    # 创建符号链接
    for old_location in old_temp_locations:
        try:
            if os.path.exists(old_location):
                # 备份现有内容
                backup_dir = f"{old_location}_backup_{int(time.time())}"
                print(f"备份 {old_location} 到 {backup_dir}")
                os.rename(old_location, backup_dir)
            
            # 创建符号链接
            print(f"创建从 {old_location} 到 {d_drive_temp} 的符号链接")
            os.symlink(d_drive_temp, old_location, target_is_directory=True)
            print(f"成功创建符号链接: {old_location} -> {d_drive_temp}")
        except Exception as e:
            print(f"创建符号链接时出错 {old_location}: {e}")
    
    return True

def main():
    print("===== 阻止原位置创建临时文件 =====")
    
    # 检查是否以管理员权限运行
    if not is_admin():
        print("此脚本需要管理员权限才能完全发挥作用")
        print("请右键点击并选择'以管理员身份运行'")
        input("按回车键退出...")
        return
    
    # 首选方法：重定向目录（符号链接）
    if redirect_temp_directories():
        print("已成功设置目录重定向")
    else:
        # 备选方法：保护目录
        protect_temp_directories()
    
    print("\n操作完成!")
    print("原位置的临时文件现在将被重定向到D盘，或被阻止创建")
    input("按回车键退出...")

if __name__ == "__main__":
    main() 