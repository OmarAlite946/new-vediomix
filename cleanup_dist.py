#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
清理dist目录中的大型文件
"""

import os
import shutil
import sys
from pathlib import Path
import logging
import time

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"dist_cleanup_{int(time.time())}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
DIST_DIR = PROJECT_ROOT / "dist"

# 定义大文件阈值 (2MB)
BIG_FILE_THRESHOLD = 2 * 1024 * 1024  # 2MB

# 需要保留的目录
KEEP_DIRS = [
    "src",
    "core",
    "_internal/PyQt5/Qt5/translations",  # 保留翻译文件
]

# 需要保留的文件扩展名
KEEP_EXTENSIONS = [
    ".exe",       # 主程序可执行文件
    ".py",        # Python源文件
    ".md",        # 文档
    ".txt",       # 文本文件
    ".json",      # 配置文件
]

# 强制删除的文件
FORCE_DELETE_FILES = [
    "_internal/ffmpeg-win-x86_64-v7.1.exe",  # FFmpeg可以单独提供
    "_internal/cv2/cv2.pyd",                 # 可以减小分发包体积
]

def format_size(size_bytes):
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} 字节"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def should_keep_file(file_path):
    """检查文件是否应该保留"""
    # 将路径转换为相对于dist的路径
    rel_path = os.path.relpath(file_path, DIST_DIR)
    
    # 检查是否在强制删除列表中
    for force_delete in FORCE_DELETE_FILES:
        if force_delete in rel_path.replace("\\", "/"):
            return False
    
    # 检查是否在需要保留的目录中
    for keep_dir in KEEP_DIRS:
        if rel_path.startswith(keep_dir):
            return True
    
    # 检查扩展名
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in KEEP_EXTENSIONS:
        return True
    
    # 检查文件大小
    file_size = os.path.getsize(file_path)
    return file_size < BIG_FILE_THRESHOLD

def clean_dist_directory():
    """清理dist目录中的大型文件"""
    if not os.path.exists(DIST_DIR):
        logger.warning(f"dist目录不存在: {DIST_DIR}")
        return
    
    logger.info(f"开始清理dist目录: {DIST_DIR}")
    
    total_size_before = 0
    total_size_after = 0
    deleted_count = 0
    skipped_count = 0
    
    # 计算清理前的总大小
    for root, dirs, files in os.walk(DIST_DIR):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                total_size_before += file_size
            except Exception:
                pass
    
    # 清理大文件
    for root, dirs, files in os.walk(DIST_DIR, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(file_path, DIST_DIR)
                file_size = os.path.getsize(file_path)
                
                if not should_keep_file(file_path):
                    logger.info(f"删除文件: {rel_path} ({format_size(file_size)})")
                    os.remove(file_path)
                    deleted_count += 1
                else:
                    logger.debug(f"保留文件: {rel_path} ({format_size(file_size)})")
                    skipped_count += 1
                    total_size_after += file_size
            except Exception as e:
                logger.error(f"处理文件时出错 {file_path}: {str(e)}")
    
    # 删除空目录
    for root, dirs, files in os.walk(DIST_DIR, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查目录是否为空
                    os.rmdir(dir_path)
                    logger.info(f"删除空目录: {os.path.relpath(dir_path, DIST_DIR)}")
            except Exception as e:
                logger.error(f"删除目录时出错 {dir_path}: {str(e)}")
    
    # 计算节省的空间
    space_saved = total_size_before - total_size_after
    
    logger.info("清理完成!")
    logger.info(f"清理前大小: {format_size(total_size_before)}")
    logger.info(f"清理后大小: {format_size(total_size_after)}")
    logger.info(f"节省空间: {format_size(space_saved)}")
    logger.info(f"删除了 {deleted_count} 个文件，保留了 {skipped_count} 个文件")

if __name__ == "__main__":
    # 执行前确认
    print("警告: 此脚本将删除dist目录中的大型文件和库文件。")
    print("这可能会导致已打包的程序无法正常运行，建议在测试环境使用。")
    confirm = input("是否继续? (y/n): ")
    
    if confirm.lower() == 'y':
        clean_dist_directory()
    else:
        print("操作已取消") 