#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试VideoProcessor类中添加的方法
"""

from src.core.video_processor import VideoProcessor

def main():
    print("开始测试VideoProcessor...")
    vp = VideoProcessor()
    print("初始化成功！")
    
    # 测试添加的方法是否存在
    print("测试_get_video_duration_fast方法:", hasattr(vp, '_get_video_duration_fast'))
    print("测试_process_folder_shortcuts方法:", hasattr(vp, '_process_folder_shortcuts'))
    print("测试_get_audio_metadata方法:", hasattr(vp, '_get_audio_metadata'))
    
    print("测试完成！")

if __name__ == "__main__":
    main() 