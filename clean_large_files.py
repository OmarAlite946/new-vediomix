import os
import shutil
import sys
import re
import time
from pathlib import Path

def format_size(size):
    """将字节大小转换为可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0 or unit == 'GB':
            break
        size /= 1024.0
    return f"{size:.2f} {unit}"

def get_system_temp_dir():
    """获取系统临时目录，按优先级返回可能的临时目录列表"""
    temp_dirs = []
    
    # 优先检查D盘的固定位置
    d_drive_path = Path("D:\\VideoMixTool_Temp")
    if d_drive_path.exists():
        temp_dirs.append(d_drive_path)
    
    # 检查环境变量中的临时目录
    env_temp = os.environ.get("TEMP") or os.environ.get("TMP")
    if env_temp and os.path.exists(env_temp):
        env_temp_path = Path(env_temp) / "VideoMixTool"
        if env_temp_path.exists():
            temp_dirs.append(env_temp_path)
    
    # 检查其他可能的驱动器位置
    for drive in ["D:", "E:", "F:", "G:"]:
        alt_path = Path(f"{drive}\\VideoMixTool_Temp")
        if alt_path.exists() and alt_path not in temp_dirs:
            temp_dirs.append(alt_path)
    
    return temp_dirs

def find_and_clean_large_files(directory='.', size_limit_mb=50, delete=False):
    """
    查找并可选删除大于指定大小的文件
    Args:
        directory: 起始目录
        size_limit_mb: 大小阈值（MB）
        delete: 是否删除文件
    """
    size_limit = size_limit_mb * 1024 * 1024  # 转换为字节
    large_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                if file_size > size_limit:
                    large_files.append((file_path, file_size))
            except (OSError, FileNotFoundError):
                pass
    
    # 按大小排序
    large_files = sorted(large_files, key=lambda x: x[1], reverse=True)
    
    if large_files:
        print(f"找到 {len(large_files)} 个大于 {size_limit_mb}MB 的文件:")
        for file_path, size in large_files:
            print(f"{file_path} - {format_size(size)}")
            
            if delete:
                try:
                    print(f"正在删除: {file_path}")
                    os.remove(file_path)
                    print(f"删除成功!")
                except Exception as e:
                    print(f"删除失败: {e}")
    else:
        print(f"未找到大于 {size_limit_mb}MB 的文件")

def clean_temp_directory():
    """清空temp目录，但保留目录结构"""
    # 清理本地temp目录
    local_temp_dir = "temp"
    if os.path.exists(local_temp_dir):
        print(f"正在清理本地 {local_temp_dir} 目录...")
        for root, dirs, files in os.walk(local_temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    file_size = os.path.getsize(file_path)
                    # 只删除超过10MB的文件
                    if file_size > 10 * 1024 * 1024:
                        print(f"正在删除: {file_path} ({format_size(file_size)})")
                        os.remove(file_path)
                except Exception as e:
                    print(f"删除失败 {file_path}: {e}")
        print("本地temp目录清理完成")
    
    # 清理可能存在的所有系统临时目录中的项目文件
    system_temp_dirs = get_system_temp_dir()
    for temp_dir in system_temp_dirs:
        print(f"正在清理临时目录: {temp_dir}...")
        try:
            for item in temp_dir.glob("*"):
                if item.is_file():
                    try:
                        file_size = item.stat().st_size
                        if file_size > 10 * 1024 * 1024:  # 只删除超过10MB的文件
                            print(f"正在删除: {item} ({format_size(file_size)})")
                            item.unlink()
                    except Exception as e:
                        print(f"删除失败 {item}: {e}")
                elif item.is_dir():
                    try:
                        dir_size = sum(f.stat().st_size for f in item.glob('**/*') if f.is_file())
                        print(f"正在删除目录: {item} ({format_size(dir_size)})")
                        shutil.rmtree(item, ignore_errors=True)
                    except Exception as e:
                        print(f"删除目录失败 {item}: {e}")
            print(f"目录 {temp_dir} 清理完成")
        except Exception as e:
            print(f"清理目录 {temp_dir} 时发生错误: {e}")

if __name__ == "__main__":
    action = "scan"  # 默认只扫描，不删除
    
    if len(sys.argv) > 1:
        if sys.argv[1].lower() in ["delete", "clean", "remove"]:
            action = "delete"
        elif sys.argv[1].lower() == "cleantemp":
            action = "cleantemp"
    
    if action == "scan":
        print("=== 仅扫描模式，不会删除文件 ===")
        print("要删除文件，请使用: python clean_large_files.py delete")
        find_and_clean_large_files(size_limit_mb=50, delete=False)
    elif action == "delete":
        print("=== 删除模式，将删除大文件 ===")
        find_and_clean_large_files(size_limit_mb=50, delete=True)
    elif action == "cleantemp":
        print("=== 清理临时目录模式 ===")
        clean_temp_directory() 