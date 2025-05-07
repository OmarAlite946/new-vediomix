#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
设置D盘临时目录脚本
"""

import os
import json
import sys
from pathlib import Path

def main():
    # 创建D盘临时目录
    d_drive_path = "D:\\VideoMixTool_Temp"
    try:
        os.makedirs(d_drive_path, exist_ok=True)
        print(f"已创建D盘临时目录: {d_drive_path}")
    except Exception as e:
        print(f"创建D盘临时目录失败: {e}")
        return False
    
    # 配置文件路径
    config_dir = Path.home() / "VideoMixTool"
    config_file = config_dir / "cache_config.json"
    
    # 确保目录存在
    config_dir.mkdir(exist_ok=True, parents=True)
    
    # 读取现有配置(如果存在)
    config = {"cache_dir": d_drive_path}
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                config.update(loaded)
        except Exception as e:
            print(f"读取配置时出错: {e}")
    
    # 更新缓存目录
    config["cache_dir"] = d_drive_path
    
    # 保存配置
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print(f"已成功设置临时目录至: {d_drive_path}")
        return True
    except Exception as e:
        print(f"保存配置时出错: {e}")
        return False

if __name__ == "__main__":
    print("===== 设置D盘临时目录 =====")
    if main():
        print("\n设置成功！所有临时文件将存放在D盘，避免占用C盘空间。")
        print("请运行'修复临时目录引用.bat'脚本来更新所有代码中的临时目录引用。")
    else:
        print("\n设置失败，请检查是否有写入D盘的权限。") 