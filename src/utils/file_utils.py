#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件操作实用工具模块
处理视频混剪过程中的文件和目录操作
"""

import os
import re
import shutil
import tempfile
import concurrent.futures
import uuid
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Union, Callable, Pattern, Set

from src.utils.logger import get_logger

logger = get_logger()

# 视频和音频文件扩展名
video_extensions = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm"}
audio_extensions = {".mp3", ".wav", ".aac", ".ogg", ".flac", ".m4a"}

def resolve_shortcut(shortcut_path):
    """
    解析Windows快捷方式(.lnk)文件，返回目标路径
    
    Args:
        shortcut_path: 快捷方式文件路径
        
    Returns:
        str: 目标路径，如果解析失败则返回None
    """
    import sys
    import subprocess
    import time
    
    # 检查路径是否有效
    if not shortcut_path or not os.path.exists(shortcut_path):
        logger.warning(f"快捷方式路径无效或不存在: {shortcut_path}")
        return None
    
    # 检查是否是.lnk文件
    if not shortcut_path.lower().endswith('.lnk'):
        logger.warning(f"文件不是快捷方式(.lnk): {shortcut_path}")
        return None
    
    # 跟踪COM初始化状态
    com_initialized = False
    
    # 方法1: 使用win32com解析快捷方式
    try:
        import win32com.client
        import pythoncom
        
        # 尝试初始化COM（多线程模式）
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
            com_initialized = True
            logger.debug("COM已初始化（多线程模式）")
        except Exception as e:
            logger.debug(f"多线程COM初始化失败: {str(e)}")
            
            # 尝试基本初始化
            try:
                pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED)
                com_initialized = True
                logger.debug("COM已初始化（单线程模式）")
            except Exception as e:
                logger.debug(f"单线程COM初始化失败: {str(e)}")
                
                # 最后尝试最基本的初始化
                try:
                    pythoncom.CoInitialize()
                    com_initialized = True
                    logger.debug("COM已初始化（基本模式）")
                except Exception as e:
                    logger.debug(f"基本COM初始化失败: {str(e)}")
        
        # 创建Shell对象
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        target_path = shortcut.Targetpath
        
        # 检查目标路径是否有效
        if target_path and len(target_path.strip()) > 0:
            logger.debug(f"成功解析快捷方式: {shortcut_path} -> {target_path}")
            
            # 释放COM资源
            if com_initialized:
                try:
                    pythoncom.CoUninitialize()
                    logger.debug("COM资源已释放")
                except:
                    pass
                    
            return target_path
        else:
            logger.warning(f"快捷方式目标为空: {shortcut_path}")
    except Exception as e:
        # 如果是COM初始化错误，尝试重新初始化
        if "尚未调用CoInitialize" in str(e) or "CoInitialize has not been called" in str(e):
            logger.debug(f"COM初始化错误，尝试重新初始化: {str(e)}")
            
            # 重新尝试初始化COM
            try:
                if com_initialized:
                    try:
                        pythoncom.CoUninitialize()
                    except:
                        pass
                
                # 等待一小段时间
                time.sleep(0.2)
                
                # 尝试重新初始化
                pythoncom.CoInitialize()
                com_initialized = True
                
                # 重新创建Shell对象
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                target_path = shortcut.Targetpath
                
                # 检查目标路径是否有效
                if target_path and len(target_path.strip()) > 0:
                    logger.debug(f"重试后成功解析快捷方式: {shortcut_path} -> {target_path}")
                    
                    # 释放COM资源
                    if com_initialized:
                        try:
                            pythoncom.CoUninitialize()
                        except:
                            pass
                            
                    return target_path
                else:
                    logger.warning(f"重试后快捷方式目标为空: {shortcut_path}")
            except Exception as retry_error:
                logger.warning(f"重试解析快捷方式失败: {str(retry_error)}")
        else:
            logger.warning(f"使用win32com解析快捷方式失败: {str(e)}")
    finally:
        # 确保释放COM资源
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except:
                pass
    
    # 方法2: 如果win32com失败，尝试使用PowerShell命令行解析
    try:
        if sys.platform == 'win32':
            # 使用PowerShell命令解析快捷方式
            cmd = ['powershell', '-Command', f'(New-Object -ComObject WScript.Shell).CreateShortcut("{shortcut_path}").TargetPath']
            result = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=5)
            if result.returncode == 0:
                target_path = result.stdout.strip()
                if target_path and len(target_path.strip()) > 0:
                    logger.debug(f"使用PowerShell成功解析快捷方式: {shortcut_path} -> {target_path}")
                    return target_path
                else:
                    logger.warning(f"PowerShell解析的快捷方式目标为空: {shortcut_path}")
    except Exception as e:
        logger.warning(f"使用PowerShell解析快捷方式失败: {str(e)}")
    
    # 方法3: 如果前面的方法都失败了，尝试使用pylnk3库
    try:
        import pylnk3
        target_path = pylnk3.parse(shortcut_path).path
        if target_path and len(target_path.strip()) > 0:
            logger.debug(f"使用pylnk3成功解析快捷方式: {shortcut_path} -> {target_path}")
            return target_path
        else:
            logger.warning(f"pylnk3解析的快捷方式目标为空: {shortcut_path}")
    except ImportError:
        logger.debug("pylnk3库未安装，跳过此方法")
    except Exception as e:
        logger.warning(f"使用pylnk3解析快捷方式失败: {str(e)}")
    
    # 所有方法都失败了
    logger.error(f"无法解析快捷方式: {shortcut_path}")
    return None

def ensure_dir_exists(directory: Union[str, Path]) -> Path:
    """
    确保目录存在，如果不存在则创建
    
    Args:
        directory: 目录路径
        
    Returns:
        Path: 目录路径对象
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return directory

def list_files(directory: Union[str, Path], 
               extensions: List[str] = None, 
               recursive: bool = False,
               name_pattern: str = None) -> List[Path]:
    """
    列出指定目录下的文件
    
    Args:
        directory: 目录路径
        extensions: 文件扩展名列表，如 ['.mp4', '.mov']
        recursive: 是否递归搜索子目录
        name_pattern: 文件名匹配模式（正则表达式）
        
    Returns:
        List[Path]: 文件路径列表
    """
    directory = Path(directory)
    
    if not directory.exists():
        logger.warning(f"目录不存在: {directory}")
        return []
    
    if not directory.is_dir():
        logger.warning(f"不是目录: {directory}")
        return []
    
    # 准备文件名模式
    pattern = None
    if name_pattern:
        try:
            pattern = re.compile(name_pattern)
        except re.error as e:
            logger.error(f"无效的正则表达式模式 '{name_pattern}': {e}")
    
    # 规范化扩展名
    if extensions:
        extensions = [ext.lower() if ext.startswith('.') else f'.{ext.lower()}' for ext in extensions]
    
    files = []
    
    # 递归搜索目录
    if recursive:
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                file_path = Path(root) / filename
                
                # 检查扩展名
                if extensions and file_path.suffix.lower() not in extensions:
                    continue
                
                # 检查文件名模式
                if pattern and not pattern.search(file_path.name):
                    continue
                
                files.append(file_path)
    else:
        for item in directory.iterdir():
            if item.is_file():
                # 检查扩展名
                if extensions and item.suffix.lower() not in extensions:
                    continue
                
                # 检查文件名模式
                if pattern and not pattern.search(item.name):
                    continue
                
                files.append(item)
    
    return sorted(files)

def list_media_files(directory: Union[str, Path], recursive: bool = False) -> Dict[str, List[Path]]:
    """
    列出指定目录下的媒体文件，分类为视频和音频
    
    Args:
        directory: 目录路径
        recursive: 是否递归搜索子目录
        
    Returns:
        Dict[str, List[Path]]: {'videos': [...], 'audios': [...]}
    """
    videos = list_files(directory, extensions=list(video_extensions), recursive=recursive)
    audios = list_files(directory, extensions=list(audio_extensions), recursive=recursive)
    
    return {
        'videos': videos,
        'audios': audios
    }

def copy_files(src_files: List[Union[str, Path]], 
               dest_dir: Union[str, Path], 
               rename_func: Callable = None,
               overwrite: bool = False) -> List[Path]:
    """
    复制文件到目标目录
    
    Args:
        src_files: 源文件路径列表
        dest_dir: 目标目录
        rename_func: 文件重命名函数，接收原文件Path对象，返回新文件名
        overwrite: 是否覆盖已存在的文件
        
    Returns:
        List[Path]: 复制后的文件路径列表
    """
    dest_dir = ensure_dir_exists(dest_dir)
    copied_files = []
    
    for src_file in src_files:
        src_path = Path(src_file)
        
        if not src_path.exists() or not src_path.is_file():
            logger.warning(f"源文件不存在或不是文件: {src_path}")
            continue
        
        # 确定目标文件名
        if rename_func:
            dest_filename = rename_func(src_path)
        else:
            dest_filename = src_path.name
        
        dest_path = dest_dir / dest_filename
        
        # 检查是否存在
        if dest_path.exists() and not overwrite:
            logger.warning(f"目标文件已存在且不覆盖: {dest_path}")
            copied_files.append(dest_path)
            continue
        
        try:
            # 复制文件
            shutil.copy2(src_path, dest_path)
            copied_files.append(dest_path)
            logger.debug(f"复制文件: {src_path} -> {dest_path}")
        except Exception as e:
            logger.error(f"复制文件失败 {src_path} -> {dest_path}: {str(e)}")
    
    logger.info(f"复制了 {len(copied_files)} 个文件到 {dest_dir}")
    return copied_files

def move_files(src_files: List[Union[str, Path]], 
               dest_dir: Union[str, Path], 
               rename_func: Callable = None,
               overwrite: bool = False) -> List[Path]:
    """
    移动文件到目标目录
    
    Args:
        src_files: 源文件路径列表
        dest_dir: 目标目录
        rename_func: 文件重命名函数，接收原文件Path对象，返回新文件名
        overwrite: 是否覆盖已存在的文件
        
    Returns:
        List[Path]: 移动后的文件路径列表
    """
    dest_dir = ensure_dir_exists(dest_dir)
    moved_files = []
    
    for src_file in src_files:
        src_path = Path(src_file)
        
        if not src_path.exists() or not src_path.is_file():
            logger.warning(f"源文件不存在或不是文件: {src_path}")
            continue
        
        # 确定目标文件名
        if rename_func:
            dest_filename = rename_func(src_path)
        else:
            dest_filename = src_path.name
        
        dest_path = dest_dir / dest_filename
        
        # 检查是否存在
        if dest_path.exists():
            if overwrite:
                try:
                    dest_path.unlink()
                except Exception as e:
                    logger.error(f"删除已存在的目标文件失败 {dest_path}: {str(e)}")
                    continue
            else:
                logger.warning(f"目标文件已存在且不覆盖: {dest_path}")
                moved_files.append(dest_path)
                continue
        
        try:
            # 移动文件
            shutil.move(str(src_path), str(dest_path))
            moved_files.append(dest_path)
            logger.debug(f"移动文件: {src_path} -> {dest_path}")
        except Exception as e:
            logger.error(f"移动文件失败 {src_path} -> {dest_path}: {str(e)}")
    
    logger.info(f"移动了 {len(moved_files)} 个文件到 {dest_dir}")
    return moved_files

def delete_files(files: List[Union[str, Path]], ignore_errors: bool = False) -> int:
    """
    删除文件
    
    Args:
        files: 文件路径列表
        ignore_errors: 是否忽略错误
        
    Returns:
        int: 成功删除的文件数量
    """
    deleted_count = 0
    
    for file_path in files:
        file_path = Path(file_path)
        try:
            if file_path.exists() and file_path.is_file():
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"删除文件: {file_path}")
            else:
                if not ignore_errors:
                    logger.warning(f"文件不存在或不是文件: {file_path}")
        except Exception as e:
            if not ignore_errors:
                logger.error(f"删除文件失败 {file_path}: {str(e)}")
    
    logger.info(f"删除了 {deleted_count} 个文件")
    return deleted_count

def create_temp_dir(prefix: str = "videomixtool_", 
                    parent_dir: Union[str, Path] = None) -> Path:
    """
    创建临时目录
    
    Args:
        prefix: 目录名前缀
        parent_dir: 父目录，如果为None则使用系统临时目录
        
    Returns:
        Path: 临时目录路径
    """
    if parent_dir:
        parent_dir = ensure_dir_exists(parent_dir)
        temp_dir = parent_dir / f"{prefix}{uuid.uuid4().hex}"
        temp_dir.mkdir(exist_ok=True)
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix=prefix))
    
    logger.debug(f"创建临时目录: {temp_dir}")
    return temp_dir

def create_temp_file(prefix: str = "videomixtool_", 
                     suffix: str = "", 
                     dir: Union[str, Path] = None) -> Path:
    """
    创建临时文件
    
    Args:
        prefix: 文件名前缀
        suffix: 文件扩展名
        dir: 目录，如果为None则使用系统临时目录
        
    Returns:
        Path: 临时文件路径
    """
    if dir:
        dir = ensure_dir_exists(dir)
    
    temp_file = tempfile.NamedTemporaryFile(delete=False, prefix=prefix, suffix=suffix, dir=dir)
    temp_file.close()
    
    logger.debug(f"创建临时文件: {temp_file.name}")
    return Path(temp_file.name)

def clean_temp_dir(directory: Union[str, Path], 
                   file_pattern: str = None, 
                   older_than: int = None,
                   recursive: bool = False) -> int:
    """
    清理临时目录
    
    Args:
        directory: 目录路径
        file_pattern: 文件名匹配模式（正则表达式）
        older_than: 删除早于指定秒数的文件
        recursive: 是否递归清理子目录
        
    Returns:
        int: 删除的文件数量
    """
    directory = Path(directory)
    
    if not directory.exists() or not directory.is_dir():
        logger.warning(f"目录不存在或不是目录: {directory}")
        return 0
    
    # 准备文件名模式
    pattern = None
    if file_pattern:
        try:
            pattern = re.compile(file_pattern)
        except re.error as e:
            logger.error(f"无效的正则表达式模式 '{file_pattern}': {e}")
    
    # 获取当前时间
    now = time.time() if older_than else None
    
    deleted_count = 0
    
    # 递归搜索目录
    if recursive:
        for root, dirs, files in os.walk(directory):
            for filename in files:
                file_path = Path(root) / filename
                
                # 检查文件名模式
                if pattern and not pattern.search(file_path.name):
                    continue
                
                # 检查文件年龄
                if older_than and (now - file_path.stat().st_mtime) < older_than:
                    continue
                
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"删除临时文件: {file_path}")
                except Exception as e:
                    logger.error(f"删除临时文件失败 {file_path}: {str(e)}")
    else:
        for item in directory.iterdir():
            if item.is_file():
                # 检查文件名模式
                if pattern and not pattern.search(item.name):
                    continue
                
                # 检查文件年龄
                if older_than and (now - item.stat().st_mtime) < older_than:
                    continue
                
                try:
                    item.unlink()
                    deleted_count += 1
                    logger.debug(f"删除临时文件: {item}")
                except Exception as e:
                    logger.error(f"删除临时文件失败 {item}: {str(e)}")
    
    logger.info(f"清理临时目录 {directory}，删除了 {deleted_count} 个文件")
    return deleted_count

def get_valid_filename(name: str) -> str:
    """
    将字符串转换为有效的文件名
    
    Args:
        name: 原始文件名
        
    Returns:
        str: 有效的文件名
    """
    # 替换无效字符为下划线
    s = re.sub(r'[^\w\s.-]', '_', name)
    # 将空白字符替换为下划线
    s = re.sub(r'\s+', '_', s)
    # 删除开头和结尾的点号和空格
    s = s.strip('._')
    # 确保不是空字符串
    return s or 'untitled'

def human_readable_size(size_bytes: int) -> str:
    """
    将字节大小转换为人类可读格式
    
    Args:
        size_bytes: 字节大小
        
    Returns:
        str: 人类可读格式的大小
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    return f"{s} {size_names[i]}"

def get_file_size(file_path: Union[str, Path]) -> int:
    """
    获取文件大小
    
    Args:
        file_path: 文件路径
        
    Returns:
        int: 文件大小（字节）
    """
    file_path = Path(file_path)
    
    if not file_path.exists() or not file_path.is_file():
        logger.warning(f"文件不存在或不是文件: {file_path}")
        return 0
    
    return file_path.stat().st_size

def get_free_space(directory: Union[str, Path]) -> int:
    """
    获取目录所在磁盘的可用空间
    
    Args:
        directory: 目录路径
        
    Returns:
        int: 可用空间（字节）
    """
    directory = Path(directory)
    
    if not directory.exists():
        logger.warning(f"目录不存在: {directory}")
        return 0
    
    try:
        # 使用shutil获取磁盘使用情况
        total, used, free = shutil.disk_usage(str(directory))
        return free
    except Exception as e:
        logger.error(f"获取磁盘可用空间失败 {directory}: {str(e)}")
        return 0

def process_files_parallel(files: List[Union[str, Path]], 
                           process_func: Callable,
                           max_workers: int = None,
                           *args, **kwargs) -> List:
    """
    并行处理文件
    
    Args:
        files: 文件路径列表
        process_func: 处理函数，接收文件路径作为第一个参数
        max_workers: 最大工作线程数
        *args, **kwargs: 传递给处理函数的其他参数
        
    Returns:
        List: 处理结果列表
    """
    results = []
    
    # 设置默认最大工作线程数
    if max_workers is None:
        # 默认为CPU核心数的2倍或者文件数量，取较小值
        max_workers = min(os.cpu_count() * 2, len(files))
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        future_to_file = {
            executor.submit(process_func, file, *args, **kwargs): file
            for file in files
        }
        
        # 收集结果
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"处理文件失败 {file}: {str(e)}")
    
    return results

def find_unused_filename(directory: Union[str, Path], 
                         base_name: str, 
                         extension: str = "") -> Path:
    """
    查找未使用的文件名
    
    Args:
        directory: 目录路径
        base_name: 基本文件名
        extension: 文件扩展名
        
    Returns:
        Path: 未使用的文件路径
    """
    directory = Path(directory)
    
    # 确保扩展名以点号开头
    if extension and not extension.startswith('.'):
        extension = f".{extension}"
    
    # 尝试原始文件名
    file_path = directory / f"{base_name}{extension}"
    
    # 如果文件已存在，添加数字后缀
    counter = 1
    while file_path.exists():
        file_path = directory / f"{base_name}_{counter}{extension}"
        counter += 1
    
    return file_path

# 导入需要的模块
import time
import math 