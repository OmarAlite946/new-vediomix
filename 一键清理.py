#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
一键清理工具：清理项目中的所有无关文件，减小项目体积
"""

import os
import shutil
import sys
from pathlib import Path
import logging
import time
import subprocess

# 设置日志
log_filename = f"一键清理_{int(time.time())}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
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
    "src/__pycache__",
    
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

# 递归查找所有__pycache__目录
def find_pycache_dirs():
    pycache_dirs = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        for dir_name in dirs:
            if dir_name == "__pycache__":
                pycache_dirs.append(os.path.join(root, dir_name))
    return pycache_dirs

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
    try:
        for dirpath, dirnames, filenames in os.walk(dir_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)
    except Exception as e:
        logger.error(f"获取目录大小出错: {str(e)}")
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

def cleanup_project_root():
    """清理项目根目录"""
    logger.info("开始清理项目根目录...")
    
    # 获取初始项目大小
    total_initial_size = get_dir_size(PROJECT_ROOT)
    cleaned_size = 0
    
    # 1. 清理所有__pycache__目录
    pycache_dirs = find_pycache_dirs()
    for pycache_dir in pycache_dirs:
        if os.path.exists(pycache_dir):
            dir_size = get_dir_size(pycache_dir)
            cleaned_size += dir_size
            try:
                shutil.rmtree(pycache_dir)
                logger.info(f"删除__pycache__目录: {os.path.relpath(pycache_dir, PROJECT_ROOT)} ({format_size(dir_size)})")
            except Exception as e:
                logger.error(f"删除__pycache__目录出错: {str(e)}")
    
    # 2. 清理根目录中的目录
    for dir_name in os.listdir(PROJECT_ROOT):
        dir_path = os.path.join(PROJECT_ROOT, dir_name)
        
        # 处理目录
        if os.path.isdir(dir_path):
            if is_safe_to_delete_dir(dir_path):
                dir_size = get_dir_size(dir_path)
                cleaned_size += dir_size
                logger.info(f"删除目录: {dir_name} ({format_size(dir_size)})")
                try:
                    shutil.rmtree(dir_path)
                except Exception as e:
                    logger.error(f"删除目录 {dir_name} 失败: {str(e)}")
    
    # 3. 清理根目录中的文件
    for file_name in os.listdir(PROJECT_ROOT):
        file_path = os.path.join(PROJECT_ROOT, file_name)
        
        # 处理文件
        if os.path.isfile(file_path) and file_path != os.path.abspath(__file__):  # 不删除当前脚本
            if is_safe_to_delete_file(file_path):
                file_size = os.path.getsize(file_path)
                cleaned_size += file_size
                logger.info(f"删除文件: {file_name} ({format_size(file_size)})")
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"删除文件 {file_name} 失败: {str(e)}")
    
    # 获取清理后的项目大小
    total_final_size = get_dir_size(PROJECT_ROOT)
    space_freed = total_initial_size - total_final_size
    
    logger.info("项目根目录清理完成!")
    logger.info(f"初始项目大小: {format_size(total_initial_size)}")
    logger.info(f"清理后项目大小: {format_size(total_final_size)}")
    logger.info(f"释放的空间: {format_size(space_freed)}")
    
    return space_freed

def clean_dist_directory():
    """清理dist目录中的大型文件"""
    logger.info("开始检查dist目录...")
    
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    if not os.path.exists(dist_dir):
        logger.info("dist目录不存在，跳过此步骤")
        return 0
    
    # 定义大文件阈值 (2MB)
    big_file_threshold = 2 * 1024 * 1024  # 2MB
    
    # 强制删除的文件
    force_delete_files = [
        "ffmpeg-win-x86_64-v7.1.exe",  # FFmpeg可以单独提供
        "cv2/cv2.pyd",                 # 可以减小分发包体积
    ]
    
    # 需要保留的文件扩展名
    keep_extensions = [
        ".exe",       # 主程序可执行文件
        ".py",        # Python源文件
        ".md",        # 文档
        ".txt",       # 文本文件
        ".json",      # 配置文件
    ]
    
    dist_size_before = get_dir_size(dist_dir)
    deleted_count = 0
    cleaned_size = 0
    
    # 清理大文件
    for root, dirs, files in os.walk(dist_dir, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                rel_path = os.path.relpath(file_path, dist_dir)
                file_size = os.path.getsize(file_path)
                file_ext = os.path.splitext(file)[1].lower()
                
                # 检查是否在强制删除列表中
                force_delete = any(fd in rel_path.replace("\\", "/") for fd in force_delete_files)
                
                # 检查是否为大文件且不在保留扩展名中
                is_big_file = file_size > big_file_threshold and file_ext not in keep_extensions
                
                if force_delete or is_big_file:
                    logger.info(f"删除dist文件: {rel_path} ({format_size(file_size)})")
                    os.remove(file_path)
                    cleaned_size += file_size
                    deleted_count += 1
            except Exception as e:
                logger.error(f"处理文件时出错 {file_path}: {str(e)}")
    
    # 删除空目录
    for root, dirs, files in os.walk(dist_dir, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # 检查目录是否为空
                    os.rmdir(dir_path)
                    logger.info(f"删除空目录: {os.path.relpath(dir_path, dist_dir)}")
            except Exception as e:
                logger.error(f"删除目录时出错 {dir_path}: {str(e)}")
    
    dist_size_after = get_dir_size(dist_dir) if os.path.exists(dist_dir) else 0
    logger.info(f"dist目录清理完成! 删除了 {deleted_count} 个文件，释放了 {format_size(cleaned_size)} 空间")
    
    return cleaned_size

def delete_ffmpeg_archives():
    """删除项目中的FFmpeg压缩包"""
    logger.info("正在查找FFmpeg相关大文件...")
    
    # 查找ffmpeg压缩包
    ffmpeg_files = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        for file in files:
            if "ffmpeg" in file.lower() and file.endswith((".zip", ".7z", ".tar", ".gz")):
                ffmpeg_files.append(os.path.join(root, file))
    
    total_size = 0
    for file_path in ffmpeg_files:
        try:
            file_size = os.path.getsize(file_path)
            total_size += file_size
            logger.info(f"删除FFmpeg文件: {os.path.relpath(file_path, PROJECT_ROOT)} ({format_size(file_size)})")
            os.remove(file_path)
        except Exception as e:
            logger.error(f"删除FFmpeg文件时出错 {file_path}: {str(e)}")
    
    logger.info(f"FFmpeg相关文件清理完成! 释放了 {format_size(total_size)} 空间")
    return total_size

def main():
    """主函数，执行所有清理操作"""
    print("=" * 50)
    print("项目一键清理工具")
    print("=" * 50)
    print("此工具将清理项目中的无关文件，减小项目体积")
    print("清理项目：")
    print("1. 删除临时文件和缓存目录")
    print("2. 删除备份目录")
    print("3. 删除测试目录和测试文件")
    print("4. 删除日志文件")
    print("5. 删除构建和打包目录")
    print("6. 删除大型二进制文件")
    print("7. 清理dist目录中的大文件")
    print("\n注意：此操作不可逆，请确保重要文件已备份")
    print("=" * 50)
    
    confirm = input("是否继续清理? (y/n): ")
    if confirm.lower() != 'y':
        print("操作已取消")
        return
    
    start_time = time.time()
    logger.info("开始一键清理操作...")
    
    # 总清理空间
    total_cleaned = 0
    
    # 1. 清理项目根目录
    root_cleaned = cleanup_project_root()
    total_cleaned += root_cleaned
    
    # 2. 清理dist目录
    dist_cleaned = clean_dist_directory()
    total_cleaned += dist_cleaned
    
    # 3. 删除FFmpeg相关大文件
    ffmpeg_cleaned = delete_ffmpeg_archives()
    total_cleaned += ffmpeg_cleaned
    
    # 记录清理总结果
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info("=" * 50)
    logger.info("清理操作完成！")
    logger.info(f"总计释放空间: {format_size(total_cleaned)}")
    logger.info(f"用时: {duration:.2f} 秒")
    logger.info("=" * 50)
    
    # 打印统计信息
    print("\n" + "=" * 50)
    print("清理完成！")
    print(f"总计释放空间: {format_size(total_cleaned)}")
    print(f"用时: {duration:.2f} 秒")
    print(f"详细日志已保存到: {log_filename}")
    print("=" * 50)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n操作被用户中断")
    except Exception as e:
        logger.error(f"清理过程中出错: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"清理过程中出错: {str(e)}")
    
    input("\n按Enter键退出...") 