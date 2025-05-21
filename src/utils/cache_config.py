#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
缓存配置模块
用于管理缓存文件的存储位置
"""

import os
import json
import logging
from pathlib import Path

# 导入路径工具
from .path_utils import get_config_dir, get_project_root

# 日志设置
logger = logging.getLogger(__name__)

# 获取系统临时目录
def get_system_temp_dir():
    """获取系统临时目录，优先使用项目内的temp目录"""
    # 优先使用项目内的temp目录
    project_temp = str(get_project_root() / "temp")
    try:
        os.makedirs(project_temp, exist_ok=True)
        return project_temp
    except Exception as e:
        logger.warning(f"无法创建项目内临时目录: {e}")
    
    # 其次尝试使用D盘
    d_drive_path = "D:\\VideoMixTool_Temp"
    if os.path.exists("D:\\") or os.access("D:\\", os.W_OK):
        try:
            os.makedirs(d_drive_path, exist_ok=True)
            return d_drive_path
        except Exception as e:
            logger.warning(f"无法创建D盘临时目录: {e}")
    
    # 再次尝试使用环境变量中的临时目录
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir and os.path.exists(temp_dir):
        # 检查是否在C盘
        if temp_dir.lower().startswith("c:"):
            logger.warning(f"系统临时目录在C盘: {temp_dir}，尝试使用其他盘...")
            # 尝试查找其他可用的磁盘
            for drive in ['D:', 'E:', 'F:', 'G:']:
                try:
                    if os.path.exists(f"{drive}\\"):
                        alt_path = f"{drive}\\VideoMixTool_Temp"
                        os.makedirs(alt_path, exist_ok=True)
                        logger.info(f"使用非C盘临时目录: {alt_path}")
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

# 默认配置
DEFAULT_CONFIG = {
    "cache_dir": get_system_temp_dir(),  # 优先使用项目内的temp目录
}

# 配置文件路径
CONFIG_DIR = get_config_dir()
CONFIG_FILE = CONFIG_DIR / "cache_config_global.json"


class CacheConfig:
    """缓存配置管理类"""
    
    def __init__(self):
        """初始化缓存配置类"""
        # 默认配置
        self.config = DEFAULT_CONFIG.copy()
        
        # 加载已有配置
        self.load_config()
    
    def _load_config(self):
        """从配置文件加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 更新配置，保留默认值
                    for key, value in loaded_config.items():
                        if key in self.config:
                            self.config[key] = value
                logger.info(f"已从 {CONFIG_FILE} 加载缓存配置")
            else:
                # 如果配置文件不存在，创建默认配置
                self._save_config()
        except Exception as e:
            logger.error(f"加载缓存配置出错: {e}")
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存缓存配置到 {CONFIG_FILE}")
        except Exception as e:
            logger.error(f"保存缓存配置出错: {e}")
    
    def get_cache_dir(self) -> str:
        """
        获取当前配置的缓存目录
        
        Returns:
            str: 缓存目录路径
        """
        cache_dir = self.config.get("cache_dir", DEFAULT_CONFIG["cache_dir"])
        
        # 确保目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        return cache_dir
    
    def set_cache_dir(self, cache_dir: str) -> bool:
        """
        设置缓存目录
        
        Args:
            cache_dir: 新的缓存目录路径
            
        Returns:
            bool: 设置是否成功
        """
        if not cache_dir:
            logger.error("缓存目录路径不能为空")
            return False
        
        try:
            # 转换为Path对象处理路径
            cache_path = Path(cache_dir)
            
            # 创建目录（如果不存在）
            os.makedirs(cache_path, exist_ok=True)
            
            # 检查目录是否可写
            test_file = cache_path / f"test_write_{os.getpid()}.tmp"
            try:
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                logger.error(f"缓存目录不可写: {str(e)}")
                return False
            
            # 更新配置
            self.config["cache_dir"] = str(cache_path)
            self._save_config()
            
            logger.info(f"已设置缓存目录: {cache_path}")
            return True
        except Exception as e:
            logger.error(f"设置缓存目录时出错: {str(e)}")
            return False
    
    def load_config(self):
        """加载配置"""
        self._load_config()
    
    def save_config(self):
        """保存配置"""
        self._save_config() 