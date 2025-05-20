#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理器模块
用于管理项目配置和用户配置，支持将配置保存到项目目录或用户目录
"""

import os
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# 日志设置
logger = logging.getLogger(__name__)

class ConfigManager:
    """配置管理器类，处理项目配置和用户配置的加载和保存"""
    
    def __init__(self):
        """初始化配置管理器"""
        # 获取项目根目录和用户配置目录
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.user_config_dir = Path.home() / "VideoMixTool"
        
        # 确保两个目录都存在
        self.user_config_dir.mkdir(parents=True, exist_ok=True)
        
        # 定义配置文件路径
        self.project_config_file = self.project_root / "config.json"
        self.user_settings_file = self.user_config_dir / "user_settings.json"
        self.cache_config_file = self.user_config_dir / "cache_config.json"
        
        # 当前正在使用的配置来源
        self.current_config_source = "user"  # "user" 或 "project"
        
        # 加载配置
        self.config = self._load_config()
        
        logger.info(f"配置管理器初始化完成，当前配置来源: {self.current_config_source}")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        加载配置，优先从项目配置文件加载，如果不存在则从用户配置加载
        
        Returns:
            Dict[str, Any]: 加载的配置
        """
        config = {}
        
        # 检查项目配置文件是否存在
        if self.project_config_file.exists():
            try:
                with open(self.project_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.current_config_source = "project"
                logger.info(f"从项目配置文件加载配置: {self.project_config_file}")
                return config
            except Exception as e:
                logger.error(f"加载项目配置文件时出错: {e}")
        
        # 如果项目配置不存在或加载失败，尝试加载用户配置
        try:
            if self.user_settings_file.exists():
                with open(self.user_settings_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                self.current_config_source = "user"
                logger.info(f"从用户配置文件加载配置: {self.user_settings_file}")
            else:
                logger.warning("用户配置文件不存在，将使用默认配置")
                self.current_config_source = "default"
        except Exception as e:
            logger.error(f"加载用户配置文件时出错: {e}")
            self.current_config_source = "default"
        
        return config
    
    def save_to_project(self, config: Dict[str, Any]) -> bool:
        """
        将配置保存到项目目录
        
        Args:
            config: 要保存的配置
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 在保存前创建备份
            if self.project_config_file.exists():
                backup_file = self.project_root / "config.json.bak"
                shutil.copy2(self.project_config_file, backup_file)
                logger.info(f"已创建项目配置备份: {backup_file}")
            
            # 保存配置
            with open(self.project_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            self.current_config_source = "project"
            logger.info(f"已将配置保存到项目配置文件: {self.project_config_file}")
            return True
        except Exception as e:
            logger.error(f"保存项目配置文件时出错: {e}")
            return False
    
    def save_to_user(self, config: Dict[str, Any]) -> bool:
        """
        将配置保存到用户目录
        
        Args:
            config: 要保存的配置
            
        Returns:
            bool: 保存是否成功
        """
        try:
            # 在保存前创建备份
            if self.user_settings_file.exists():
                backup_file = self.user_config_dir / "user_settings.json.bak"
                shutil.copy2(self.user_settings_file, backup_file)
                logger.info(f"已创建用户配置备份: {backup_file}")
            
            # 确保目录存在
            self.user_config_dir.mkdir(parents=True, exist_ok=True)
            
            # 保存配置
            with open(self.user_settings_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            
            self.current_config_source = "user"
            logger.info(f"已将配置保存到用户配置文件: {self.user_settings_file}")
            return True
        except Exception as e:
            logger.error(f"保存用户配置文件时出错: {e}")
            return False
    
    def get_config_source(self) -> str:
        """
        获取当前配置来源
        
        Returns:
            str: 当前配置来源，可能的值：'project'、'user'或'default'
        """
        return self.current_config_source
    
    def import_config_from_file(self, file_path: str) -> Tuple[bool, Dict[str, Any]]:
        """
        从文件导入配置
        
        Args:
            file_path: 配置文件路径
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (是否成功, 导入的配置)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"从文件导入配置成功: {file_path}")
            return True, config
        except Exception as e:
            logger.error(f"从文件导入配置时出错: {e}")
            return False, {}
    
    def export_config_to_file(self, config: Dict[str, Any], file_path: str) -> bool:
        """
        将配置导出到文件
        
        Args:
            config: 要导出的配置
            file_path: 导出文件路径
            
        Returns:
            bool: 导出是否成功
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
            logger.info(f"配置导出成功: {file_path}")
            return True
        except Exception as e:
            logger.error(f"导出配置到文件时出错: {e}")
            return False
    
    def get_configs_difference(self, config1: Dict[str, Any], config2: Dict[str, Any]) -> Dict[str, List[Any]]:
        """
        比较两个配置的差异
        
        Args:
            config1: 第一个配置
            config2: 第二个配置
            
        Returns:
            Dict[str, List[Any]]: 差异字典，格式为 {key: [config1_value, config2_value]}
        """
        diff = {}
        
        # 检查config1中有但config2中不同的项
        for key, value in config1.items():
            if key in config2:
                if value != config2[key]:
                    diff[key] = [value, config2[key]]
            else:
                diff[key] = [value, None]
        
        # 检查config2中有但config1中没有的项
        for key, value in config2.items():
            if key not in config1:
                diff[key] = [None, value]
        
        return diff 