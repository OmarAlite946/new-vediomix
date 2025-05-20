#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试process_batch方法对字典类型参数的处理
"""

import os
import sys
import time
from datetime import datetime

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from src.core.video_processor import VideoProcessor

def progress_callback(message, percent):
    """进度回调函数"""
    print(f"[进度 {percent:.1f}%] {message}")

def main():
    """测试批量处理功能"""
    try:
        print("正在初始化视频处理器...")
        
        # 创建视频处理器实例
        processor = VideoProcessor(
            settings={
                "temp_dir": os.path.join(os.getcwd(), "temp"),
                "ffmpeg_path": "D:/ffmpeg_compat/ffmpeg.exe",
                "clean_temp_files": True,
                "hwaccel": "nvenc",
                "preset": "medium",
                "crf": 23,
                "bgm_volume": 0.3
            },
            progress_callback=progress_callback
        )
        
        print(f"视频处理器初始化成功，使用FFmpeg路径: {processor._get_ffmpeg_cmd()}")
        
        # 创建测试输出目录
        output_dir = os.path.join(os.getcwd(), "test_output")
        os.makedirs(output_dir, exist_ok=True)
        
        # 构建测试素材文件夹
        # 这里使用字典格式的文件夹列表，模拟实际使用场景
        material_folders = [
            {
                "name": "测试场景1",
                "folder_path": "E:/视频/素材/高手接话素材/高手接话003无头版/1、我给你讲个故事"
            },
            {
                "name": "测试场景2",
                "folder_path": "E:/视频/素材/高手接话素材/高手接话003无头版/3.1、故事1【混剪】"
            }
        ]
        
        # 记录开始时间
        start_time = time.time()
        
        # 执行批量处理
        try:
            print("开始执行批量处理测试...")
            result_files, result_message = processor.process_batch(
                material_folders=material_folders,
                output_dir=output_dir,
                count=1,  # 只生成1个视频用于测试
                bgm_path=None  # 不使用背景音乐
            )
            
            # 记录结束时间
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            print(f"\n批量处理测试完成，耗时: {elapsed_time:.2f}秒")
            print(f"结果消息: {result_message}")
            
            if result_files:
                print(f"生成的视频文件:")
                for i, file_path in enumerate(result_files):
                    print(f"  {i+1}. {file_path}")
                    if os.path.exists(file_path):
                        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
                        print(f"     文件大小: {file_size:.2f} MB")
                    else:
                        print(f"     文件不存在!")
            else:
                print("没有生成视频文件!")
                
        except Exception as e:
            print(f"批量处理测试失败: {str(e)}")
            import traceback
            print(traceback.format_exc())
    except Exception as e:
        print(f"初始化失败: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    main() 