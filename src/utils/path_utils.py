#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
路径工具模块
提供与路径相关的工具函数
"""

import os
import sys
from pathlib import Path
import logging

# 获取日志
logger = logging.getLogger(__name__)

def get_project_root() -> Path:
    """
    获取项目根目录的路径
    
    Returns:
        Path: 项目根目录的Path对象
    """
    try:
        # 尝试从当前文件位置推断项目根目录
        # 假设当前文件在 src/utils/ 目录下
        current_file = Path(__file__).resolve()
        # 向上两级即为项目根目录
        project_root = current_file.parent.parent.parent
        
        # 验证这是否是项目根目录（检查一些关键文件或目录是否存在）
        if (project_root / "src").exists() and (project_root / "配置和信息").exists():
            return project_root
        
        # 如果通过文件位置无法确定，则尝试使用当前工作目录
        cwd = Path.cwd()
        if (cwd / "src").exists() and (cwd / "配置和信息").exists():
            return cwd
        
        # 如果都无法确定，则使用脚本运行目录
        script_dir = Path(sys.path[0])
        if (script_dir / "src").exists() and (script_dir / "配置和信息").exists():
            return script_dir
        
        # 如果所有方法都失败，则返回当前工作目录并记录警告
        logger.warning(f"无法确定项目根目录，使用当前工作目录: {cwd}")
        return cwd
    
    except Exception as e:
        # 出现异常时，返回当前工作目录
        cwd = Path.cwd()
        logger.error(f"获取项目根目录时出错: {str(e)}，使用当前工作目录: {cwd}")
        return cwd

def get_config_dir() -> Path:
    """
    获取配置目录的路径
    
    Returns:
        Path: 配置目录的Path对象
    """
    return get_project_root() / "配置和信息" 