#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
用户设置模块
用于保存和加载用户界面设置，使程序在下次启动时能够记住上次的设置
"""

import os
import json
import logging
import uuid
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional

# 日志设置
logger = logging.getLogger(__name__)

# 获取项目根目录
def get_project_root() -> Path:
    """获取项目根目录"""
    # 从当前文件位置向上查找项目根目录
    current_file = Path(__file__).resolve()
    # 向上查找3级目录（src/utils/user_settings.py -> src/utils -> src -> 项目根目录）
    project_root = current_file.parent.parent.parent
    return project_root

# 配置文件路径（修改为项目目录）
PROJECT_ROOT = get_project_root()
CONFIG_DIR = PROJECT_ROOT / "配置和信息"
# 确保配置目录存在
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_FILE = CONFIG_DIR / "user_settings.json"

# 默认设置
DEFAULT_SETTINGS = {
    # 导入素材设置
    "import_folder": "",           # 最后导入的文件夹路径
    "last_material_folders": [],   # 最后导入的素材文件夹列表 
    "folder_extract_modes": {},    # 文件夹抽取模式设置
    
    # 输出目录设置
    "save_dir": "",                # 保存目录
    
    # 视频参数设置
    "resolution": "竖屏 1080x1920", # 默认分辨率
    "bitrate": 5000,               # 默认比特率
    "original_bitrate": False,     # 是否使用原始比特率
    "transition": "不使用转场",      # 默认转场效果
    "gpu": "自动检测",              # 默认GPU选项
    "encode_mode": "标准模式",       # 编码模式
    
    # 水印设置
    "watermark_enabled": False,    # 是否启用水印
    "watermark_prefix": "",        # 水印前缀
    "watermark_size": 36,          # 水印大小
    "watermark_color": "#FFFFFF",  # 水印颜色
    "watermark_position": "右下角", # 水印位置
    "watermark_pos_x": 10,         # 水印X偏移
    "watermark_pos_y": 10,         # 水印Y偏移
    
    # 音频设置
    "voice_volume": 100,           # 配音音量
    "bgm_volume": 50,              # 背景音乐音量
    "bgm_path": "",                # 背景音乐路径
    "audio_mode": "自动识别",        # 音频处理模式
    
    # 批量处理设置
    "generate_count": 1,           # 生成数量
    
    # 缓存设置
    "cache_dir": "",               # 缓存目录
    
    # 界面状态
    "last_active_tab": 0,          # 最后活动的标签页索引
    "main_window_size": [1200, 800], # 主窗口大小
    "main_window_pos": [100, 100],   # 主窗口位置
    
    # 最后一次操作状态
    "last_operation_success": True    # 最后一次操作是否成功
}


class UserSettings:
    """用户设置管理类"""
    
    # 存储多实例的设置
    _instances = {}
    
    def __init__(self, instance_id: str = None):
        """
        初始化用户设置
        
        Args:
            instance_id: 实例ID，用于区分不同的设置文件
        """
        # 初始化内部设置变量
        self._settings = DEFAULT_SETTINGS.copy()
        
        # 设置实例标识符
        self._instance_id = None  # 先初始化为None，避免在instance_id setter中调用load_settings时出现问题
        self.instance_id = instance_id or str(uuid.uuid4())[:8]
        
        # 设置文件路径（修改为项目目录）
        self.settings_dir = CONFIG_DIR
        self.settings_file = self.settings_dir / f"user_settings_{self.instance_id}.json"
        
        # 确保设置目录存在
        self.settings_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载设置
        try:
            self.load_settings()
        except Exception as e:
            logger.error(f"加载设置时出错: {e}，使用默认设置")
            self._settings = DEFAULT_SETTINGS.copy()
        
        # 记录实例
        UserSettings._instances[self.instance_id] = self
        
        # 记录标识符
        logger.debug(f"创建新的用户设置实例: {self.instance_id}")
    
    @property
    def settings(self):
        """获取设置字典的属性getter，确保总是有值"""
        if not hasattr(self, '_settings') or self._settings is None:
            logger.warning("settings属性不存在或为None，重新创建默认设置")
            self._settings = DEFAULT_SETTINGS.copy()
        return self._settings
    
    @settings.setter
    def settings(self, value):
        """设置字典的属性setter"""
        if value is None:
            logger.warning("尝试将settings设置为None，使用默认值")
            self._settings = DEFAULT_SETTINGS.copy()
        else:
            self._settings = value
    
    def __getattr__(self, name):
        """
        确保即使settings属性丢失也能正常工作
        
        Args:
            name: 属性名
            
        Returns:
            对应的属性值
        """
        # 如果尝试访问settings属性但不存在，则重新创建
        if name == "settings":
            logger.warning("通过__getattr__访问settings属性，重新创建默认设置")
            self._settings = DEFAULT_SETTINGS.copy()
            return self._settings
        # 对于其他属性，抛出正常的AttributeError
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    @property
    def instance_id(self):
        """获取实例ID"""
        return self._instance_id
    
    @instance_id.setter
    def instance_id(self, value):
        """设置实例ID"""
        if not value:
            value = f"global_{uuid.uuid4().hex[:8]}"
        
        # 规范化实例ID，确保不会有特殊字符导致文件名问题
        sanitized_id = value
        if not isinstance(value, str):
            sanitized_id = str(value)
        
        # 如果ID太长，使用哈希值缩短它
        if len(sanitized_id) > 50:
            hash_obj = hashlib.md5(sanitized_id.encode())
            sanitized_id = f"tab_{hash_obj.hexdigest()[:16]}"
        
        # 确保实例ID有效（移除非法字符）
        sanitized_id = "".join(c for c in sanitized_id if c.isalnum() or c in "_-.")
        if not sanitized_id:
            sanitized_id = f"tab_{uuid.uuid4().hex[:16]}"
        
        self._instance_id = sanitized_id
        
        # 如果实例ID发生变化，重新加载设置
        logger.debug(f"设置实例ID: {self._instance_id}")
        self.load_settings()
    
    def _get_settings_file(self):
        """获取当前实例的设置文件路径"""
        # 修改为使用项目目录中的配置文件
        if self.instance_id == "global" or self.instance_id.startswith("global_"):
            return CONFIG_DIR / "user_settings_global.json"
        else:
            # 为每个实例创建单独的设置文件，确保文件名有效
            settings_filename = f"user_settings_{self.instance_id}.json"
            return CONFIG_DIR / settings_filename
    
    def _load_settings(self) -> bool:
        """
        从配置文件加载设置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                self._settings = DEFAULT_SETTINGS.copy()
                
            settings_file = self._get_settings_file()
            
            # 首先加载全局设置作为基础
            global_settings_file = CONFIG_DIR / "user_settings_global.json"
            if not self.instance_id.startswith("global") and global_settings_file.exists():
                try:
                    with open(global_settings_file, 'r', encoding='utf-8') as f:
                        global_settings = json.load(f)
                        # 更新设置，保留默认值
                        for key, value in global_settings.items():
                            if key in self._settings:
                                self._settings[key] = value
                    logger.info(f"已从项目目录加载全局设置: {global_settings_file}")
                except Exception as e:
                    logger.warning(f"加载全局设置作为基础时出错: {e}")
            
            # 然后加载实例特定设置
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    
                    # 检查设置文件的完整性
                    if not isinstance(loaded_settings, dict):
                        logger.warning(f"设置文件 {settings_file} 格式错误，使用默认设置")
                        return False
                    
                    # 更新设置，保留默认值
                    for key, value in loaded_settings.items():
                        if key in self._settings:
                            self._settings[key] = value
                logger.info(f"已从项目目录加载用户设置: {settings_file}，实例ID: {self.instance_id}")
                return True
            else:
                # 如果配置文件不存在，使用全局设置或默认设置
                if not self.instance_id.startswith("global"):
                    logger.info(f"实例 {self.instance_id} 无独立设置文件，使用全局设置或默认设置")
                else:
                    # 如果是全局设置，创建默认设置文件
                    self._save_settings()
                    logger.info(f"创建了默认用户设置文件: {settings_file}")
                return True
        except Exception as e:
            logger.error(f"加载用户设置出错: {e}")
            # 确保settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                self._settings = DEFAULT_SETTINGS.copy()
            # 创建备份以防止损坏
            self._save_settings_backup()
            return False
    
    def _save_settings_backup(self):
        """保存设置备份"""
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                self._settings = DEFAULT_SETTINGS.copy()
                
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            settings_file = self._get_settings_file()
            backup_file = settings_file.with_suffix(f".bak.{uuid.uuid4().hex[:8]}")
            
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存用户设置备份到项目目录: {backup_file}")
            
            # 清理旧备份文件
            backup_pattern = f"user_settings*.bak.*"
            backup_files = sorted(CONFIG_DIR.glob(backup_pattern), 
                                key=lambda x: os.path.getmtime(x),
                                reverse=True)
            
            # 保留最新的3个备份
            for old_file in backup_files[3:]:
                try:
                    old_file.unlink()
                    logger.debug(f"删除旧备份文件: {old_file}")
                except Exception as e:
                    logger.warning(f"删除旧备份文件失败: {e}")
                
        except Exception as e:
            logger.error(f"保存用户设置备份到项目目录失败: {e}")
    
    def _save_settings(self) -> bool:
        """
        保存设置到文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                logger.warning("保存设置时_settings不存在，创建默认设置")
                self._settings = DEFAULT_SETTINGS.copy()
                
            # 确保目录存在
            if not CONFIG_DIR.exists():
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            
            settings_file = self._get_settings_file()
            
            # 先保存到临时文件，然后重命名，避免写入过程中文件损坏
            temp_file = settings_file.with_suffix(".tmp")
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            
            # 如果已存在设置文件，先创建备份
            if settings_file.exists():
                try:
                    backup_file = settings_file.with_suffix(f".bak")
                    if backup_file.exists():
                        backup_file.unlink()  # 删除旧备份
                    settings_file.rename(backup_file)  # 创建新备份
                    logger.debug(f"创建设置文件备份: {backup_file}")
                except Exception as e:
                    logger.warning(f"创建设置文件备份失败: {e}")
                    
            # 重命名临时文件为正式文件
            temp_file.rename(settings_file)
            
            logger.info(f"已保存用户设置到项目目录: {settings_file}，实例ID: {self.instance_id}")
            
            # 同时创建一个带时间戳的备份
            self._save_settings_backup()
            
            return True
        except Exception as e:
            logger.error(f"保存用户设置到项目目录出错: {e}，实例ID: {self.instance_id}")
            # 尝试保存备份
            self._save_settings_backup()
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        获取设置值
        
        Args:
            key: 设置键名
            default: 默认值
            
        Returns:
            设置值
        """
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                logger.warning("获取设置时发现_settings不存在，创建默认设置")
                self._settings = DEFAULT_SETTINGS.copy()
                
            return self._settings.get(key, default)
        except Exception as e:
            logger.error(f"获取设置出错: {key}, {e}")
            return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        """
        设置配置值
        
        Args:
            key: 设置键名
            value: 设置值
            
        Returns:
            bool: 是否设置成功
        """
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                logger.warning("设置配置时发现_settings不存在，创建默认设置")
                self._settings = DEFAULT_SETTINGS.copy()
                
            # 设置值
            self._settings[key] = value
            
            # 保存设置
            return self._save_settings()
        except Exception as e:
            logger.error(f"设置配置值失败: {key}={value}, {e}")
            return False
    
    def set_multiple_settings(self, settings_dict: Dict[str, Any]) -> bool:
        """
        设置多个配置项
        
        Args:
            settings_dict: 包含多个设置的字典
            
        Returns:
            bool: 是否全部设置成功
        """
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                logger.warning("批量设置配置时发现_settings不存在，创建默认设置")
                self._settings = DEFAULT_SETTINGS.copy()
                
            # 更新设置
            for key, value in settings_dict.items():
                self._settings[key] = value
            
            # 保存设置
            return self._save_settings()
        except Exception as e:
            logger.error(f"批量设置配置失败: {e}")
            return False
    
    def get_all_settings(self) -> Dict[str, Any]:
        """
        获取所有设置
        
        Returns:
            Dict[str, Any]: 所有设置的字典
        """
        # 确保_settings属性存在
        if not hasattr(self, '_settings') or self._settings is None:
            logger.warning("获取所有设置时发现_settings不存在，创建默认设置")
            self._settings = DEFAULT_SETTINGS.copy()
            
        return self._settings.copy()
    
    def reset_to_defaults(self) -> bool:
        """
        将设置重置为默认值
        
        Returns:
            bool: 重置是否成功
        """
        self._settings = DEFAULT_SETTINGS.copy()
        logger.info(f"重置实例 {self.instance_id} 的设置为默认值")
        return self._save_settings()
    
    def load_settings(self) -> bool:
        """
        从文件加载设置
        
        Returns:
            bool: 加载是否成功
        """
        try:
            # 确保_settings存在
            if not hasattr(self, '_settings') or self._settings is None:
                self._settings = DEFAULT_SETTINGS.copy()
                
            # 调用内部实现方法
            return self._load_settings()
        except Exception as e:
            logger.error(f"调用load_settings方法出错: {e}")
            # 确保至少有默认设置
            self._settings = DEFAULT_SETTINGS.copy()
            return False
    
    def save_settings(self) -> bool:
        """
        保存设置到文件
        
        Returns:
            bool: 保存是否成功
        """
        try:
            # 确保_settings属性存在
            if not hasattr(self, '_settings') or self._settings is None:
                logger.warning("保存设置时_settings不存在，创建默认设置")
                self._settings = DEFAULT_SETTINGS.copy()
                
            # 调用内部实现方法
            return self._save_settings()
        except Exception as e:
            logger.error(f"调用save_settings方法出错: {e}")
            return False 