#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
项目清理工具：清理与源代码无关的临时文件、备份、测试数据等
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
        logging.FileHandler(f"project_cleanup_{int(time.time())}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

# 定义可以安全删除的目录
SAFE_TO_DELETE_DIRS = [
    # 临时目录
    "temp",
    "test_temp",
    "test_videos_temp",
    "__pycache__",
    
    # 构建和发布目录
    "build",
    "dist",
    
    # 备份目录
    "backup",
    "backup_code",
    "organized_backups",
    "memory_backup",
    "cleanup_backup",
    "备份和临时",
    
    # 测试目录
    "test",
    "tests",
    "test_data",
    "test_media",
    "test_material",
    "test_materials",
    "test_out",
    "test_output",
    "test_valid_data",
    "test_mixed_mode",
    "test_grandchild_shortcuts",
    "test_simple",
    "test_media_shortcuts_enhanced",
    "test_media_shortcuts",
    "test_find_subfolder",
    "test_optimization_dir",
    
    # 开发辅助目录
    "维护和清理",
    "开发辅助"
]

# 定义可以安全删除的文件类型
SAFE_TO_DELETE_EXTENSIONS = [
    ".log",  # 所有日志文件
    ".bak",  # 所有备份文件
    ".pyc",  # Python编译文件
    ".pyo",  # Python优化文件
]

# 定义可以安全删除的特定文件
SAFE_TO_DELETE_FILES = [
    "ffmpeg.zip",         # 大型FFmpeg包
    "temp_log.txt",
    "ffmpeg_path.txt.bak",
    "settings.json.bak",
]

# 定义需要保留的重要目录
IMPORTANT_DIRS = [
    "src",
    "config", 
    "assets",
    "核心功能",
    "FFmpeg工具",  # 保留工具目录，但后面会清理里面的大文件
]

def is_safe_to_delete_dir(dir_path):
    """检查目录是否可以安全删除"""
    dir_name = os.path.basename(dir_path)
    
    # 检查是否在安全删除列表中
    if dir_name in SAFE_TO_DELETE_DIRS:
        return True
    
    # 检查是否以test_开头
    if dir_name.startswith("test_"):
        return True
    
    return False

def is_safe_to_delete_file(file_path):
    """检查文件是否可以安全删除"""
    file_name = os.path.basename(file_path)
    file_ext = os.path.splitext(file_name)[1].lower()
    
    # 检查是否在安全删除列表中
    if file_name in SAFE_TO_DELETE_FILES:
        return True
    
    # 检查文件扩展名
    if file_ext in SAFE_TO_DELETE_EXTENSIONS:
        return True
    
    # 检查是否为测试文件
    if file_name.startswith("test_") and file_ext == ".py":
        return True
    
    # 检查是否为修复脚本
    if file_name.startswith("fix_") and file_ext == ".py":
        return True
    
    return False

def get_dir_size(dir_path):
    """获取目录大小"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(dir_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size

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

def cleanup_project():
    """清理项目"""
    logger.info("开始清理项目...")
    
    # 获取初始项目大小
    initial_size = sum(
        os.path.getsize(os.path.join(PROJECT_ROOT, f)) 
        for f in os.listdir(PROJECT_ROOT) 
        if os.path.isfile(os.path.join(PROJECT_ROOT, f))
    )
    
    for dir_name in os.listdir(PROJECT_ROOT):
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        
        # 处理目录
        if os.path.isdir(dir_path):
            if is_safe_to_delete_dir(dir_path):
                dir_size = get_dir_size(dir_path)
                logger.info(f"删除目录: {dir_name} ({format_size(dir_size)})")
                try:
                    shutil.rmtree(dir_path)
                except Exception as e:
                    logger.error(f"删除目录 {dir_name} 失败: {str(e)}")
        
        # 处理文件
        elif os.path.isfile(dir_path):
            if is_safe_to_delete_file(dir_path):
                file_size = os.path.getsize(dir_path)
                logger.info(f"删除文件: {dir_name} ({format_size(file_size)})")
                try:
                    os.remove(dir_path)
                except Exception as e:
                    logger.error(f"删除文件 {dir_name} 失败: {str(e)}")
    
    # 获取清理后的项目大小
    final_size = sum(
        os.path.getsize(os.path.join(PROJECT_ROOT, f)) 
        for f in os.listdir(PROJECT_ROOT) 
        if os.path.isfile(os.path.join(PROJECT_ROOT, f))
    )
    
    # 计算释放的空间
    space_freed = initial_size - final_size
    
    logger.info("项目清理完成!")
    logger.info(f"初始文件大小: {format_size(initial_size)}")
    logger.info(f"最终文件大小: {format_size(final_size)}")
    logger.info(f"释放的空间: {format_size(space_freed)}")

if __name__ == "__main__":
    # 执行前确认
    print("警告: 此脚本将删除与源代码无关的临时文件、备份和测试数据。")
    print("建议在执行前备份重要文件。")
    confirm = input("是否继续? (y/n): ")
    
    if confirm.lower() == 'y':
        cleanup_project()
    else:
        print("操作已取消") 