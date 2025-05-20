#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试_scan_material_folders方法对字典类型参数的处理
"""

from src.core.video_processor import VideoProcessor
import os
import sys

def main():
    print("开始测试_scan_material_folders方法对字典类型参数的处理...")
    
    # 初始化视频处理器
    vp = VideoProcessor()
    
    # 测试路径
    test_dir = os.path.abspath("./test_media")
    os.makedirs(test_dir, exist_ok=True)
    
    # 创建测试字典列表，模拟可能的输入格式
    material_folders = [
        {"folder_path": test_dir, "name": "测试文件夹1"}, 
        {"path": "C:/不存在的路径", "name": "测试文件夹2"},
        test_dir  # 直接使用路径字符串
    ]
    
    print(f"测试素材文件夹列表: {material_folders}")
    
    try:
        # 测试扫描方法
        material_data = vp._scan_material_folders(material_folders)
        print("扫描完成，没有类型错误！")
        print(f"扫描结果: 找到 {len(material_data) if material_data else 0} 个文件夹数据")
        return True
    except TypeError as e:
        print(f"类型错误: {str(e)}")
        return False
    except Exception as e:
        print(f"其他错误: {str(e)}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 