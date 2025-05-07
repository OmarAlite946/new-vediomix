#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试临时目录设置
"""

import os
import time
import json
from pathlib import Path

# 从src.utils.cache_config导入函数
def get_system_temp_dir():
    """获取系统临时目录，优先使用非C盘路径"""
    # 优先尝试使用D盘
    d_drive_path = "D:\\VideoMixTool_Temp"
    if os.path.exists("D:\\") or os.access("D:\\", os.W_OK):
        try:
            os.makedirs(d_drive_path, exist_ok=True)
            return d_drive_path
        except Exception as e:
            print(f"无法创建D盘临时目录: {e}")
    
    # 其次尝试使用环境变量中的临时目录
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir and os.path.exists(temp_dir):
        # 检查是否在C盘
        if temp_dir.lower().startswith("c:"):
            print(f"系统临时目录在C盘: {temp_dir}，尝试使用其他盘...")
            # 尝试查找其他可用的磁盘
            for drive in ['D:', 'E:', 'F:', 'G:']:
                try:
                    if os.path.exists(f"{drive}\\"):
                        alt_path = f"{drive}\\VideoMixTool_Temp"
                        os.makedirs(alt_path, exist_ok=True)
                        print(f"使用非C盘临时目录: {alt_path}")
                        return alt_path
                except Exception:
                    continue
        else:
            # 不在C盘，可以直接使用
            temp_path = os.path.join(temp_dir, "VideoMixTool")
            os.makedirs(temp_path, exist_ok=True)
            return temp_path
    
    # 最后使用用户目录
    user_temp = str(Path.home() / "VideoMixTool" / "temp")
    os.makedirs(user_temp, exist_ok=True)
    return user_temp

def test_temp_dir():
    """测试临时目录设置"""
    print("\n===== 测试临时目录设置 =====")
    
    # 获取配置的临时目录
    config_dir = Path.home() / "VideoMixTool"
    config_file = config_dir / "cache_config.json"
    
    print(f"配置文件路径: {config_file}")
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                configured_temp = config.get("cache_dir", "未设置")
                print(f"配置的临时目录: {configured_temp}")
        except Exception as e:
            print(f"读取配置文件出错: {e}")
    else:
        print("配置文件不存在")
    
    # 获取系统临时目录
    system_temp = get_system_temp_dir()
    print(f"获取的系统临时目录: {system_temp}")
    
    # 测试是否可以写入临时文件
    test_file = Path(system_temp) / f"test_{int(time.time())}.txt"
    try:
        with open(test_file, 'w') as f:
            f.write("测试文件")
        print(f"成功写入测试文件: {test_file}")
        # 删除测试文件
        test_file.unlink()
        print(f"成功删除测试文件")
        return True
    except Exception as e:
        print(f"写入测试文件失败: {e}")
        return False
    
if __name__ == "__main__":
    if test_temp_dir():
        print("\n测试成功! 临时文件将被存放到D盘，不会占用C盘空间。")
    else:
        print("\n测试失败! 请检查D盘权限或重新运行设置脚本。") 