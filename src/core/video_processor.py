#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
视频处理核心模块
"""

import os
import time
import random
import shutil
import subprocess
import threading
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional, Tuple, Callable
import uuid
import datetime
import logging
import sys
import json
import gc
import traceback

# 添加项目根目录到 Python 路径
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    import cv2
    import numpy as np
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, vfx, CompositeAudioClip
except ImportError as e:
    print(f"正在安装必要的依赖...")
    try:
        import pip
        pip.main(["install", "moviepy", "opencv-python", "numpy"])
        import cv2
        import numpy as np
        from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips, vfx, CompositeAudioClip
    except Exception as install_error:
        print(f"安装依赖失败: {install_error}")
        print("请手动安装依赖：")
        print("pip install moviepy opencv-python numpy")
        sys.exit(1)

from src.utils.logger import get_logger
from src.utils.cache_config import CacheConfig

logger = get_logger()

class VideoProcessor:
    """视频处理核心类"""
    
    def __init__(self, settings: Dict[str, Any] = None, progress_callback: Callable[[str, float], None] = None):
        """
        初始化视频处理器
        
        Args:
            settings: 处理设置参数
            progress_callback: 进度回调函数，参数为(状态消息, 进度百分比)
        """
        # 初始化设置
        self.settings = settings if settings else {}
        self.progress_callback = progress_callback
        self.stop_requested = False
        self.temp_files = []
        self.start_time = 0
        
        # 进度更新定时器
        self._progress_timer = None
        self._last_progress_message = ""
        self._last_progress_percent = 0
        
        # 批量合成进度跟踪
        self._total_videos = 0
        self._completed_videos = 0
        
        # 初始化日志
        global logger
        self.logger = logger  # 将全局logger赋值给实例变量
        if not logger:
            logger = logging.getLogger("VideoProcessor")
            self.logger = logger
        
        # 检查FFmpeg
        self._check_ffmpeg()
        
        # 获取缓存配置
        cache_config = CacheConfig()
        cache_dir = cache_config.get_cache_dir()
        
        # 默认设置
        self.default_settings = {
            "hardware_accel": "auto",  # 硬件加速：auto, cuda, qsv, amf, none
            "encoder": "libx264",       # 视频编码器
            "resolution": "1080p",      # 输出分辨率
            "bitrate": 5000,            # 比特率(kbps)
            "threads": 4,               # 处理线程数
            "transition": "random",     # 转场效果: random, mirror_flip, hue_shift, ...
            "transition_duration": 0.5,  # 转场时长(秒)
            "voice_volume": 1.0,        # 配音音量
            "bgm_volume": 0.5,          # 背景音乐音量
            "output_format": "mp4",     # 输出格式
            "temp_dir": cache_dir,      # 使用配置的缓存目录
            # 添加水印相关默认设置
            "watermark_enabled": False,  # 水印功能默认关闭
            "watermark_prefix": "",      # 默认无自定义前缀
            "watermark_size": 24,        # 默认字体大小24像素
            "watermark_color": "#FFFFFF", # 默认白色
            "watermark_position": "右上角", # 默认位置在右上角
            "watermark_pos_x": 0,        # 默认X轴位置修正
            "watermark_pos_y": 0         # 默认Y轴位置修正
        }
        
        # 更新设置
        self.settings = self.default_settings.copy()
        if settings:
            # 保留原始temp_dir设置
            original_temp_dir = self.default_settings["temp_dir"]
            # 更新所有设置
            self.settings.update(settings)
            # 如果settings中没有提供temp_dir，使用默认的缓存目录
            if "temp_dir" not in settings:
                self.settings["temp_dir"] = original_temp_dir
        
        # 确保临时目录存在
        os.makedirs(self.settings["temp_dir"], exist_ok=True)
        
        # 初始化随机数生成器
        random.seed(time.time())
    
    def _check_ffmpeg(self) -> bool:
        """
        检查FFmpeg是否可用
        
        Returns:
            bool: 是否可用
        """
        ffmpeg_cmd = "ffmpeg"
        ffmpeg_path_file = None
        
        # 尝试从ffmpeg_path.txt读取自定义路径
        try:
            # 获取项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent
            ffmpeg_path_file = project_root / "ffmpeg_path.txt"
            
            if ffmpeg_path_file.exists():
                with open(ffmpeg_path_file, 'r', encoding="utf-8") as f:
                    custom_path = f.read().strip()
                    if custom_path and os.path.exists(custom_path):
                        logger.info(f"使用自定义FFmpeg路径: {custom_path}")
                        ffmpeg_cmd = custom_path
                    else:
                        logger.warning(f"自定义FFmpeg路径无效或不存在: {custom_path}")
        except Exception as e:
            logger.error(f"读取自定义FFmpeg路径时出错: {str(e)}")
        
        try:
            # 尝试执行ffmpeg命令
            logger.info(f"正在检查FFmpeg: {ffmpeg_cmd}")
            result = subprocess.run(
                [ffmpeg_cmd, "-version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True,
                timeout=5  # 增加超时时间
            )
            
            if result.returncode == 0:
                version_info = result.stdout.splitlines()[0] if result.stdout else "未知版本"
                logger.info(f"FFmpeg可用，版本信息：{version_info}")
                
                # 检查编码器支持
                try:
                    encoders_result = subprocess.run(
                        [ffmpeg_cmd, "-encoders"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5
                    )
                    
                    if encoders_result.returncode == 0:
                        encoders_output = encoders_result.stdout
                        # 检查硬件加速编码器
                        hw_encoders = []
                        for encoder in ["nvenc", "qsv", "amf", "vaapi"]:
                            if encoder in encoders_output:
                                hw_encoders.append(encoder)
                        
                        if hw_encoders:
                            logger.info(f"检测到支持的硬件加速编码器: {', '.join(hw_encoders)}")
                        else:
                            logger.info("未检测到支持的硬件加速编码器")
                except Exception as e:
                    logger.warning(f"检查编码器支持时出错: {str(e)}")
                
                return True
            else:
                error_detail = f"返回码: {result.returncode}, 错误: {result.stderr}"
                logger.error(f"FFmpeg不可用: {error_detail}")
                return False
        except FileNotFoundError:
            if ffmpeg_path_file and ffmpeg_path_file.exists():
                error_msg = f"自定义FFmpeg路径不正确，请重新配置。路径: {ffmpeg_cmd}"
            else:
                error_msg = "FFmpeg不在系统路径中，请安装FFmpeg并确保可以在命令行中使用，或使用配置路径功能"
            logger.error(error_msg)
            return False
        except PermissionError:
            logger.error(f"没有执行FFmpeg的权限: {ffmpeg_cmd}")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"检查FFmpeg超时，可能系统资源不足或FFmpeg无响应")
            return False
        except Exception as e:
            logger.error(f"检查FFmpeg时出错: {str(e)}, 类型: {type(e).__name__}")
            return False
    
    def _format_time(self, seconds):
        """
        将秒数格式化为时:分:秒格式
        
        Args:
            seconds: 秒数
            
        Returns:
            str: 格式化后的时间字符串 (HH:MM:SS)
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def report_progress(self, message: str, percent: float):
        """
        报告进度
        
        Args:
            message: 状态消息
            percent: 进度百分比 (0-100)
        """
        if self.progress_callback:
            try:
                # 如果处理已经开始，添加已用时间
                if self.start_time > 0:
                    elapsed_time = time.time() - self.start_time
                    elapsed_str = self._format_time(elapsed_time)
                    # 如果有设置合成总数，显示已合成数量
                    if self._total_videos > 0:
                        message = f"{message} (已用时: {elapsed_str}, 已合成: {self._completed_videos}/{self._total_videos})"
                    else:
                        message = f"{message} (已用时: {elapsed_str})"
                
                # 保存最后一次进度信息，用于定时器重发
                self._last_progress_message = message
                self._last_progress_percent = percent
                
                # 进度更新应该在主线程中进行
                # 这个回调通常是通过Qt的信号槽机制连接的，
                # 它会自动处理跨线程调用
                self.progress_callback(message, percent)
            except Exception as e:
                logger.error(f"调用进度回调时出错: {str(e)}")
        
        logger.info(f"进度 {percent:.1f}%: {message}")
    
    def get_last_progress(self) -> Optional[Tuple[str, float]]:
        """
        获取最后一次进度更新的消息和百分比
        
        Returns:
            Tuple[str, float] 或 None: 最后进度消息和百分比的元组，如果没有则返回None
        """
        if not self._last_progress_message:
            return None
        
        return (self._last_progress_message, self._last_progress_percent)
    
    def _start_progress_timer(self):
        """启动定期进度更新定时器，防止批处理模式中的超时检测"""
        if self._progress_timer is not None:
            return  # 已有定时器在运行
            
        def _timer_func():
            while not self.stop_requested:
                try:
                    # 每15秒重发一次最后的进度信息
                    if self._last_progress_message and self.progress_callback:
                        # 重新添加时间信息
                        if self.start_time > 0:
                            elapsed_time = time.time() - self.start_time
                            elapsed_str = self._format_time(elapsed_time)
                            base_message = self._last_progress_message.split('(已用时:')[0].strip()
                            # 如果有设置合成总数，显示已合成数量
                            if self._total_videos > 0:
                                message = f"{base_message} (已用时: {elapsed_str}, 已合成: {self._completed_videos}/{self._total_videos})"
                            else:
                                message = f"{base_message} (已用时: {elapsed_str})"
                            self.progress_callback(message, self._last_progress_percent)
                            logger.debug(f"定时重发进度: {self._last_progress_percent:.1f}%: {message}")
                except Exception as e:
                    logger.error(f"进度定时器错误: {str(e)}")
                
                # 睡眠15秒
                time.sleep(15)
        
        # 创建并启动定时器线程
        self._progress_timer = threading.Thread(target=_timer_func, daemon=True)
        self._progress_timer.start()
        logger.info("已启动进度定时更新")
    
    def _stop_progress_timer(self):
        """停止定期进度更新定时器"""
        # 因为是守护线程，不需要显式终止
        self._progress_timer = None
    
    def process_batch(self, 
                      material_folders: List[Dict[str, Any]], 
                      output_dir: str, 
                      count: int = 1, 
                      bgm_path: str = None) -> Tuple[List[str], str]:
        """
        批量处理视频
        
        Args:
            material_folders: 素材文件夹列表
            output_dir: 输出目录
            count: 生成视频数量
            bgm_path: 背景音乐路径
            
        Returns:
            Tuple[List[str], str]: 生成的视频路径列表和总处理时间
        """
        self.start_time = time.time()
        self._total_videos = count
        self._completed_videos = 0
        
        # 记录开始时间
        batch_start_time = time.time()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成的视频路径列表
        output_videos = []
        
        try:
            # 扫描素材文件夹
            self.report_progress("扫描素材文件夹...", 1)
            
            # 优化：使用轻量级扫描，只获取文件路径，不读取元数据
            material_data = self._scan_material_folders(material_folders)
            
            if not material_data:
                error_msg = "没有找到有效的素材"
                logger.error(error_msg)
                self.report_progress(f"错误: {error_msg}", 100)
                return [], "00:00:00"
            
            # 记录扫描完成时间
            scan_end_time = time.time()
            scan_time = scan_end_time - batch_start_time
            logger.info(f"扫描素材完成，用时: {self._format_time(scan_time)}")
            
            # 处理多个视频
            for i in range(count):
                if self.stop_requested:
                    logger.info("收到停止请求，中断批量处理")
                    break
                
                # 计算当前视频的进度范围
                progress_start = 5 + (i / count) * 95
                progress_end = 5 + ((i + 1) / count) * 95
                
                # 生成输出文件名
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                output_filename = f"视频_{timestamp}_{i+1}.mp4"
                output_path = os.path.join(output_dir, output_filename)
                
                self.report_progress(f"处理视频 {i+1}/{count}: {output_filename}", progress_start)
                
                try:
                    # 处理单个视频
                    processed_video = self._process_single_video(
                        material_data=material_data,
                        output_path=output_path,
                        bgm_path=bgm_path,
                        progress_start=progress_start,
                        progress_end=progress_end
                    )
                    
                    if processed_video and os.path.exists(processed_video):
                        output_videos.append(processed_video)
                        self._completed_videos += 1
                        logger.info(f"成功生成视频 {i+1}/{count}: {processed_video}")
                    else:
                        logger.error(f"处理视频 {i+1}/{count} 失败")
                except Exception as e:
                    logger.error(f"处理视频 {i+1}/{count} 时出错: {str(e)}")
                    error_detail = traceback.format_exc()
                    logger.error(f"详细错误信息: {error_detail}")
            
            # 计算总处理时间
            batch_end_time = time.time()
            total_time = batch_end_time - batch_start_time
            formatted_time = self._format_time(total_time)
            
            # 记录成功率
            success_rate = (len(output_videos) / count) * 100 if count > 0 else 0
            logger.info(f"批量处理完成，成功率: {success_rate:.1f}%, 总用时: {formatted_time}")
            
            self.report_progress(f"批量处理完成，成功生成 {len(output_videos)}/{count} 个视频", 100)
            
            return output_videos, formatted_time
            
        except Exception as e:
            logger.error(f"批量处理时出错: {str(e)}")
            error_detail = traceback.format_exc()
            logger.error(f"详细错误信息: {error_detail}")
            
            # 计算已用时间
            current_time = time.time()
            used_time = current_time - batch_start_time
            formatted_time = self._format_time(used_time)
            
            self.report_progress(f"错误: {str(e)}", 100)
            
            return output_videos, formatted_time
    
    def stop_processing(self):
        """停止处理"""
        self.stop_requested = True
        logger.info("已请求停止视频处理")
    
    def _scan_material_folders(self, material_folders: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        扫描素材文件夹，获取所有视频和配音文件
        
        Args:
            material_folders: 素材文件夹信息列表
            
        Returns:
            Dict[str, Dict[str, Any]]: 素材数据字典
        """
        # 导入解析快捷方式的函数
        from src.utils.file_utils import resolve_shortcut
        
        material_data = {}
        
        # 计算每个文件夹的扫描进度
        progress_per_folder = 4.0 / len(material_folders) if material_folders else 0
        
        # 遍历每个素材文件夹
        for idx, folder_info in enumerate(material_folders):
            folder_path = folder_info.get("path", "")
            folder_name = folder_info.get("name", os.path.basename(folder_path) if folder_path else "未命名")
            extract_mode = folder_info.get("extract_mode", "single_video")
            
            if not folder_path or not os.path.exists(folder_path):
                logger.warning(f"素材文件夹不存在: {folder_path}")
                continue
                
            self.report_progress(f"扫描素材文件夹: {folder_name}", 1 + progress_per_folder * idx)
            
            # 检查是否是多视频拼接模式
            if extract_mode == "multi_video":
                # 多视频拼接模式：直接将素材文件夹作为一个场景
                logger.info(f"使用多视频拼接模式处理素材: {folder_path}")
                
                # 初始化场景数据
                segment_key = f"01_{folder_name}"
                material_data[segment_key] = {
                    "videos": [],
                    "audios": [],
                    "path": folder_path,
                    "segment_index": 0,  # 存储段落索引，用于排序
                    "parent_folder": folder_name,  # 记录所属父文件夹
                    "is_shortcut": False,  # 记录是否为快捷方式
                    "original_path": folder_path,  # 记录原始路径
                    "display_name": folder_name,  # 用于显示的名称
                    "extract_mode": "multi_video"  # 标记为多视频拼接模式
                }
                
                # 扫描视频和配音文件夹
                self._scan_media_folder(folder_path, segment_key, material_data)
                
            else:
                # 单视频模式：检查是否有子文件夹
                logger.info(f"使用单视频模式处理素材: {folder_path}")
                
                # 获取所有子文件夹，包括普通文件夹和快捷方式
                sub_folders = []
                
                try:
                    # 遍历文件夹中的所有项目
                    for item in os.listdir(folder_path):
                        # 确保文件名是正确的字符串格式
                        if isinstance(item, bytes):
                            try:
                                item = item.decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    item = item.decode('gbk')
                                except UnicodeDecodeError:
                                    logger.error(f"无法解码文件名: {item}")
                                    continue
                        
                        item_path = os.path.join(folder_path, item)
                        is_shortcut = False
                        actual_path = item_path
                        
                        # 检查是否是快捷方式
                        if item.lower().endswith('.lnk'):
                            logger.debug(f"发现可能的快捷方式: {item_path}")
                            shortcut_target = resolve_shortcut(item_path)
                            if shortcut_target and os.path.isdir(shortcut_target):
                                actual_path = shortcut_target
                                is_shortcut = True
                                logger.info(f"解析快捷方式成功: {item_path} -> {actual_path}")
                            else:
                                logger.warning(f"无法解析快捷方式或目标不是目录: {item_path}")
                                continue
                                
                        # 检查是否是文件夹
                        if os.path.isdir(actual_path):
                            # 检查是否有视频或配音子文件夹
                            has_video = os.path.exists(os.path.join(actual_path, "视频"))
                            has_audio = os.path.exists(os.path.join(actual_path, "配音"))
                            
                            # 检查是否有视频快捷方式
                            if not has_video:
                                video_shortcut_paths = [
                                    os.path.join(actual_path, "视频 - 快捷方式.lnk"),
                                    os.path.join(actual_path, "视频.lnk"),
                                    os.path.join(actual_path, "视频快捷方式.lnk")
                                ]
                                
                                for shortcut_path in video_shortcut_paths:
                                    if os.path.exists(shortcut_path):
                                        has_video = True
                                        break
                                        
                                # 如果仍未找到，尝试搜索包含"视频"的所有.lnk文件
                                if not has_video:
                                    try:
                                        for sub_item in os.listdir(actual_path):
                                            # 确保文件名是正确的字符串格式
                                            if isinstance(sub_item, bytes):
                                                try:
                                                    sub_item = sub_item.decode('utf-8')
                                                except UnicodeDecodeError:
                                                    try:
                                                        sub_item = sub_item.decode('gbk')
                                                    except UnicodeDecodeError:
                                                        logger.error(f"无法解码文件名: {sub_item}")
                                                        continue
                                            
                                            if sub_item.lower().endswith('.lnk') and "视频" in sub_item:
                                                has_video = True
                                                break
                                    except Exception as e:
                                        logger.error(f"搜索视频快捷方式时出错: {str(e)}")
                            
                            # 检查是否有配音快捷方式
                            if not has_audio:
                                audio_shortcut_paths = [
                                    os.path.join(actual_path, "配音 - 快捷方式.lnk"),
                                    os.path.join(actual_path, "配音.lnk"),
                                    os.path.join(actual_path, "配音快捷方式.lnk")
                                ]
                                
                                for shortcut_path in audio_shortcut_paths:
                                    if os.path.exists(shortcut_path):
                                        has_audio = True
                                        break
                                        
                                # 如果仍未找到，尝试搜索包含"配音"的所有.lnk文件
                                if not has_audio:
                                    try:
                                        for sub_item in os.listdir(actual_path):
                                            # 确保文件名是正确的字符串格式
                                            if isinstance(sub_item, bytes):
                                                try:
                                                    sub_item = sub_item.decode('utf-8')
                                                except UnicodeDecodeError:
                                                    try:
                                                        sub_item = sub_item.decode('gbk')
                                                    except UnicodeDecodeError:
                                                        logger.error(f"无法解码文件名: {sub_item}")
                                                        continue
                                            
                                            if sub_item.lower().endswith('.lnk') and "配音" in sub_item:
                                                has_audio = True
                                                break
                                    except Exception as e:
                                        logger.error(f"搜索配音快捷方式时出错: {str(e)}")
                            
                            # 如果有视频或配音子文件夹，则添加到子文件夹列表
                            if has_video or has_audio:
                                sub_folders.append({
                                    "name": item,
                                    "path": actual_path,
                                    "is_shortcut": is_shortcut,
                                    "original_path": item_path
                                })
                except Exception as e:
                    logger.error(f"扫描子文件夹时出错: {str(e)}")
                    continue
                
                # 如果没有找到子文件夹，则直接使用当前文件夹
                if not sub_folders:
                    logger.info(f"未找到有效的子文件夹，直接使用当前文件夹: {folder_path}")
                    
                    # 初始化场景数据
                    segment_key = f"01_{folder_name}"
                    material_data[segment_key] = {
                        "videos": [],
                        "audios": [],
                        "path": folder_path,
                        "segment_index": 0,
                        "parent_folder": folder_name,
                        "is_shortcut": False,
                        "original_path": folder_path,
                        "display_name": folder_name
                    }
                    
                    # 扫描视频和配音文件夹
                    self._scan_media_folder(folder_path, segment_key, material_data)
                else:
                    # 按名称排序子文件夹
                    sub_folders.sort(key=lambda x: x["name"])
                    
                    # 处理每个子文件夹
                    for sub_idx, sub_folder_info in enumerate(sub_folders):
                        sub_path = sub_folder_info["path"]
                        sub_name = sub_folder_info["name"]
                        
                        if sub_folder_info["is_shortcut"]:
                            # 移除.lnk后缀，以便更好的显示
                            if sub_name.lower().endswith('.lnk'):
                                sub_name = sub_name[:-4]
                            sub_display_name = f"{sub_name} (快捷方式)"
                        else:
                            sub_display_name = sub_name
                        
                        self.report_progress(
                            f"扫描段落 {sub_idx+1}/{len(sub_folders)}: {sub_display_name}", 
                            1 + progress_per_folder * idx + (progress_per_folder * sub_idx / len(sub_folders))
                        )
                        
                        # 使用顺序编号作为键，确保段落按顺序排列
                        segment_key = f"{sub_idx+1:02d}_{sub_name}"
                        
                        # 初始化段落数据
                        material_data[segment_key] = {
                            "videos": [],
                            "audios": [],
                            "path": sub_path,
                            "segment_index": sub_idx,  # 存储段落索引，用于排序
                            "parent_folder": folder_name,  # 记录所属父文件夹
                            "is_shortcut": sub_folder_info["is_shortcut"],  # 记录是否为快捷方式
                            "original_path": sub_folder_info["original_path"],  # 记录原始快捷方式路径
                            "display_name": sub_display_name  # 用于显示的名称
                        }
                        
                        try:
                            # 扫描视频文件夹
                            self._scan_media_folder(sub_path, segment_key, material_data)
                        except Exception as e:
                            logger.error(f"扫描段落 {sub_display_name} 时出错: {str(e)}")
        
        return material_data
    
    def _scan_media_folder(self, folder_path: str, folder_key: str, material_data: Dict[str, Dict[str, Any]]):
        """
        扫描指定文件夹的媒体文件
        
        Args:
            folder_path: 文件夹路径
            folder_key: 素材数据字典中的键
            material_data: 素材数据字典
        """
        # 导入解析快捷方式的函数
        from src.utils.file_utils import resolve_shortcut
        
        # 查找视频文件夹，包括处理快捷方式
        video_folder = os.path.join(folder_path, "视频")
        video_folder_paths = [video_folder]
        
        # 检查视频文件夹是否存在，如果不存在则尝试查找快捷方式
        if not os.path.exists(video_folder) or not os.path.isdir(video_folder):
            logger.debug(f"常规视频文件夹不存在，尝试寻找快捷方式: {video_folder}")
            
            # 检查所有可能的命名格式
            video_shortcut_candidates = [
                os.path.join(folder_path, "视频 - 快捷方式.lnk"),
                os.path.join(folder_path, "视频.lnk"),
                os.path.join(folder_path, "视频快捷方式.lnk")
            ]
            
            # 添加更多可能的快捷方式路径
            for item in os.listdir(folder_path) if os.path.exists(folder_path) and os.path.isdir(folder_path) else []:
                if item.lower().endswith('.lnk') and "视频" in item:
                    shortcut_path = os.path.join(folder_path, item)
                    if shortcut_path not in video_shortcut_candidates:
                        video_shortcut_candidates.append(shortcut_path)
            
            # 检查所有候选快捷方式
            for shortcut_path in video_shortcut_candidates:
                if os.path.exists(shortcut_path):
                    logger.info(f"发现视频文件夹快捷方式: {shortcut_path}")
                    target_path = resolve_shortcut(shortcut_path)
                    if target_path and os.path.exists(target_path) and os.path.isdir(target_path):
                        logger.info(f"解析快捷方式成功: {shortcut_path} -> {target_path}")
                        video_folder_paths = [target_path]
                        break
        
        # 处理视频文件夹 - 优化：使用快速方法获取视频时长
        video_info_list = []
        for video_folder in video_folder_paths:
            if os.path.exists(video_folder) and os.path.isdir(video_folder):
                # 获取所有视频文件
                video_files = []
                for root, _, files in os.walk(video_folder):
                    for file in files:
                        if file.lower().endswith((".mp4", ".avi", ".mov", ".mkv", ".wmv")):
                            video_files.append(os.path.join(root, file))
                
                logger.info(f"在文件夹 '{video_folder}' 中找到 {len(video_files)} 个视频文件")
                
                # 优化：尝试使用快速方法获取视频时长
                for video_file in video_files:
                    try:
                        # 尝试快速获取视频时长
                        duration = self._get_video_duration_fast(video_file)
                        
                        # 创建视频信息对象
                        video_info = {
                            "path": video_file,
                            "duration": duration,  # 使用快速方法获取的时长
                            "fps": -1,  # 这些信息暂不获取
                            "width": -1,
                            "height": -1
                        }
                        video_info_list.append(video_info)
                    except Exception as e:
                        logger.warning(f"处理视频路径失败: {video_file}, 错误: {str(e)}")
                        # 创建基本信息对象，不包含时长
                        video_info = {
                            "path": video_file,
                            "duration": -1,  # 使用-1表示未知时长
                            "fps": -1,
                            "width": -1,
                            "height": -1
                        }
                        video_info_list.append(video_info)
        
        # 保存视频列表
        material_data[folder_key]["videos"] = video_info_list
        logger.info(f"文件夹 '{folder_key}' 中找到 {len(video_info_list)} 个视频文件")
        
        # 查找配音文件夹，包括处理快捷方式
        audio_folder = os.path.join(folder_path, "配音")
        audio_folder_paths = [audio_folder]
        
        # 检查配音文件夹是否存在，如果不存在则尝试查找快捷方式
        if not os.path.exists(audio_folder) or not os.path.isdir(audio_folder):
            logger.debug(f"常规配音文件夹不存在，尝试寻找快捷方式: {audio_folder}")
            
            # 检查所有可能的命名格式
            audio_shortcut_candidates = [
                os.path.join(folder_path, "配音 - 快捷方式.lnk"),
                os.path.join(folder_path, "配音.lnk"),
                os.path.join(folder_path, "配音快捷方式.lnk")
            ]
            
            # 添加更多可能的快捷方式路径
            for item in os.listdir(folder_path) if os.path.exists(folder_path) and os.path.isdir(folder_path) else []:
                if item.lower().endswith('.lnk') and "配音" in item:
                    shortcut_path = os.path.join(folder_path, item)
                    if shortcut_path not in audio_shortcut_candidates:
                        audio_shortcut_candidates.append(shortcut_path)
            
            # 检查所有候选快捷方式
            for shortcut_path in audio_shortcut_candidates:
                if os.path.exists(shortcut_path):
                    logger.info(f"发现配音文件夹快捷方式: {shortcut_path}")
                    target_path = resolve_shortcut(shortcut_path)
                    if target_path and os.path.exists(target_path) and os.path.isdir(target_path):
                        logger.info(f"解析快捷方式成功: {shortcut_path} -> {target_path}")
                        audio_folder_paths = [target_path]
                        break
        
        # 处理配音文件夹 - 配音文件需要获取时长，因为它们决定了视频选择
        audio_info_list = []
        for audio_folder in audio_folder_paths:
            if os.path.exists(audio_folder) and os.path.isdir(audio_folder):
                # 获取所有音频文件
                audio_files = []
                for root, _, files in os.walk(audio_folder):
                    for file in files:
                        if file.lower().endswith((".mp3", ".wav", ".aac", ".ogg", ".flac")):
                            audio_files.append(os.path.join(root, file))
                
                logger.info(f"在文件夹 '{audio_folder}' 中找到 {len(audio_files)} 个音频文件")
                
                # 配音文件需要获取时长，因为它们决定了视频选择
                for audio_file in audio_files:
                    try:
                        audio_info = self._get_audio_metadata(audio_file)
                        if audio_info and audio_info.get("duration", 0) > 0:
                            audio_info_list.append(audio_info)
                    except Exception as e:
                        logger.warning(f"分析音频失败: {audio_file}, 错误: {str(e)}")
        
        # 保存音频列表
        material_data[folder_key]["audios"] = audio_info_list
        logger.info(f"文件夹 '{folder_key}' 中找到 {len(audio_info_list)} 个有效配音")
    
    def _get_video_metadata(self, video_path: str, lazy_load: bool = False) -> Dict[str, Any]:
        """
        获取视频文件的元数据信息
        
        Args:
            video_path: 视频文件路径
            lazy_load: 是否延迟加载元数据（只返回路径）
            
        Returns:
            Dict[str, Any]: 包含视频元数据的字典
        """
        # 检查文件是否存在
        if not os.path.exists(video_path):
            logger.warning(f"视频文件不存在: {video_path}")
            return None
        
        # 如果是延迟加载模式，只返回路径信息
        if lazy_load:
            return {
                "path": video_path,
                "duration": -1,  # 使用-1表示未知时长
                "fps": -1,
                "width": -1,
                "height": -1
            }
            
        try:
            # 获取FFmpeg路径
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            # 创建FFprobe命令
            ffprobe_cmd = ffmpeg_cmd.replace("ffmpeg", "ffprobe")
            
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    short_path = win32api.GetShortPathName(video_path)
                    video_path = short_path
                except ImportError:
                    logger.warning("无法导入win32api模块，将使用原始路径")
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}，将使用原始路径")
            
            # 构建命令
            cmd = [
                ffprobe_cmd,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height,avg_frame_rate,duration",
                "-show_entries", "format=duration,bit_rate",
                "-of", "json",
                video_path
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                logger.warning(f"获取视频元数据失败: {result.stderr}")
                
                # 尝试使用OpenCV作为备选方案（保留原始功能作为备选）
                logger.info(f"尝试使用OpenCV获取视频信息: {video_path}")
                try:
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        logger.warning(f"无法打开视频: {video_path}")
                        return None
                    
                    # 获取视频帧率和总帧数
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    
                    # 计算视频时长(秒)
                    duration = frame_count / fps if fps > 0 else 0
                    
                    # 获取分辨率
                    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    cap.release()
                    
                    if duration > 0:
                        return {
                            "path": video_path,
                            "duration": duration,
                            "fps": fps,
                            "width": width,
                            "height": height
                        }
                    return None
                except Exception as cv_error:
                    logger.error(f"OpenCV分析视频也失败: {str(cv_error)}")
                    return None
            
            # 解析JSON结果
            metadata = json.loads(result.stdout)
            
            # 提取视频流信息
            stream_info = metadata.get("streams", [])[0] if metadata.get("streams") else {}
            format_info = metadata.get("format", {})
            
            # 从流或格式中获取时长
            duration = float(stream_info.get("duration", 0))
            if duration == 0:
                duration = float(format_info.get("duration", 0))
            
            # 获取帧率
            fps_str = stream_info.get("avg_frame_rate", "0/1")
            fps_parts = fps_str.split('/')
            fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) > 0 else 0
            
            # 创建结果字典
            video_info = {
                "path": video_path,
                "duration": duration,
                "fps": fps,
                "width": int(stream_info.get("width", 0)),
                "height": int(stream_info.get("height", 0)),
                "bit_rate": int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else 0
            }
            
            return video_info
            
        except Exception as e:
            logger.warning(f"获取视频元数据失败: {str(e)}")
            # 出错后返回None
            return None
    
    def _get_audio_metadata(self, audio_path: str) -> Dict[str, Any]:
        """
        获取音频文件的元数据信息，不解码音频内容
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            Dict[str, Any]: 包含音频元数据的字典
        """
        # 检查文件是否存在
        if not os.path.exists(audio_path):
            logger.warning(f"音频文件不存在: {audio_path}")
            return None
            
        try:
            # 获取FFmpeg路径
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            # 创建FFprobe命令
            ffprobe_cmd = ffmpeg_cmd.replace("ffmpeg", "ffprobe")
            
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    short_path = win32api.GetShortPathName(audio_path)
                    audio_path = short_path
                except ImportError:
                    logger.warning("无法导入win32api模块，将使用原始路径")
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}，将使用原始路径")
            
            # 构建命令
            cmd = [
                ffprobe_cmd,
                "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=duration,sample_rate,channels",
                "-show_entries", "format=duration,bit_rate",
                "-of", "json",
                audio_path
            ]
            
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                logger.warning(f"获取音频元数据失败: {result.stderr}")
                
                # 尝试使用MoviePy作为备选方案（保留原始功能作为备选）
                logger.info(f"尝试使用MoviePy获取音频信息: {audio_path}")
                try:
                    audio_clip = AudioFileClip(audio_path)
                    duration = audio_clip.duration
                    audio_clip.close()
                    
                    if duration > 0:
                        return {
                            "path": audio_path,
                            "duration": duration
                        }
                    return None
                except Exception as mp_error:
                    logger.error(f"MoviePy分析音频也失败: {str(mp_error)}")
                    return None
            
            # 解析JSON结果
            metadata = json.loads(result.stdout)
            
            # 提取音频流信息
            stream_info = metadata.get("streams", [])[0] if metadata.get("streams") else {}
            format_info = metadata.get("format", {})
            
            # 从流或格式中获取时长
            duration = float(stream_info.get("duration", 0))
            if duration == 0:
                duration = float(format_info.get("duration", 0))
            
            # 创建结果字典
            audio_info = {
                "path": audio_path,
                "duration": duration,
                "sample_rate": int(stream_info.get("sample_rate", 0)),
                "channels": int(stream_info.get("channels", 0)),
                "bit_rate": int(format_info.get("bit_rate", 0)) if format_info.get("bit_rate") else 0
            }
            
            return audio_info
            
        except Exception as e:
            logger.warning(f"获取音频元数据失败: {str(e)}")
            # 出错后返回None
            return None
    
    def _process_single_video(self, 
                              material_data: Dict[str, Dict[str, Any]], 
                              output_path: str, 
                              bgm_path: str = None,
                              progress_start: float = 0,
                              progress_end: float = 100) -> str:
        """
        处理单个视频
        
        Args:
            material_data: 素材数据
            output_path: 输出路径
            bgm_path: 背景音乐路径
            progress_start: 进度起始值
            progress_end: 进度结束值
        
        Returns:
            str: 输出视频路径
        """
        # 启动进度定时更新
        self._start_progress_timer()
        
        try:
            # 设置进度范围
            progress_range = progress_end - progress_start
            
            # 处理output_path，确保使用短路径名
            original_output_path = output_path
            if os.name == 'nt':
                try:
                    import win32api
                    # 确保输出目录存在
                    output_dir = os.path.dirname(output_path)
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir, exist_ok=True)
                    # 获取输出目录的短路径名
                    output_dir_short = win32api.GetShortPathName(output_dir)
                    # 合成新的输出路径
                    output_filename = os.path.basename(output_path)
                    output_path = os.path.join(output_dir_short, output_filename)
                    logger.info(f"输出路径已转换为短路径: {original_output_path} -> {output_path}")
                except ImportError:
                    logger.warning("win32api模块未安装，无法转换输出路径为短路径名")
                except Exception as e:
                    logger.warning(f"转换输出路径失败: {str(e)}，将使用原始路径")
                    output_path = original_output_path
            
            # 保持段落顺序
            # 检查是否有段落索引，如果有则按段落索引排序
            folders = []
            has_segment_structure = False
            
            for key, data in material_data.items():
                if "segment_index" in data:
                    has_segment_structure = True
                    break
            
            if has_segment_structure:
                # 按段落索引排序
                folders = sorted(material_data.keys(), 
                                key=lambda k: material_data[k].get("segment_index", 0))
                logger.info("检测到分段结构，将按段落顺序处理视频")
            else:
                # 使用原始顺序
                folders = list(material_data.keys())
            
            # 确保至少有1个场景
            if len(folders) == 0:
                error_msg = "没有可用的场景，无法生成视频"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 使用所有场景，保持原始顺序
            selected_folders = folders
            
            logger.info(f"将按顺序使用 {len(selected_folders)} 个场景: {', '.join(selected_folders)}")
            
            # 收集所选场景的素材
            self.report_progress(f"正在按顺序合成 {len(selected_folders)} 个场景...", 
                               progress_start + progress_range * 0.05)
            
            selected_clips = []
            open_resources = []  # 跟踪需要关闭的资源
            used_videos = set()  # 跟踪已使用的视频，避免重复
            
            # 创建临时文件夹用于分段处理
            temp_dir = os.path.join(os.path.dirname(output_path), "temp_segments")
            os.makedirs(temp_dir, exist_ok=True)
            temp_segment_files = []  # 存储临时片段文件路径
            
            try:
                for i, folder_name in enumerate(selected_folders):
                    if self.stop_requested:
                        logger.info("收到停止请求，中断视频合成")
                        raise InterruptedError("视频处理被用户中断")
                        
                    folder_data = material_data[folder_name]
                    
                    self.report_progress(f"处理场景: {folder_name}", 
                                       progress_start + progress_range * 0.1 + i * (progress_range * 0.4 / len(selected_folders)))
                    
                    logger.info(f"处理场景: {folder_name}")
                    videos = folder_data["videos"]
                    audios = folder_data["audios"]
                    
                    # 获取该文件夹的抽取模式，默认为"single_video"（单视频模式）
                    extract_mode = folder_data.get("extract_mode", "single_video")
                    logger.info(f"场景 '{folder_name}' 使用抽取模式: {extract_mode}")
                    
                    if not videos:
                        logger.warning(f"场景 '{folder_name}' 没有可用视频，跳过")
                        continue
                    
                    if not audios:
                        logger.warning(f"场景 '{folder_name}' 没有可用配音，使用无声视频")
                        audio_file = None
                        audio_duration = 0
                    else:
                        # 随机选择一个配音
                        import random
                        if len(audios) > 1:
                            audio_info = random.choice(audios)
                            logger.info(f"从{len(audios)}个可用配音中随机选择")
                        else:
                            audio_info = audios[0]
                        audio_file = audio_info["path"]
                        audio_duration = audio_info["duration"]
                        logger.info(f"选择配音: {os.path.basename(audio_file)}, 时长: {audio_duration:.2f}秒")
                    
                    # 根据抽取模式选择不同的处理逻辑
                    segment_output_path = None  # 用于存储当前片段的输出路径
                    
                    if extract_mode == "multi_video" and audio_duration > 0:
                        # 多视频拼接模式 - 优化：只选择需要的视频，不加载所有视频
                        logger.info(f"场景 '{folder_name}' 使用多视频拼接模式")
                        
                        # 优化：随机打乱视频顺序，但排除已使用的视频
                        # 将视频复制到一个新列表中，避免修改原始数据
                        available_videos = [v for v in videos if v["path"] not in used_videos]
                        
                        if not available_videos:
                            logger.warning(f"场景 '{folder_name}' 没有未使用的视频，将使用已使用过的视频")
                            available_videos = videos.copy()
                        
                        # 随机打乱视频顺序
                        import random
                        random.shuffle(available_videos)
                        
                        # 创建当前片段的临时文件路径
                        segment_output_path = os.path.join(temp_dir, f"segment_{i}_{uuid.uuid4()}.mp4")
                        
                        # 优化：只选择足够满足配音时长的视频
                        selected_video_paths = []
                        total_duration = 0
                        
                        # 选择视频直到总时长满足配音时长
                        for v in available_videos:
                            # 如果视频元数据未加载，则现在加载
                            video_duration = v.get("duration", -1)
                            if video_duration < 0:
                                # 只有在需要时才获取视频元数据
                                video_info = self._get_video_metadata(v["path"])
                                if video_info:
                                    # 更新元数据
                                    v.update(video_info)
                                    video_duration = video_info.get("duration", 0)
                                else:
                                    # 如果获取元数据失败，跳过此视频
                                    continue
                            
                            # 添加到选中视频列表
                            selected_video_paths.append(v["path"])
                            total_duration += video_duration
                            
                            # 记录已使用的视频
                            used_videos.add(v["path"])
                            
                            # 如果总时长已经满足配音时长，停止选择
                            if total_duration >= audio_duration:
                                break
                        
                        if not selected_video_paths:
                            logger.warning(f"场景 '{folder_name}' 没有找到足够长的视频，跳过")
                            continue
                            
                        logger.info(f"已选择 {len(selected_video_paths)} 个视频，总时长: {total_duration:.2f}秒，配音时长: {audio_duration:.2f}秒")
                        
                        # 优化：使用FFmpeg的concat demuxer直接拼接视频，避免重新编码
                        concat_success = self._concat_videos_with_ffmpeg(
                            video_files=selected_video_paths,
                            audio_file=audio_file,
                            output_path=segment_output_path,
                            target_duration=audio_duration
                        )
                        
                        if not concat_success:
                            logger.error(f"拼接视频失败: {segment_output_path}")
                            continue
                        
                        # 检查生成的片段文件
                        if os.path.exists(segment_output_path) and os.path.getsize(segment_output_path) > 0:
                            temp_segment_files.append(segment_output_path)
                            logger.info(f"成功创建片段: {segment_output_path}")
                        else:
                            logger.warning(f"创建片段文件失败: {segment_output_path}")
                        
                        # 强制内存清理
                        self._force_memory_cleanup()
                        
                    else:
                        # 单视频模式 - 优化：只选择一个合适的视频，不加载所有视频
                        logger.info(f"场景 '{folder_name}' 使用单视频模式")
                        
                        # 优化：先获取未使用的视频
                        unused_videos = [v for v in videos if v["path"] not in used_videos]
                        
                        if not unused_videos:
                            logger.warning(f"场景 '{folder_name}' 的所有视频都已使用，将随机重复使用")
                            unused_videos = videos  # 使用所有视频，后续会随机选择
                        
                        # 优化：如果有配音，先尝试找到时长足够的视频
                        suitable_videos = []
                        
                        if audio_duration > 0:
                            # 先检查已有时长信息的视频
                            for v in unused_videos:
                                if v.get("duration", -1) >= audio_duration:
                                    suitable_videos.append(v)
                            
                            # 如果没有找到足够长的视频，尝试加载更多视频的时长
                            if not suitable_videos:
                                # 随机选择一部分视频进行检查，避免检查所有视频
                                sample_size = min(50, len(unused_videos))
                                sample_videos = random.sample(unused_videos, sample_size)
                                
                                for v in sample_videos:
                                    # 如果视频元数据未加载，则现在加载
                                    if v.get("duration", -1) < 0:
                                        video_info = self._get_video_metadata(v["path"])
                                        if video_info:
                                            # 更新元数据
                                            v.update(video_info)
                                            if video_info.get("duration", 0) >= audio_duration:
                                                suitable_videos.append(v)
                        
                        # 选择视频
                        selected_video = None
                        
                        if suitable_videos:
                            # 从合适的视频中随机选择一个
                            selected_video = random.choice(suitable_videos)
                            logger.info(f"从 {len(suitable_videos)} 个足够长的视频中随机选择")
                        else:
                            # 如果没有找到足够长的视频，随机选择一个视频
                            selected_video = random.choice(unused_videos)
                            logger.info("未找到足够长的视频，随机选择")
                            
                            # 如果视频元数据未加载，则现在加载
                            if selected_video.get("duration", -1) < 0:
                                video_info = self._get_video_metadata(selected_video["path"])
                                if video_info:
                                    selected_video.update(video_info)
                        
                        video_file = selected_video["path"]
                        video_duration = selected_video.get("duration", 0)
                        
                        # 记录已使用的视频
                        used_videos.add(video_file)
                        
                        logger.info(f"选择视频: {os.path.basename(video_file)}, 时长: {video_duration:.2f}秒")
                        
                        # 创建当前片段的临时文件路径
                        segment_output_path = os.path.join(temp_dir, f"segment_{i}_{uuid.uuid4()}.mp4")
                        
                        # 优化：使用FFmpeg直接处理单个视频，避免加载到内存
                        process_success = self._process_single_video_with_ffmpeg(
                            video_file=video_file,
                            audio_file=audio_file,
                            output_path=segment_output_path,
                            target_duration=audio_duration if audio_duration > 0 else None
                        )
                        
                        if not process_success:
                            logger.error(f"处理视频失败: {segment_output_path}")
                            continue
                        
                        # 检查生成的片段文件
                        if os.path.exists(segment_output_path) and os.path.getsize(segment_output_path) > 0:
                            temp_segment_files.append(segment_output_path)
                            logger.info(f"成功创建片段: {segment_output_path}")
                        else:
                            logger.warning(f"创建片段文件失败: {segment_output_path}")
                        
                        # 强制内存清理
                        self._force_memory_cleanup()
                    
                    # 添加更多进度更新点，避免长时间无更新
                    current_progress = (i + 1) / len(folders) * 0.4  # 场景选择占总进度的40%
                    self.report_progress(f"已处理 {i+1}/{len(folders)} 个场景", 
                                      progress_start + progress_range * current_progress)
                
                # 检查是否有生成的片段
                if not temp_segment_files:
                    error_msg = "没有生成任何有效的视频片段"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                
                # 合并所有片段，添加转场效果
                self.report_progress("正在合并片段并添加转场效果...", 
                                   progress_start + progress_range * 0.5)
                
                try:
                    # 使用ffmpeg合并所有片段
                    final_success = self._combine_segments_with_ffmpeg(
                        segment_files=temp_segment_files,
                        output_path=output_path,
                        bgm_path=bgm_path,
                        transition_type=self.settings["transition"],
                        transition_duration=self.settings["transition_duration"]
                    )
                    
                    if not final_success:
                        error_msg = "合并视频片段失败"
                        logger.error(error_msg)
                        raise RuntimeError(error_msg)
                    
                    # 添加水印（如果启用）
                    if self.settings.get("watermark_enabled", False):
                        self.report_progress("正在添加水印...", progress_start + progress_range * 0.9)
                        watermark_success = self._add_watermark_to_video(output_path, output_path)
                        if not watermark_success:
                            logger.warning("添加水印失败，将使用无水印版本")
                    
                    self.report_progress("视频处理完成", progress_start + progress_range)
                    return output_path
                    
                except Exception as e:
                    error_msg = f"合并视频片段时出错: {str(e)}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
            finally:
                # 清理临时片段文件
                for temp_file in temp_segment_files:
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                            logger.debug(f"已删除临时片段文件: {temp_file}")
                    except Exception as e:
                        logger.warning(f"删除临时片段文件失败: {temp_file}, 错误: {str(e)}")
                
                # 尝试删除临时目录
                try:
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                        logger.debug(f"已删除空的临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"删除临时目录失败: {temp_dir}, 错误: {str(e)}")
                
        except Exception as e:
            error_msg = f"处理视频时出错: {str(e)}"
            logger.error(error_msg)
            self.report_progress(f"错误: {error_msg}", progress_start + progress_range)
            raise
        finally:
            # 停止进度定时更新
            self._stop_progress_timer()
    
    def _merge_clips_with_transitions(self, clip_infos: List[Dict[str, Any]]) -> VideoFileClip:
        """
        合并视频片段并添加转场效果
        
        Args:
            clip_infos: 视频片段信息列表
            
        Returns:
            VideoFileClip: 合并后的视频
        """
        if not clip_infos:
            raise ValueError("没有可用的视频片段")
        
        if len(clip_infos) == 1:
            return clip_infos[0]["clip"]
        
        # 检查是否使用转场
        transition_type = self.settings["transition"]
        if transition_type == "不使用转场":
            # 直接拼接所有片段，不应用任何转场效果
            logger.info("使用快速模式：不应用转场效果")
            clips = [info["clip"] for info in clip_infos]
            return concatenate_videoclips(clips)
        
        # 准备要合并的片段
        merged_clips = []
        
        # 添加第一个片段
        merged_clips.append(clip_infos[0]["clip"])
        
        # 为每个后续片段添加转场效果
        for i in range(1, len(clip_infos)):
            prev_clip = clip_infos[i-1]["clip"]
            curr_clip = clip_infos[i]["clip"]
            
            # 获取转场类型
            if transition_type == "随机转场":
                # 随机选择转场效果
                transition_types = ["fade", "mirror_flip", "hue_shift", "zoom", "wipe", "pixelate", "slide", "blur"]
                transition_type = random.choice(transition_types)
            
            # 转场时长
            transition_duration = self.settings["transition_duration"]
            
            # 确保有足够的转场时长
            if prev_clip.duration < transition_duration * 2:
                transition_duration = min(0.5, prev_clip.duration / 2)
            if curr_clip.duration < transition_duration * 2:
                transition_duration = min(transition_duration, curr_clip.duration / 2)
            
            # 为了处理音频转场，我们需要修改音频部分
            # 1. 保存原始音频
            prev_audio = prev_clip.audio
            curr_audio = curr_clip.audio
            
            # 2. 应用视觉转场效果
            if transition_type == "fade":
                # 淡入淡出
                prev_clip = prev_clip.fadeout(transition_duration)
                curr_clip = curr_clip.fadein(transition_duration)
            elif transition_type == "mirror_flip":
                # 镜像翻转效果
                def mirror_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    if progress < 0.5:
                        # 第一个视频逐渐镜像
                        h, w = frame.shape[:2]
                        mid = int(w * (0.5 + progress))
                        mirrored = frame.copy()
                        mirrored[:, mid:] = np.fliplr(frame[:, mid:])
                        return mirrored
                    else:
                        # 第二个视频逐渐恢复正常
                        h, w = frame.shape[:2]
                        mid = int(w * (1.0 - (progress - 0.5) * 2))
                        mirrored = frame.copy()
                        mirrored[:, :mid] = np.fliplr(frame[:, :mid])
                        return mirrored
                
                prev_clip = prev_clip.fx(vfx.custom_fx, mirror_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                # 确保转场后的片段保持合适音量
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "hue_shift":
                # 色相偏移效果
                def hue_shift_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    # 将RGB转换为HSV
                    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
                    # 根据进度调整色相
                    shift = int(180 * progress)
                    hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + shift) % 180
                    # 将HSV转换回RGB
                    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, hue_shift_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "zoom":
                # 缩放效果
                prev_clip = prev_clip.fx(vfx.resize, lambda t: 1 + 0.1 * t / transition_duration)
                prev_clip = prev_clip.fx(vfx.fadeout, transition_duration)
                curr_clip = curr_clip.fx(vfx.resize, lambda t: 1.1 - 0.1 * t / transition_duration)
                curr_clip = curr_clip.fx(vfx.fadein, transition_duration)
            elif transition_type == "wipe":
                # 擦除效果
                def wipe_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    h, w = frame.shape[:2]
                    mask = np.zeros((h, w), dtype=np.uint8)
                    wipe_pos = int(w * progress)
                    mask[:, :wipe_pos] = 255
                    return cv2.bitwise_and(frame, frame, mask=mask)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, wipe_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "pixelate":
                # 像素化效果
                def pixelate_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    h, w = frame.shape[:2]
                    
                    # 根据进度调整像素大小
                    pixel_size = max(1, int(20 * progress))
                    
                    # 缩小并放大回原始尺寸，产生像素化效果
                    small = cv2.resize(frame, (w // pixel_size, h // pixel_size), interpolation=cv2.INTER_LINEAR)
                    return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, pixelate_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            elif transition_type == "slide": 
                # 滑动效果 - 使用自定义效果
                def slide_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    h, w = frame.shape[:2]
                    
                    # 创建一个位移变换矩阵
                    offset_x = int(w * progress)
                    M = np.float32([[1, 0, -offset_x], [0, 1, 0]])
                    
                    # 应用仿射变换实现滑动效果
                    return cv2.warpAffine(frame, M, (w, h))
                
                # 使用我们自定义的slide_effect而不是不存在的slide_out
                prev_clip = prev_clip.fx(vfx.custom_fx, slide_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                # 添加音频淡出效果
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
                
                # 为当前剪辑添加淡入效果
                curr_clip = curr_clip.fadein(transition_duration)
            elif transition_type == "blur":
                # 模糊效果
                def blur_effect(gf, t):
                    """t从0到转场时长"""
                    progress = min(1, t / transition_duration)
                    frame = gf(t)
                    
                    # 计算模糊半径，确保是大于1的奇数
                    blur_size = max(3, int(30 * progress))
                    # 确保内核大小是奇数
                    if blur_size % 2 == 0:
                        blur_size += 1
                    
                    # 应用高斯模糊
                    return cv2.GaussianBlur(frame, (blur_size, blur_size), 0)
                
                prev_clip = prev_clip.fx(vfx.custom_fx, blur_effect)
                prev_clip = prev_clip.set_duration(transition_duration)
                
                if prev_audio:
                    prev_clip = prev_clip.set_audio(prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration))
            else:  # 默认使用淡入淡出
                # 过渡淡出效果
                prev_clip = prev_clip.fadeout(transition_duration)
                curr_clip = curr_clip.fadein(transition_duration)
            
            # 3. 应用音频转场效果
            if curr_audio and prev_audio:
                # 音频交叉淡变
                prev_audio_clip = prev_audio.subclip(0, transition_duration).audio_fadeout(transition_duration)
                curr_audio_clip = curr_audio.subclip(0, transition_duration).audio_fadein(transition_duration)
                
                # 将这些音频应用到转场部分
                if transition_type not in ["fade", "zoom"]:  # 这些转场已经处理了音频
                    # 创建转场时的混合音频
                    mixed_audio = CompositeAudioClip([prev_audio_clip, curr_audio_clip])
                    prev_clip = prev_clip.set_audio(mixed_audio)
            
            # 确保音频转场的平滑衔接
            if i < len(clip_infos) - 1:  # 不是最后一个转场
                # 使用音频淡入淡出确保无缝衔接
                if curr_audio:
                    # 应用音频效果到主体部分
                    main_audio = curr_audio.subclip(transition_duration if curr_audio.duration > transition_duration else 0)
                    if main_audio.duration > transition_duration:
                        main_audio = main_audio.audio_fadeout(transition_duration)
                    curr_clip = curr_clip.set_audio(main_audio)
            
            # 替换之前的片段
            merged_clips[-1] = prev_clip
            
            # 添加当前片段
            merged_clips.append(curr_clip)
        
        # 合并所有片段
        final_clip = concatenate_videoclips(merged_clips)
        
        return final_clip
    
    def _create_temp_file(self, prefix: str, suffix: str) -> str:
        """
        创建临时文件
        
        Args:
            prefix: 文件名前缀
            suffix: 文件扩展名
            
        Returns:
            str: 临时文件路径
        """
        import uuid
        import datetime
        
        # 确保临时目录存在
        temp_dir = self.settings.get("temp_dir", os.path.join(os.path.expanduser("~"), "VideoMixTool", "temp"))
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        
        # 生成唯一文件名：前缀 + 时间戳 + UUID
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        unique_str = str(uuid.uuid4()).replace("-", "")[:8]
        filename = f"{prefix}_{timestamp}_{unique_str}{suffix}"
        
        # 完整路径
        temp_path = os.path.join(temp_dir, filename)
        
        # 在Windows环境下转换为短路径名
        if os.name == 'nt':
            try:
                import win32api
                # 确保目录存在
                if not os.path.exists(os.path.dirname(temp_path)):
                    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
                # 创建一个空文件以获取短路径名
                with open(temp_path, 'w', encoding='utf-8') as f:
                    pass
                # 获取短路径名
                temp_path = win32api.GetShortPathName(temp_path)
                logger.debug(f"临时文件路径已转换为短路径: {temp_path}")
            except ImportError:
                logger.warning("win32api模块未安装，无法转换为短路径名")
            except Exception as e:
                logger.warning(f"转换临时文件路径失败: {str(e)}")
        
        logger.debug(f"创建临时文件: {temp_path}")
        return temp_path
    
    def clean_temp_files(self):
        """清理临时文件"""
        temp_dir = self.settings["temp_dir"]
        
        if os.path.exists(temp_dir):
            try:
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                
                logger.info("临时文件清理完成")
            except Exception as e:
                logger.error(f"清理临时文件失败: {str(e)}") 
    
    def release_resources(self):
        """释放所有资源，包括内存和文件资源"""
        try:
            logger.info("开始释放视频处理器资源...")
            
            # 1. 停止任何进行中的处理
            self.stop_processing()
            
            # 2. 停止进度定时器
            self._stop_progress_timer()
            
            # 3. 清理临时文件
            self.clean_temp_files()
            
            # 4. 释放可能的对象引用
            self._last_progress_message = ""
            self._last_progress_percent = 0
            
            # 5. 尝试手动清理未关闭的其他资源
            # 先触发一次垃圾回收
            gc.collect()
            
            # 安全的资源类型列表 - 这些是确认可以安全关闭的资源类型
            safe_types = [
                "VideoFileClip", "AudioFileClip", "CompositeVideoClip", 
                "CompositeAudioClip", "VideoCapture", "AudioCapture",
                "subprocess.Popen", "Thread", "Pool", "file", "io.TextIOWrapper"
            ]
            
            # 明确需要跳过的类型
            skip_types = [
                "PyQt", "QWidget", "QLayout", "QObject", "QMainWindow", 
                "QDialog", "QTimer", "QEvent", "QAction", "QMenu", "QLabel",
                "QScrollArea", "QTabWidget", "QTableWidget", "QComboBox", "QSpinBox",
                "ui", "window", "dialog", "form", "Button", "Layout", "Widget"
            ]
            
            # 尝试关闭所有挂在该实例上的可关闭对象
            for attr_name in dir(self):
                if attr_name.startswith("__"):
                    continue
                
                try:
                    attr = getattr(self, attr_name)
                    
                    # 跳过None值
                    if attr is None:
                        continue
                    
                    # 跳过基本类型
                    if isinstance(attr, (int, float, str, bool, list, dict, tuple)):
                        continue
                    
                    # 获取类名和类型字符串，用于后续判断
                    class_name = attr.__class__.__name__ if hasattr(attr, "__class__") else ""
                    type_str = str(type(attr)).lower()
                    
                    # 检查是否为需要跳过的类型
                    skip_this = False
                    for skip_type in skip_types:
                        if (skip_type.lower() in type_str.lower() or 
                            (class_name and skip_type.lower() in class_name.lower())):
                            logger.debug(f"跳过UI相关对象: {attr_name}, 类型: {class_name}")
                            skip_this = True
                            break
                    
                    if skip_this:
                        continue
                    
                    # 检查是否为安全类型
                    is_safe_type = False
                    for safe_type in safe_types:
                        if (safe_type.lower() in type_str.lower() or 
                            (class_name and safe_type.lower() in class_name.lower())):
                            is_safe_type = True
                            break
                    
                    # 只处理安全类型的资源
                    if is_safe_type:
                        if hasattr(attr, "close") and callable(attr.close):
                            logger.debug(f"关闭资源: {attr_name}, 类型: {class_name}")
                            attr.close()
                        elif hasattr(attr, "release") and callable(attr.release):
                            logger.debug(f"释放资源: {attr_name}, 类型: {class_name}")
                            attr.release()
                        elif hasattr(attr, "terminate") and callable(attr.terminate):
                            logger.debug(f"终止进程: {attr_name}, 类型: {class_name}")
                            attr.terminate()
                    else:
                        logger.debug(f"跳过非安全类型资源: {attr_name}, 类型: {class_name}")
                except Exception as e:
                    logger.debug(f"关闭资源 {attr_name} 时出错: {str(e)}")
            
            logger.info("视频处理器资源释放完成")
        except Exception as e:
            logger.error(f"释放资源时出错: {str(e)}")
    
    def __del__(self):
        """析构函数，确保资源被释放"""
        try:
            self.release_resources()
        except:
            pass
    
    def _should_use_direct_ffmpeg(self, codec):
        """
        判断是否应该使用直接FFmpeg命令进行编码
        主要用于启用硬件加速时跳过MoviePy的编码流程
        
        关于重编码模式和快速不重编码模式：
        
        1. 重编码模式（返回False）：
           - 使用MoviePy处理视频后再使用FFmpeg编码
           - 优势：
             * 更高的兼容性和稳定性
             * 支持更丰富的视频处理效果
             * 更适合复杂的视频特效和转场
           - 劣势：
             * 处理速度较慢，需要两次编码
             * 可能导致额外的质量损失
             * 内存占用较高
           
        2. 快速不重编码模式（返回True）：
           - 直接使用FFmpeg硬件加速编码，跳过MoviePy的编码流程
           - 优势：
             * 处理速度更快，通常快2-5倍
             * 减少视频质量损失
             * 更高效利用GPU资源
             * 内存占用更低
           - 劣势：
             * 可能与某些特效或转场不兼容
             * 在旧GPU或驱动上可能不稳定
             * 编码选项较为有限
        
        Args:
            codec: 当前使用的编码器
            
        Returns:
            bool: 是否应该使用直接FFmpeg命令
        """
        # 优先检查视频模式设置
        video_mode = self.settings.get("video_mode", "")
        if video_mode == "standard_mode":
            logger.info("使用标准模式(重编码)，不使用直接FFmpeg")
            return False
        elif video_mode == "fast_mode":
            logger.info("使用快速模式(不重编码)，将使用直接FFmpeg")
            return True
        
        # 如果没有指定视频模式或使用旧的设置格式，则使用原有逻辑
        
        # 如果硬件加速没有启用，直接返回False
        hardware_accel = self.settings.get("hardware_accel", "none")
        if hardware_accel == "none":
            logger.info(f"硬件加速未启用，不使用直接FFmpeg")
            return False
        
        # 检查编码器
        # 根据硬件加速设置调整编码器
        encoder_setting = self.settings.get("encoder", "").lower()
        if hardware_accel != "none":
            if "nvidia" in encoder_setting or "nvenc" in encoder_setting:
                codec = "h264_nvenc"
            elif "intel" in encoder_setting or "qsv" in encoder_setting:
                codec = "h264_qsv"
            elif "amd" in encoder_setting or "amf" in encoder_setting:
                codec = "h264_amf"
            elif codec == "libx264":  # 如果是CPU编码器但启用了硬件加速
                # 尝试自动检测硬件类型
                try:
                    from hardware.gpu_config import GPUConfig
                    gpu_config = GPUConfig()
                    if gpu_config.is_hardware_acceleration_enabled():
                        encoder = gpu_config.get_encoder()
                        if encoder and encoder != "libx264":
                            codec = encoder
                            logger.info(f"从GPU配置中获取编码器: {codec}")
                except Exception as e:
                    logger.warning(f"检查GPU配置时出错: {str(e)}")
                    # 默认使用NVENC
                    codec = "h264_nvenc"
                    logger.info(f"无法确定硬件编码器，默认使用: {codec}")
        
        # 只对特定的硬件加速编码器使用直接FFmpeg命令
        hw_encoders = ["h264_nvenc", "h264_qsv", "h264_amf", "hevc_nvenc", "hevc_qsv", "hevc_amf"]
        result = codec in hw_encoders
        logger.info(f"编码器 {codec} {'支持' if result else '不支持'}直接FFmpeg硬件加速")
        return result
    
    def _encode_with_ffmpeg(self, input_path, output_path, hardware_type="auto", codec="libx264"):
        """
        使用FFmpeg进行视频编码
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            hardware_type: 硬件加速类型
            codec: 视频编码器
            
        Returns:
            bool: 编码是否成功
        """
        # 添加进度更新定时器，防止批处理模式中的超时检测
        export_start_time = time.time()
        self._encoding_completed = False
        
        def progress_update_timer():
            """定期发送进度更新的线程函数，防止超时检测"""
            while not self.stop_requested and not hasattr(self, '_encoding_completed'):
                try:
                    # 计算已用时间，估算进度
                    elapsed_time = time.time() - export_start_time
                    self.report_progress(f"视频编码中...", 85)
                except Exception as e:
                    logger.error(f"进度更新定时器错误: {str(e)}")
                # 每15秒更新一次进度
                time.sleep(15)
        
        # 启动进度更新定时器
        progress_thread = threading.Thread(target=progress_update_timer)
        progress_thread.daemon = True
        progress_thread.start()
        
        try:
            # 获取FFmpeg命令路径
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 记录原始编码器
            original_codec = codec
            
            # 检查是否启用了硬件加速
            if hardware_type != "none" and hardware_type != "":
                # 如果指定了硬件加速但编码器为默认编码器，则根据硬件类型选择合适的编码器
                if codec == "libx264":
                    # 尝试从encoder设置中确定正确的硬件编码器
                    encoder_setting = self.settings.get("encoder", "").lower()
                    if "nvenc" in encoder_setting:
                        codec = "h264_nvenc"
                        logger.info(f"根据encoder设置调整为NVIDIA编码器: {codec}")
                    elif "qsv" in encoder_setting:
                        codec = "h264_qsv"
                        logger.info(f"根据encoder设置调整为Intel编码器: {codec}")
                    elif "amf" in encoder_setting:
                        codec = "h264_amf"
                        logger.info(f"根据encoder设置调整为AMD编码器: {codec}")
                    else:
                        # 如果无法从encoder设置确定，根据硬件类型推断
                        if hardware_type == "auto" or "nvidia" in hardware_type:
                            codec = "h264_nvenc"
                            logger.info(f"根据硬件加速类型调整为NVIDIA编码器: {codec}")
                        elif "intel" in hardware_type:
                            codec = "h264_qsv"
                            logger.info(f"根据硬件加速类型调整为Intel编码器: {codec}")
                        elif "amd" in hardware_type:
                            codec = "h264_amf"
                            logger.info(f"根据硬件加速类型调整为AMD编码器: {codec}")
            
            # 记录最终确定的硬件编码器
            logger.info(f"最终确定的编码器: {codec} (原始编码器: {original_codec})")
            
            # 检查是否启用了兼容模式
            compatibility_mode = True  # 默认启用兼容模式
            gpu_config = None
            try:
                # 尝试从配置中读取兼容模式设置
                from hardware.gpu_config import GPUConfig
                gpu_config = GPUConfig()
                compatibility_mode = gpu_config.is_compatibility_mode_enabled()
                logger.info(f"GPU兼容模式设置: {'启用' if compatibility_mode else '禁用'}")
            except Exception as e:
                logger.warning(f"读取GPU兼容模式设置时出错: {str(e)}，将使用默认兼容模式")
            
            # 视频格式标准化参数 - 添加这些参数确保输出视频兼容性
            format_params = [
                "-pix_fmt", "yuv420p",   # 使用标准像素格式
                "-profile:v", "high",    # 使用高质量配置文件
                "-level", "4.1",         # 兼容性级别
                "-movflags", "+faststart", # 优化网络流式传输
                "-g", "30",              # 设定关键帧间隔，提高转场质量
                "-keyint_min", "15",     # 最小关键帧间隔，确保转场区域有足够关键帧
                "-sc_threshold", "40"    # 场景切换阈值，提高转场处理效果
            ]
            
            # GPU加速相关参数
            gpu_params = []
            # NVENC特殊参数
            if "nvenc" in codec:
                # 使用兼容模式参数还是高性能参数
                if compatibility_mode:
                    logger.info("使用NVENC编码 - 兼容模式参数")
                    gpu_params = [
                        "-c:v", codec,
                        "-preset", "p4",  # 兼容性好的预设
                        "-b:v", f"{self.settings['bitrate']}k",
                        "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k", # 增大最大比特率，提高转场质量
                        "-bufsize", f"{self.settings['bitrate'] * 3}k",        # 增大缓冲区大小，优化转场处理
                        "-spatial-aq", "1",  # 保留基础的自适应量化
                        "-temporal-aq", "1", # 保留基础的时间自适应量化
                        "-rc-lookahead", "32", # 增加前瞻帧数，提高转场区域的处理质量
                        "-b_ref_mode", "middle" # 改进B帧参考模式
                    ]
                else:
                    logger.info("使用NVENC编码 - 高性能模式参数")
                    # 新版NVENC参数格式
                    gpu_params = [
                        "-c:v", codec,
                        "-preset", "p2",
                        "-tune", "hq",
                        "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                        "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 增大最大比特率
                        "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k", # 增大缓冲区
                        "-rc", "vbr",  # 使用vbr替代vbr_hq
                        "-multipass", "2",  # 添加多通道编码参数
                        "-spatial-aq", "1",
                        "-temporal-aq", "1",
                        "-cq", "19",
                        "-rc-lookahead", "32", # 增加前瞻帧数
                        "-b_ref_mode", "middle" # 改进B帧参考模式
                    ]
            # QSV特殊参数
            elif codec == "h264_qsv":
                gpu_params = [
                    "-c:v", codec,
                    "-preset", "medium",
                    "-global_quality", "21", # 降低数值，提高质量
                    "-b:v", f"{self.settings['bitrate']}k",
                    "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k", # 提高最大比特率
                    "-look_ahead", "1", # 开启前瞻，提高转场质量
                    "-adaptive_i", "1", # 自适应I帧，有助于场景切换
                    "-adaptive_b", "1"  # 自适应B帧，提高压缩效率
                ]
            # AMF特殊参数
            elif codec == "h264_amf":
                gpu_params = [
                    "-c:v", codec,
                    "-quality", "quality",
                    "-usage", "transcoding",
                    "-b:v", f"{self.settings['bitrate']}k",
                    "-maxrate", f"{int(self.settings['bitrate'] * 2.0)}k", # 提高最大比特率
                    "-header_insertion", "1", # 优化转场处的包头
                    "-bf", "4", # 增加B帧数量，提高压缩率和转场处理
                    "-preanalysis", "1" # 预分析模式，提高转场质量
                ]
            else:
                # 其他编码器使用基本参数 (如libx264)
                gpu_params = [
                    "-c:v", codec,
                    "-preset", "medium",  # libx264的预设
                    "-crf", "22",         # 降低crf值，提高质量以减少转场处的方块
                    "-b:v", f"{self.settings['bitrate']}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k",
                    "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k",
                    "-b_strategy", "1",   # B帧决策策略
                    "-bf", "3",           # 最大B帧数量
                    "-refs", "4"          # 参考帧数，提高质量
                ]
            
            # 通用参数
            common_params = [
                "-i", input_path,
                "-c:a", "aac",  # 音频编码器
                "-b:a", "192k", # 音频比特率
                "-ar", "48000", # 音频采样率
                "-y"            # 覆盖输出文件
            ]
            
            # 如果指定了线程数
            thread_params = []
            if self.settings["threads"] > 0:
                thread_params = ["-threads", str(self.settings["threads"])]
            
            # 组合完整命令
            cmd = [ffmpeg_cmd] + common_params + gpu_params + format_params + thread_params + [output_path]
            
            # 记录实际使用的命令
            cmd_str = " ".join(cmd)
            logger.info(f"执行FFmpeg硬件加速编码: {cmd_str}")
            
            # 执行命令
            try:
                # 创建一个临时文件来捕获输出
                log_file = self._create_temp_file("ffmpeg_log", ".txt")
                
                # 在开始编码前记录GPU状态
                if codec == "h264_nvenc":
                    self._log_gpu_info("编码开始前")
                
                # 确保命令中的路径符合Windows命令行要求（处理中文路径）
                # 将cmd中的所有路径参数进行正确转换
                # 路径可能出现在input_path，output_path参数位置
                if os.name == 'nt':  # 在Windows系统下
                    for i, arg in enumerate(cmd):
                        # 如果参数看起来像文件路径（包含路径分隔符）
                        if isinstance(arg, str) and ('/' in arg or '\\' in arg):
                            # 使用短路径名来避免中文路径问题
                            try:
                                import win32api
                                # 确保路径存在，如果是输出路径可能还不存在
                                if os.path.exists(arg) or i == len(cmd) - 1:  # 最后一个参数是输出路径
                                    # 如果是输出路径但目录不存在，则先创建目录
                                    if i == len(cmd) - 1 and not os.path.exists(os.path.dirname(arg)):
                                        os.makedirs(os.path.dirname(arg), exist_ok=True)
                                    # 获取短路径名
                                    if os.path.exists(arg):
                                        cmd[i] = win32api.GetShortPathName(arg)
                                        logger.debug(f"将路径转换为短路径: {arg} -> {cmd[i]}")
                            except Exception as e:
                                logger.warning(f"转换路径时出错: {str(e)}，将保持原始路径")
                
                with open(log_file, 'w', encoding='utf-8') as log:
                    # 设置编码为UTF-8并启用错误替换
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        universal_newlines=True,
                        bufsize=1,
                        text=True,
                        encoding='utf-8',      # 明确设置编码为UTF-8
                        errors='replace',       # 对于无法解码的字符进行替换
                        shell=False            # 避免shell注入风险
                    )
                    
                    # 记录开始时间
                    start_time = time.time()
                    frames_processed = 0
                    
                    # 实时读取输出并写入日志
                    for line in process.stdout:
                        log.write(line)
                        log.flush()
                        
                        # 解析进度信息并更新UI
                        if "frame=" in line and "fps=" in line:
                            try:
                                frame_match = re.search(r'frame=\s*(\d+)', line)
                                fps_match = re.search(r'fps=\s*(\d+)', line)
                                
                                if frame_match and fps_match:
                                    frames_processed = int(frame_match.group(1))
                                    current_fps = int(fps_match.group(1))
                                    
                                    elapsed = time.time() - start_time
                                    if elapsed > 0 and frames_processed > 0:
                                        self.report_progress(
                                            f"正在使用GPU加速编码... {frames_processed}帧 @ {current_fps} fps", 
                                            90 + min(9, (elapsed / 60) * 9)  # 进度估算，最多到99%
                                        )
                                        
                                        # 每处理500帧记录一次GPU状态
                                        if frames_processed % 500 == 0 and codec == "h264_nvenc":
                                            self._log_gpu_info(f"处理中 ({frames_processed}帧)")
                            except Exception as e:
                                logger.debug(f"解析FFmpeg输出时出错: {str(e)}")
                        
                        # 如果用户请求停止处理，中断进程
                        if self.stop_requested:
                            process.terminate()
                            logger.info("FFmpeg编码过程被用户中断")
                            return False
                    
                    # 等待进程完成
                    process.wait()
                    
                    # 记录编码完成后的GPU状态
                    if codec == "h264_nvenc":
                        self._log_gpu_info("编码完成后")
                    
                    # 计算编码时间和平均帧率
                    encode_time = time.time() - start_time
                    avg_fps = frames_processed / encode_time if encode_time > 0 else 0
                    
                    # 检查返回码
                    if process.returncode == 0:
                        logger.info(f"FFmpeg硬件加速编码成功，用时: {encode_time:.2f}秒，平均帧率: {avg_fps:.2f}fps")
                        logger.info(f"命令行日志保存在: {log_file}")
                        
                        # 显示输出文件信息
                        if os.path.exists(output_path):
                            file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
                            logger.info(f"输出文件大小: {file_size:.2f} MB")
                            
                            # 提取文件时长和比特率
                            try:
                                # 同样处理info_cmd中的路径
                                info_cmd = [ffmpeg_cmd, "-i", output_path]
                                
                                # 在Windows环境下处理可能包含中文的路径
                                if os.name == 'nt':
                                    try:
                                        import win32api
                                        if os.path.exists(output_path):
                                            info_cmd[2] = win32api.GetShortPathName(output_path)
                                    except Exception as e:
                                        logger.warning(f"转换输出路径时出错: {str(e)}，将保持原始路径")
                                
                                info_proc = subprocess.Popen(
                                    info_cmd, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE,
                                    universal_newlines=True,
                                    encoding='utf-8',  # 确保使用UTF-8编码
                                    errors='replace'   # 对于无法解码的字符进行替换
                                )
                                _, stderr = info_proc.communicate()
                                
                                # 提取时长
                                duration_match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', stderr)
                                if duration_match:
                                    hours, minutes, seconds = map(float, duration_match.groups())
                                    total_seconds = hours * 3600 + minutes * 60 + seconds
                                    logger.info(f"输出视频时长: {total_seconds:.2f}秒")
                                
                                # 提取比特率
                                bitrate_match = re.search(r'bitrate: (\d+) kb/s', stderr)
                                if bitrate_match:
                                    bitrate = int(bitrate_match.group(1))
                                    logger.info(f"输出视频比特率: {bitrate} kb/s")
                            except Exception as e:
                                logger.debug(f"提取输出文件信息时出错: {str(e)}")
                        
                        return True
                    else:
                        logger.error(f"FFmpeg进程返回错误码: {process.returncode}")
                        
                        # 尝试从日志中提取错误信息
                        try:
                            with open(log_file, 'r', encoding='utf-8') as f:
                                last_lines = "".join(f.readlines()[-20:])  # 读取最后20行
                                logger.error(f"FFmpeg错误输出: {last_lines}")
                        except Exception:
                            pass
                        
                        return False
            except Exception as e:
                logger.error(f"执行FFmpeg命令时出错: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"执行FFmpeg命令时出错: {str(e)}")
            return False
        finally:
            # 标记编码已完成，停止进度更新
            self._encoding_completed = True
            # 停止进度更新定时器（设置超时，避免阻塞）
            try:
                progress_thread.join(timeout=1.0)
            except Exception as e:
                logger.error(f"停止进度更新线程时出错: {str(e)}")
    
    def _get_ffmpeg_cmd(self):
        """
        获取FFmpeg命令路径
        
        Returns:
            str: FFmpeg可执行文件路径
        """
        ffmpeg_cmd = "ffmpeg"
        
        # 尝试从ffmpeg_path.txt读取自定义路径
        try:
            # 获取项目根目录
            project_root = Path(__file__).resolve().parent.parent.parent
            ffmpeg_path_file = project_root / "ffmpeg_path.txt"
            
            if ffmpeg_path_file.exists():
                with open(ffmpeg_path_file, 'r', encoding="utf-8") as f:
                    custom_path = f.read().strip()
                    if custom_path and os.path.exists(custom_path):
                        logger.info(f"使用自定义FFmpeg路径: {custom_path}")
                        
                        # 在Windows环境下处理中文路径
                        if os.name == 'nt':
                            try:
                                import win32api
                                custom_path = win32api.GetShortPathName(custom_path)
                                logger.info(f"转换为短路径名: {custom_path}")
                            except ImportError:
                                logger.warning("无法导入win32api模块，将使用原始路径")
                            except Exception as e:
                                logger.warning(f"转换FFmpeg路径时出错: {str(e)}，将使用原始路径")
                        
                        ffmpeg_cmd = custom_path
        except Exception as e:
            logger.error(f"读取自定义FFmpeg路径时出错: {str(e)}")
        
        return ffmpeg_cmd

    def _log_gpu_info(self, stage=""):
        """
        记录GPU状态信息
        
        Args:
            stage: 当前阶段描述
        """
        try:
            # 基本GPU利用率
            utilization_cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory",
                               "--format=csv,noheader,nounits"]
            output = subprocess.check_output(utilization_cmd, universal_newlines=True).strip().split(', ')
            
            if len(output) >= 2:
                gpu_util = output[0]
                mem_util = output[1]
                logger.info(f"GPU状态({stage}) - 利用率: {gpu_util}%, 显存利用率: {mem_util}%")
            
            # 编码器使用情况
            encoder_cmd = ["nvidia-smi", "--query-gpu=encoder.stats.sessionCount,encoder.stats.averageFps",
                          "--format=csv,noheader,nounits"]
            encoder_output = subprocess.check_output(encoder_cmd, universal_newlines=True).strip().split(', ')
            
            if len(encoder_output) >= 2:
                session_count = encoder_output[0]
                avg_fps = encoder_output[1]
                logger.info(f"编码器状态({stage}) - 会话数: {session_count}, 平均帧率: {avg_fps} fps")
        except Exception as e:
            logger.debug(f"记录GPU信息时出错: {str(e)}") 
    
    def _check_video_file(self, file_path: str) -> bool:
        """
        检查视频文件是否有效
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            bool: 文件是否有效
        """
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 1000:
            logger.warning(f"视频文件不存在或太小: {file_path}")
            return False
            
        try:
            # 使用ffprobe检查文件有效性
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            ffprobe_cmd = ffmpeg_cmd.replace("ffmpeg", "ffprobe")
            
            # 如果ffprobe不存在，尝试使用ffmpeg
            if not os.path.exists(ffprobe_cmd):
                ffprobe_cmd = ffmpeg_cmd
                
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    if os.path.exists(file_path):
                        file_path_short = win32api.GetShortPathName(file_path)
                    else:
                        return False
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}")
                    file_path_short = file_path
            else:
                file_path_short = file_path
                
            # 构建命令
            cmd = [ffprobe_cmd, "-v", "error", "-select_streams", "v:0", "-show_entries", 
                   "stream=codec_type,width,height,duration", "-of", "json", file_path_short]
                
            # 执行命令
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
            
            if result.returncode != 0:
                logger.warning(f"ffprobe检查视频失败: {result.stderr}")
                return False
                
            # 检查输出是否包含有效的视频流信息
            if "codec_type" in result.stdout and "video" in result.stdout:
                return True
            else:
                logger.warning(f"视频文件不包含有效视频流: {file_path}")
                return False
                
        except Exception as e:
            logger.warning(f"检查视频文件有效性时出错: {str(e)}")
            return False
    
    def _get_watermark_text(self) -> str:
        """
        生成时间戳水印文本
        
        Returns:
            str: 格式化的时间戳水印文本
        """
        # 获取当前时间
        now = datetime.datetime.now()
        # 格式化为 年.月日.时分
        timestamp = now.strftime("%Y.%m%d.%H%M")
        
        # 检查是否有自定义前缀
        prefix = self.settings.get("watermark_prefix", "")
        if prefix:
            return f"{prefix}{timestamp}"
        else:
            return timestamp

    def _add_watermark_to_video(self, input_path: str, output_path: str) -> bool:
        """
        向视频添加时间戳水印
        
        Args:
            input_path: 输入视频路径
            output_path: 输出带水印的视频路径
            
        Returns:
            bool: 是否成功添加水印
        """
        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            if not ffmpeg_cmd:
                logger.error("未找到FFmpeg命令，无法添加水印")
                return False
                
            # 获取水印文本
            watermark_text = self._get_watermark_text()
            
            # 检查同一分钟是否已有视频生成
            # 如果有，则在时间戳后面添加编号，例如 (1), (2) 等
            dir_path = os.path.dirname(output_path)
            base_name = os.path.basename(output_path)
            count = 0
            
            # 查找同一分钟生成的视频数量
            for file in os.listdir(dir_path):
                if file.endswith(".mp4") and watermark_text in file:
                    count += 1
            
            # 如果已经有同一分钟的视频，则添加编号
            if count > 0:
                watermark_text = f"{watermark_text}({count})"
            
            # 获取水印设置
            font_size = self.settings.get("watermark_size", 24)
            font_color = self.settings.get("watermark_color", "#FFFFFF")
            position = self.settings.get("watermark_position", "右上角")
            pos_x_offset = self.settings.get("watermark_pos_x", 0)
            pos_y_offset = self.settings.get("watermark_pos_y", 0)
            
            # 转换RGB颜色为十六进制，并去掉#前缀
            if font_color.startswith("#"):
                font_color = font_color[1:]
            
            # 获取视频分辨率
            probe_cmd = [
                ffmpeg_cmd, 
                "-i", input_path,
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0"
            ]
            
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    if os.path.exists(input_path):
                        probe_cmd[2] = win32api.GetShortPathName(input_path)
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}")
            
            # 获取视频尺寸
            try:
                result = subprocess.check_output(probe_cmd, universal_newlines=True).strip()
                width, height = map(int, result.split('x'))
            except Exception as e:
                logger.error(f"获取视频尺寸失败: {str(e)}")
                # 默认使用1080p尺寸
                if "1080p" in self.settings.get("resolution", ""):
                    if "竖屏" in self.settings.get("resolution", ""):
                        width, height = 1080, 1920
                    else:
                        width, height = 1920, 1080
                else:
                    width, height = 1280, 720
            
            # 确定水印位置
            positions = {
                "右上角": f"x=w-tw-10{pos_x_offset:+}:y=10{pos_y_offset:+}",
                "左上角": f"x=10{pos_x_offset:+}:y=10{pos_y_offset:+}",
                "右下角": f"x=w-tw-10{pos_x_offset:+}:y=h-th-10{pos_y_offset:+}",
                "左下角": f"x=10{pos_x_offset:+}:y=h-th-10{pos_y_offset:+}",
                "中心": f"x=(w-tw)/2{pos_x_offset:+}:y=(h-th)/2{pos_y_offset:+}"
            }
            
            # 获取对应位置的坐标表达式
            position_expr = positions.get(position, positions["右上角"])
            
            # 构建FFmpeg命令
            # 使用drawtext过滤器添加水印
            drawtext_filter = f"drawtext=text='{watermark_text}':fontsize={font_size}:fontcolor=0x{font_color}:box=0:{position_expr}"
            
            # 检查是否使用快速模式和兼容模式
            is_fast_mode = self.settings.get("video_mode", "") in ["fast_mode", "ultra_fast_mode"]
            is_ultra_fast = self.settings.get("video_mode", "") == "ultra_fast_mode"
            compatibility_mode = self.settings.get("compatibility_mode", False)
            
            # 完整的FFmpeg命令
            cmd = [
                ffmpeg_cmd,
                "-i", input_path,
                "-vf", drawtext_filter
            ]
            
            # 添加优化的编码参数，减少转场处的乱码和方块
            cmd.extend([
                "-g", "30",              # 设定关键帧间隔，提高转场质量
                "-keyint_min", "15",     # 最小关键帧间隔，确保转场区域有足够关键帧
                "-sc_threshold", "40"    # 场景切换阈值，提高转场处理效果
            ])
            
            # 根据模式选择不同的编码方式
            encoder = self.settings.get("encoder", "libx264")
            
            # 对于NVENC编码器使用特殊参数
            if "nvenc" in encoder:
                # 使用与FFmpeg编码相同的优化参数
                cmd.extend([
                    "-c:v", encoder,
                    "-preset", "p2",
                    "-tune", "hq",
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 增大最大比特率
                    "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k", # 增大缓冲区
                    "-spatial-aq", "1",
                    "-temporal-aq", "1",
                    "-rc-lookahead", "32" # 增加前瞻帧数
                ])
            elif "qsv" in encoder:
                # 对于Intel QSV编码器
                cmd.extend([
                    "-c:v", encoder,
                    "-preset", "medium",
                    "-global_quality", "21", # 降低数值，提高质量
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 提高最大比特率
                    "-look_ahead", "1", # 开启前瞻，提高转场质量
                    "-adaptive_i", "1", # 自适应I帧，有助于场景切换
                    "-adaptive_b", "1"  # 自适应B帧，提高压缩效率
                ])
            elif "amf" in encoder:
                # 对于AMD AMF编码器
                cmd.extend([
                    "-c:v", encoder,
                    "-quality", "quality",
                    "-usage", "transcoding",
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k", # 提高最大比特率
                    "-header_insertion", "1", # 优化转场处的包头
                    "-bf", "4" # 增加B帧数量，提高压缩率和转场处理
                ])
            else:
                # 对于CPU编码器
                cmd.extend([
                    "-c:v", encoder,
                    "-preset", "medium",
                    "-crf", "22",         # 降低crf值，提高质量以减少转场处的方块
                    "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                    "-maxrate", f"{int(self.settings.get('bitrate', 5000) * 2.0)}k",
                    "-bufsize", f"{self.settings.get('bitrate', 5000) * 3}k",
                    "-b_strategy", "1",   # B帧决策策略
                    "-bf", "3",           # 最大B帧数量
                    "-refs", "4"          # 参考帧数，提高质量
                ])
            
            # 设置通用格式参数
            cmd.extend([
                "-pix_fmt", "yuv420p",          # 标准像素格式
                "-profile:v", "high",           # 高质量配置文件
                "-level", "4.1",                # 兼容性级别
                "-movflags", "+faststart",      # 优化网络流式传输
                "-c:a", "copy"                  # 复制音频，不重新编码
            ])
            
            # 添加输出路径和覆盖参数
            cmd.extend([
                "-y",  # 覆盖已存在的文件
                output_path
            ])
            
            # 处理Windows中文路径
            if os.name == 'nt':
                try:
                    import win32api
                    if os.path.exists(input_path):
                        cmd[2] = win32api.GetShortPathName(input_path)
                except Exception as e:
                    logger.warning(f"转换路径时出错: {str(e)}")
            
            # 记录命令并执行
            cmd_str = " ".join(cmd)
            logger.info(f"添加水印命令: {cmd_str}")
            
            result = subprocess.run(cmd, check=True)
            
            # 检查是否成功
            if result.returncode == 0 and os.path.exists(output_path):
                logger.info(f"成功添加水印: {watermark_text}")
                return True
            else:
                logger.error("添加水印过程返回非零状态")
                return False
                
        except subprocess.CalledProcessError as e:
            logger.error(f"添加水印时FFmpeg命令执行失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"添加水印时发生错误: {str(e)}")
            return False

    def _get_video_dimensions(self, video_path):
        """获取视频的宽度和高度"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_streams',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return stream.get('width', 0), stream.get('height', 0)
            
            return 0, 0
        except Exception as e:
            logger.error(f"获取视频尺寸失败: {e}")
            return 0, 0

    def _check_video_file(self, video_path):
        """检查视频文件是否有效"""
        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_streams',
                '-of', 'json',
                video_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)
            
            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video':
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"ffprobe检查视频失败: {e}")
            return False

    def _process_folder_shortcuts(self, folder_path):
        """
        处理文件夹中的快捷方式
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            Dict: 包含处理后的文件夹路径信息
        """
        # 导入解析快捷方式的函数
        from src.utils.file_utils import resolve_shortcut
        
        result = {
            "video_folder": os.path.join(folder_path, "视频"),
            "audio_folder": os.path.join(folder_path, "配音"),
            "video_folder_paths": [],
            "audio_folder_paths": []
        }
        
        # 检查视频文件夹是否存在，如果不存在则尝试查找快捷方式
        if not os.path.exists(result["video_folder"]) or not os.path.isdir(result["video_folder"]):
            logger.debug(f"常规视频文件夹不存在，尝试寻找快捷方式: {result['video_folder']}")
            
            # 检查所有可能的命名格式
            video_shortcut_candidates = [
                os.path.join(folder_path, "视频 - 快捷方式.lnk"),
                os.path.join(folder_path, "视频.lnk"),
                os.path.join(folder_path, "视频快捷方式.lnk")
            ]
            
            # 添加更多可能的快捷方式路径
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                try:
                    for item in os.listdir(folder_path):
                        # 确保文件名是正确的字符串格式
                        if isinstance(item, bytes):
                            try:
                                item = item.decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    item = item.decode('gbk')
                                except UnicodeDecodeError:
                                    logger.error(f"无法解码文件名: {item}")
                                    continue
                        
                        if item.lower().endswith('.lnk') and "视频" in item:
                            shortcut_path = os.path.join(folder_path, item)
                            if shortcut_path not in video_shortcut_candidates:
                                video_shortcut_candidates.append(shortcut_path)
                except Exception as e:
                    logger.error(f"搜索视频快捷方式时出错: {str(e)}")
            
            # 检查所有候选快捷方式
            for shortcut_path in video_shortcut_candidates:
                if os.path.exists(shortcut_path):
                    logger.info(f"发现视频文件夹快捷方式: {shortcut_path}")
                    target_path = resolve_shortcut(shortcut_path)
                    if target_path and os.path.exists(target_path) and os.path.isdir(target_path):
                        logger.info(f"解析快捷方式成功: {shortcut_path} -> {target_path}")
                        result["video_folder_paths"] = [target_path]
                        break
        else:
            result["video_folder_paths"] = [result["video_folder"]]
        
        # 检查配音文件夹是否存在，如果不存在则尝试查找快捷方式
        if not os.path.exists(result["audio_folder"]) or not os.path.isdir(result["audio_folder"]):
            logger.debug(f"常规配音文件夹不存在，尝试寻找快捷方式: {result['audio_folder']}")
            
            # 检查所有可能的命名格式
            audio_shortcut_candidates = [
                os.path.join(folder_path, "配音 - 快捷方式.lnk"),
                os.path.join(folder_path, "配音.lnk"),
                os.path.join(folder_path, "配音快捷方式.lnk")
            ]
            
            # 添加更多可能的快捷方式路径
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                try:
                    for item in os.listdir(folder_path):
                        # 确保文件名是正确的字符串格式
                        if isinstance(item, bytes):
                            try:
                                item = item.decode('utf-8')
                            except UnicodeDecodeError:
                                try:
                                    item = item.decode('gbk')
                                except UnicodeDecodeError:
                                    logger.error(f"无法解码文件名: {item}")
                                    continue
                        
                        if item.lower().endswith('.lnk') and "配音" in item:
                            shortcut_path = os.path.join(folder_path, item)
                            if shortcut_path not in audio_shortcut_candidates:
                                audio_shortcut_candidates.append(shortcut_path)
                except Exception as e:
                    logger.error(f"搜索配音快捷方式时出错: {str(e)}")
            
            # 检查所有候选快捷方式
            for shortcut_path in audio_shortcut_candidates:
                if os.path.exists(shortcut_path):
                    logger.info(f"发现配音文件夹快捷方式: {shortcut_path}")
                    target_path = resolve_shortcut(shortcut_path)
                    if target_path and os.path.exists(target_path) and os.path.isdir(target_path):
                        logger.info(f"解析快捷方式成功: {shortcut_path} -> {target_path}")
                        result["audio_folder_paths"] = [target_path]
                        break
        else:
            result["audio_folder_paths"] = [result["audio_folder"]]
        
        return result

    def compose_video(self, 
                    video_files: List[str], 
                    audio_file: str, 
                    output_path: str, 
                    bgm_path: str = None) -> bool:
        """
        合成单个视频
        
        Args:
            video_files: 视频文件列表
            audio_file: 配音文件路径
            output_path: 输出文件路径
            bgm_path: 背景音乐路径
            
        Returns:
            bool: 是否成功
        """
        if not video_files:
            logger.error("没有提供视频文件")
            return False
            
        if not audio_file or not os.path.exists(audio_file):
            logger.warning(f"配音文件不存在: {audio_file}")
            # 继续处理，但不添加配音
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取硬件加速类型和编码器
        hardware_accel = self.settings.get("hardware_accel", "none")
        encoder = self.settings.get("encoder", "libx264")
        
        # 记录开始时间
        start_time = time.time()
        
        # 初始化打开的资源列表，用于最后清理
        open_resources = []
        
        try:
            # 随机打乱视频顺序
            import random
            random.shuffle(video_files)
            
            # 加载配音文件
            audio_duration = 0
            if audio_file and os.path.exists(audio_file):
                try:
                    audio_clip = AudioFileClip(audio_file)
                    open_resources.append(audio_clip)
                    audio_duration = audio_clip.duration
                    logger.info(f"配音文件时长: {audio_duration:.2f}秒")
                except Exception as e:
                    logger.error(f"加载配音文件失败: {str(e)}")
                    audio_file = None
            
            # 准备拼接的片段
            concat_clips = []
            total_duration = 0
            
            # 拼接视频片段直到达到配音时长
            for video_file in video_files:
                if total_duration >= audio_duration and audio_duration > 0:
                    break
                    
                try:
                    # 加载视频剪辑
                    video_clip = VideoFileClip(video_file)
                    open_resources.append(video_clip)
                    
                    # 计算需要的时长
                    if audio_duration > 0:
                        remaining_duration = audio_duration - total_duration
                        clip_duration = min(remaining_duration, video_clip.duration)
                    else:
                        # 如果没有配音，使用整个视频
                        clip_duration = video_clip.duration
                    
                    # 裁剪视频
                    if clip_duration < video_clip.duration:
                        video_clip = video_clip.subclip(0, clip_duration)
                    
                    # 添加到拼接列表
                    concat_clips.append(video_clip)
                    total_duration += clip_duration
                    
                    logger.info(f"添加视频片段: {os.path.basename(video_file)}, 时长: {clip_duration:.2f}秒")
                except Exception as e:
                    logger.error(f"处理视频文件失败: {str(e)}")
                    continue
            
            # 检查是否有视频片段
            if not concat_clips:
                logger.error("没有可用的视频片段")
                return False
            
            # 合并视频片段
            if len(concat_clips) > 1:
                logger.info(f"合并 {len(concat_clips)} 个视频片段")
                final_clip = concatenate_videoclips(concat_clips)
                open_resources.append(final_clip)
            else:
                final_clip = concat_clips[0]
            
            # 添加配音
            if audio_file and os.path.exists(audio_file) and 'audio_clip' in locals():
                # 如果配音时长小于视频时长，则裁剪视频
                if audio_duration < final_clip.duration:
                    final_clip = final_clip.subclip(0, audio_duration)
                
                # 替换原始音频
                final_clip = final_clip.set_audio(audio_clip)
                logger.info("已添加配音")
            
            # 添加背景音乐
            if bgm_path and os.path.exists(bgm_path):
                try:
                    # 加载背景音乐
                    bgm_clip = AudioFileClip(bgm_path)
                    open_resources.append(bgm_clip)
                    
                    # 调整背景音乐音量
                    bgm_volume = self.settings.get("bgm_volume", 0.3)
                    bgm_clip = bgm_clip.volumex(bgm_volume)
                    
                    # 如果背景音乐时长小于视频时长，则循环播放
                    if bgm_clip.duration < final_clip.duration:
                        repeats = int(final_clip.duration / bgm_clip.duration) + 1
                        bgm_clips = [bgm_clip] * repeats
                        bgm_clip = concatenate_videoclips(bgm_clips)
                        open_resources.append(bgm_clip)
                    
                    # 裁剪背景音乐
                    bgm_clip = bgm_clip.subclip(0, final_clip.duration)
                    
                    # 合并配音和背景音乐
                    if final_clip.audio:
                        final_audio = CompositeAudioClip([final_clip.audio, bgm_clip])
                        final_clip = final_clip.set_audio(final_audio)
                    else:
                        final_clip = final_clip.set_audio(bgm_clip)
                    
                    logger.info("已添加背景音乐")
                except Exception as e:
                    logger.error(f"添加背景音乐失败: {str(e)}")
            
            # 创建临时文件
            temp_dir = os.path.join(os.path.dirname(output_path), "temp")
            os.makedirs(temp_dir, exist_ok=True)
            
            temp_raw_video = os.path.join(temp_dir, f"temp_raw_{uuid.uuid4()}.mp4")
            
            # 使用moviepy导出初始视频
            logger.info("开始导出视频...")
            
            # 获取编码器设置
            codec = encoder
            hardware_type = hardware_accel
            
            # 导出视频
            try:
                # 确保使用硬件加速编码器，如果兼容模式开启则使用GPU编码器，否则回退到libx264
                temp_codec = codec if self.settings.get("compatibility_mode", True) else "libx264"
                logger.info(f"临时文件将使用编码器: {temp_codec}")
                
                # 记录最终确定的硬件编码器
                final_encoder = temp_codec
                logger.info(f"最终确定的硬件编码器: {final_encoder}")
                
                # 导出视频使用GPU编码
                final_clip.write_videofile(
                    temp_raw_video, 
                    fps=30, 
                    codec=temp_codec,  # 对临时文件也尝试使用GPU编码
                    audio_codec="aac",
                    remove_temp=True,
                    write_logfile=False,
                    preset="fast", 
                    verbose=False,
                    threads=self.settings.get("threads", 4),
                    ffmpeg_params=[
                        "-hide_banner", "-y",
                        "-pix_fmt", "yuv420p",  # 确保使用标准像素格式
                        "-profile:v", "high",   # 使用高质量配置文件
                        "-level", "4.1",        # 兼容性级别
                        "-movflags", "+faststart" # 优化网络流式传输
                    ]
                )
            except Exception as e:
                logger.error(f"导出视频失败: {str(e)}")
                return False
            
            # 使用FFmpeg添加水印和进行最终编码
            if os.path.exists(temp_raw_video):
                # 获取水印设置
                watermark_enabled = self.settings.get("watermark_enabled", False)
                
                # 获取FFmpeg命令路径
                ffmpeg_cmd = self._get_ffmpeg_cmd()
                
                # 构建基本的FFmpeg命令
                cmd = [ffmpeg_cmd, "-y", "-i", temp_raw_video]
                
                # 根据是否启用水印分别处理
                if watermark_enabled:
                    # 创建带水印的临时文件路径
                    watermarked_output = self._create_temp_file("watermarked", ".mp4")
                    # 先生成不带水印的视频
                    cmd.extend([
                        "-c:v", codec,
                        "-preset", "medium",
                        "-profile:v", "high",
                        "-level", "4.1",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        watermarked_output
                    ])
                    
                    # 执行FFmpeg命令生成中间文件
                    logger.info(f"执行FFmpeg命令生成中间文件: {' '.join(cmd)}")
                    try:
                        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                        
                        # 如果中间文件生成成功，添加水印
                        if os.path.exists(watermarked_output):
                            # 添加水印到中间文件，并输出到最终文件
                            watermark_success = self._add_watermark_to_video(watermarked_output, output_path)
                            
                            # 清理中间文件
                            try:
                                os.remove(watermarked_output)
                            except Exception as e:
                                logger.warning(f"删除中间文件失败: {str(e)}")
                                
                            if not watermark_success:
                                logger.warning("水印添加失败，将使用无水印版本")
                                # 直接复制中间文件到输出路径
                                shutil.copy2(watermarked_output, output_path)
                        else:
                            logger.error("中间文件生成失败")
                            return False
                    except subprocess.CalledProcessError as e:
                        logger.error(f"FFmpeg命令执行失败: {e.stderr}")
                        return False
                    except Exception as e:
                        logger.error(f"执行FFmpeg命令时出错: {str(e)}")
                        return False
                else:
                    # 不添加水印，直接导出
                    cmd.extend([
                        "-c:v", codec,
                        "-preset", "medium",
                        "-profile:v", "high",
                        "-level", "4.1",
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart",
                        "-c:a", "aac",
                        "-b:a", "192k",
                        output_path
                    ])
                    
                    # 执行FFmpeg命令
                    logger.info(f"执行FFmpeg命令: {' '.join(cmd)}")
                    try:
                        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                        logger.info(f"FFmpeg命令执行成功: {result.stdout}")
                    except subprocess.CalledProcessError as e:
                        logger.error(f"FFmpeg命令执行失败: {e.stderr}")
                        return False
                    except Exception as e:
                        logger.error(f"执行FFmpeg命令时出错: {str(e)}")
                        return False
            
            # 计算处理时间
            end_time = time.time()
            process_time = end_time - start_time
            logger.info(f"视频处理完成，耗时: {process_time:.2f}秒")
            
            return True
        except Exception as e:
            logger.error(f"视频合成过程中出错: {str(e)}")
            return False
        finally:
            # 清理资源
            for resource in open_resources:
                try:
                    resource.close()
                except Exception as e:
                    logger.warning(f"关闭资源失败: {str(e)}")
            
            # 清理临时文件
            if 'temp_raw_video' in locals() and os.path.exists(temp_raw_video):
                try:
                    os.remove(temp_raw_video)
                    logger.debug(f"已删除临时文件: {temp_raw_video}")
                except Exception as e:
                    logger.warning(f"删除临时文件失败: {str(e)}")
            
            # 清理临时目录
            if 'temp_dir' in locals() and os.path.exists(temp_dir):
                try:
                    if os.path.exists(temp_dir) and not os.listdir(temp_dir):
                        os.rmdir(temp_dir)
                        logger.debug(f"已删除空临时目录: {temp_dir}")
                except Exception as e:
                    logger.warning(f"删除临时目录失败: {str(e)}")
    
    def _get_video_files(self, folder_path: str) -> List[str]:
        """
        获取文件夹中的视频文件
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            List[str]: 视频文件路径列表
        """
        video_files = []
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._is_video_file(file_path):
                        video_files.append(file_path)
        return video_files
    
    def _get_audio_files(self, folder_path: str) -> List[str]:
        """
        获取文件夹中的音频文件
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            List[str]: 音频文件路径列表
        """
        audio_files = []
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for root, _, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._is_audio_file(file_path):
                        audio_files.append(file_path)
        return audio_files
    
    def _is_video_file(self, file_path: str) -> bool:
        """
        判断文件是否为视频文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否为视频文件
        """
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
        _, ext = os.path.splitext(file_path.lower())
        return ext in video_extensions
    
    def _is_audio_file(self, file_path: str) -> bool:
        """
        判断文件是否为音频文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否为音频文件
        """
        audio_extensions = ['.mp3', '.wav', '.aac', '.ogg', '.flac', '.m4a']
        _, ext = os.path.splitext(file_path.lower())
        return ext in audio_extensions

    def _force_memory_cleanup(self):
        """
        强制清理内存、执行垃圾回收
        用于高内存占用操作后释放资源
        """
        # 记录清理前内存
        try:
            import psutil
            process = psutil.Process()
            before_mem = process.memory_info().rss / (1024 * 1024)  # MB
            logger.debug(f"清理前内存占用: {before_mem:.2f} MB")
        except ImportError:
            logger.debug("未安装psutil，无法监控内存使用")
            before_mem = 0
        
        # 执行多次垃圾回收
        collected = 0
        for i in range(3):
            collected += gc.collect(i)
        
        # 记录清理后内存
        try:
            if before_mem > 0:
                after_mem = process.memory_info().rss / (1024 * 1024)  # MB
                logger.info(f"内存清理完成: 回收{collected}个对象, 内存从 {before_mem:.2f} MB 降至 {after_mem:.2f} MB")
        except:
            logger.debug(f"内存清理完成: 回收{collected}个对象")

    def _concat_videos_with_ffmpeg(self, video_files, audio_file, output_path, target_duration=None):
        """
        使用FFmpeg直接拼接视频并添加音频，避免内存占用
        
        Args:
            video_files: 视频文件路径列表
            audio_file: 音频文件路径
            output_path: 输出文件路径
            target_duration: 目标时长，如果提供则裁剪到指定时长
            
        Returns:
            bool: 是否成功
        """
        if not video_files:
            logger.error("没有提供视频文件")
            return False
        
        # 获取FFmpeg命令
        ffmpeg_cmd = self._get_ffmpeg_cmd()
        
        # 创建临时文件列表
        list_file = self._create_temp_file("concat_list", ".txt")
        
        try:
            # 如果只有一个视频文件，直接处理单个视频
            if len(video_files) == 1:
                return self._process_single_video_with_ffmpeg(
                    video_files[0], 
                    audio_file, 
                    output_path, 
                    target_duration
                )
            
            # 计算已有总时长和选择最终要使用的视频
            total_duration = 0
            final_video_files = []
            
            # 选择视频直到达到目标时长
            for video_file in video_files:
                # 获取视频信息 - 优先使用已有的时长信息
                video_duration = -1
                
                # 尝试从文件名获取视频对象
                for v in self._get_video_by_path(video_files, video_file):
                    if v and v.get("duration", -1) > 0:
                        video_duration = v.get("duration")
                        break
                
                # 如果没有找到时长信息，获取视频信息
                if video_duration <= 0:
                    video_info = self._get_video_metadata(video_file)
                    if not video_info:
                        logger.warning(f"无法获取视频元数据: {video_file}")
                        continue
                    video_duration = video_info.get("duration", 0)
                
                if video_duration <= 0:
                    logger.warning(f"视频时长无效: {video_file}")
                    continue
                
                # 如果已达到目标时长，跳出循环
                if target_duration and total_duration >= target_duration:
                    break
                
                # 添加到最终列表
                final_video_files.append(video_file)
                total_duration += video_duration
                
                logger.info(f"添加视频: {os.path.basename(video_file)}, 时长: {video_duration:.2f}秒, 累计: {total_duration:.2f}秒")
            
            if not final_video_files:
                logger.error("没有有效的视频文件可拼接")
                return False
                
            # 创建文件列表
            with open(list_file, 'w', encoding='utf-8') as f:
                for video in final_video_files:
                    # 处理Windows路径
                    if os.name == 'nt':
                        video = video.replace('\\', '/')
                    f.write(f"file '{video}'\n")
            
            # 构建基本拼接命令 - 使用concat demuxer
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file
            ]
            
            # 如果有音频文件
            if audio_file and os.path.exists(audio_file):
                cmd.extend(["-i", audio_file])
                
                # 配置音频选项
                cmd.extend([
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-map", "0:v:0",
                    "-map", "1:a:0"
                ])
                
                # 调整音频音量
                voice_volume = self.settings.get("voice_volume", 1.0)
                if voice_volume != 1.0:
                    cmd.extend(["-af", f"volume={voice_volume}"])
            else:
                # 如果没有音频，保留原视频音轨
                cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            
            # 如果目标时长存在且比总时长短，则裁剪
            if target_duration and target_duration < total_duration:
                cmd.extend(["-t", str(target_duration)])
            
            # 添加视频编码选项 - 使用copy模式避免重新编码
            cmd.extend([
                "-c:v", "copy",  # 直接复制视频流，不重新编码
                "-movflags", "+faststart",
                output_path
            ])
            
            # 执行命令
            logger.info(f"执行FFmpeg拼接命令: {' '.join(cmd)}")
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info("视频拼接成功")
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"视频拼接失败: {e.stderr}")
                return False
            
        except Exception as e:
            logger.error(f"拼接视频时出错: {str(e)}")
            return False
        finally:
            # 清理临时文件
            try:
                if os.path.exists(list_file):
                    os.remove(list_file)
            except Exception:
                pass
    
    def _get_video_by_path(self, video_list, path):
        """
        通过路径在视频列表中查找视频对象
        
        Args:
            video_list: 视频对象列表
            path: 视频路径
            
        Returns:
            list: 匹配的视频对象列表
        """
        # 标准化路径
        norm_path = os.path.normpath(path).lower()
        
        # 查找匹配的视频
        return [v for v in video_list if os.path.normpath(v.get("path", "")).lower() == norm_path]

    def _process_single_video_with_ffmpeg(self, video_file, audio_file, output_path, target_duration=None):
        """
        使用FFmpeg直接处理单个视频和音频
        
        Args:
            video_file: 视频文件路径
            audio_file: 音频文件路径
            output_path: 输出文件路径
            target_duration: 目标时长，如果提供则裁剪到指定时长
            
        Returns:
            bool: 是否成功
        """
        if not video_file or not os.path.exists(video_file):
            logger.error(f"视频文件不存在: {video_file}")
            return False
        
        # 获取FFmpeg命令
        ffmpeg_cmd = self._get_ffmpeg_cmd()
        
        # 构建基本命令
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-i", video_file
        ]
        
        # 如果有音频文件
        if audio_file and os.path.exists(audio_file):
            cmd.extend(["-i", audio_file])
            
            # 配置音频选项
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "192k",
                "-map", "0:v:0",
                "-map", "1:a:0"
            ])
            
            # 调整音频音量
            voice_volume = self.settings.get("voice_volume", 1.0)
            if voice_volume != 1.0:
                cmd.extend(["-af", f"volume={voice_volume}"])
        else:
            # 如果没有音频，保留原视频音轨
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])
        
        # 如果目标时长存在，则裁剪
        if target_duration:
            cmd.extend(["-t", str(target_duration)])
        
        # 优化：直接复制视频流，避免重新编码
        cmd.extend([
            "-c:v", "copy",
            "-movflags", "+faststart",
            output_path
        ])
        
        # 执行命令
        logger.info(f"执行FFmpeg处理命令: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info("视频处理成功")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"视频处理失败: {e.stderr}")
            
            # 如果直接复制失败（可能是格式不兼容），尝试使用转码模式
            logger.info("直接复制视频流失败，尝试使用转码模式")
            
            # 重新构建命令，这次使用编码器
            transcode_cmd = [
                ffmpeg_cmd,
                "-y",
                "-i", video_file
            ]
            
            # 如果有音频文件
            if audio_file and os.path.exists(audio_file):
                transcode_cmd.extend(["-i", audio_file])
                
                # 配置音频选项
                transcode_cmd.extend([
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-map", "0:v:0",
                    "-map", "1:a:0"
                ])
                
                # 调整音频音量
                if voice_volume != 1.0:
                    transcode_cmd.extend(["-af", f"volume={voice_volume}"])
            else:
                # 如果没有音频，保留原视频音轨
                transcode_cmd.extend(["-c:a", "aac", "-b:a", "192k"])
            
            # 如果目标时长存在，则裁剪
            if target_duration:
                transcode_cmd.extend(["-t", str(target_duration)])
            
            # 选择合适的编码器
            hardware_accel = self.settings.get("hardware_accel", "none")
            encoder = self.settings.get("encoder", "libx264")
            
            if hardware_accel != "none":
                if "nvenc" in encoder or "nvidia" in hardware_accel.lower():
                    encoder = "h264_nvenc"
                elif "qsv" in encoder or "intel" in hardware_accel.lower():
                    encoder = "h264_qsv"
                elif "amf" in encoder or "amd" in hardware_accel.lower():
                    encoder = "h264_amf"
            
            # 添加编码器和质量选项
            transcode_cmd.extend([
                "-c:v", encoder,
                "-pix_fmt", "yuv420p",
                "-profile:v", "high",
                "-level", "4.1",
                "-b:v", f"{self.settings.get('bitrate', 5000)}k",
                "-preset", "fast",  # 使用快速预设，提高处理速度
                "-movflags", "+faststart",
                output_path
            ])
            
            # 执行转码命令
            logger.info(f"执行FFmpeg转码命令: {' '.join(transcode_cmd)}")
            try:
                result = subprocess.run(transcode_cmd, check=True, capture_output=True, text=True)
                logger.info("视频转码成功")
                return True
            except subprocess.CalledProcessError as e2:
                logger.error(f"视频转码也失败: {e2.stderr}")
                return False
        except Exception as e:
            logger.error(f"处理视频时出错: {str(e)}")
            return False

    def _combine_segments_with_ffmpeg(self, segment_files, output_path, bgm_path=None, transition_type="随机转场", transition_duration=0.5):
        """
        使用FFmpeg合并视频片段，添加转场效果和背景音乐
        
        Args:
            segment_files: 片段文件路径列表
            output_path: 输出文件路径
            bgm_path: 背景音乐路径
            transition_type: 转场类型
            transition_duration: 转场时长
            
        Returns:
            bool: 是否成功
        """
        if not segment_files:
            logger.error("没有提供片段文件")
            return False
        
        # 如果只有一个片段，直接复制
        if len(segment_files) == 1:
            try:
                shutil.copy2(segment_files[0], output_path)
                logger.info(f"只有一个片段，直接复制到输出路径: {output_path}")
                
                # 如果有背景音乐，添加背景音乐
                if bgm_path and os.path.exists(bgm_path):
                    return self._add_bgm_to_video(output_path, bgm_path)
                return True
            except Exception as e:
                logger.error(f"复制单个片段失败: {str(e)}")
                return False
        
        # 获取FFmpeg命令
        ffmpeg_cmd = self._get_ffmpeg_cmd()
        
        # 创建临时文件列表
        list_file = self._create_temp_file("concat_list", ".txt")
        
        try:
            # 创建文件列表
            with open(list_file, 'w', encoding='utf-8') as f:
                for segment in segment_files:
                    # 处理Windows路径
                    segment_path = segment.replace('\\', '/') if os.name == 'nt' else segment
                    f.write(f"file '{segment_path}'\n")
            
            logger.info(f"创建了合并列表文件: {list_file}")
            
            # 构建基本合并命令 - 使用concat demuxer
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file
            ]
            
            # 判断是否需要添加背景音乐
            if bgm_path and os.path.exists(bgm_path):
                # 如果需要添加背景音乐，则需要两步处理
                # 1. 先使用concat demuxer合并视频
                temp_merged_video = self._create_temp_file("merged_video", ".mp4")
                
                # 使用copy编解码器直接拼接，避免重新编码
                concat_cmd = cmd + [
                    "-c", "copy",
                    "-movflags", "+faststart",
                    temp_merged_video
                ]
                
                logger.info(f"执行视频拼接命令: {' '.join(concat_cmd)}")
                try:
                    result = subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
                    logger.info("视频片段拼接成功")
                except subprocess.CalledProcessError as e:
                    logger.error(f"视频片段拼接失败: {e.stderr}")
                    return False
                
                # 2. 然后添加背景音乐
                return self._add_bgm_to_video(temp_merged_video, bgm_path, output_path)
            else:
                # 如果不需要添加背景音乐，直接使用copy编解码器拼接
                cmd.extend([
                    "-c", "copy",
                    "-movflags", "+faststart",
                    output_path
                ])
                
                logger.info(f"执行视频拼接命令: {' '.join(cmd)}")
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    logger.info("视频片段拼接成功")
                    return True
                except subprocess.CalledProcessError as e:
                    logger.error(f"视频片段拼接失败: {e.stderr}")
                    return False
                
        except Exception as e:
            logger.error(f"合并视频片段时出错: {str(e)}")
            return False
        finally:
            # 清理临时文件
            try:
                if os.path.exists(list_file):
                    os.remove(list_file)
            except Exception:
                pass
                
    def _add_bgm_to_video(self, video_path, bgm_path, output_path=None):
        """
        为视频添加背景音乐
        
        Args:
            video_path: 视频文件路径
            bgm_path: 背景音乐路径
            output_path: 输出文件路径，如果为None则覆盖原视频
            
        Returns:
            bool: 是否成功
        """
        if not video_path or not os.path.exists(video_path):
            logger.error(f"视频文件不存在: {video_path}")
            return False
            
        if not bgm_path or not os.path.exists(bgm_path):
            logger.error(f"背景音乐文件不存在: {bgm_path}")
            return False
            
        # 如果未指定输出路径，则覆盖原视频
        if not output_path:
            # 创建临时文件作为输出
            temp_output = self._create_temp_file("bgm_video", ".mp4")
            final_output = video_path
        else:
            temp_output = output_path
            final_output = output_path
        
        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 获取背景音乐音量
            bgm_volume = self.settings.get("bgm_volume", 0.5)
            
            # 构建命令
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-i", video_path,
                "-i", bgm_path,
                "-filter_complex", 
                f"[1:a]volume={bgm_volume}[bgm];[0:a][bgm]amix=inputs=2:duration=longest",
                "-c:v", "copy",  # 视频流直接复制，不重新编码
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                temp_output
            ]
            
            # 执行命令
            logger.info(f"执行添加背景音乐命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            
            # 如果是覆盖原视频，需要将临时文件移动到原位置
            if temp_output != final_output:
                # 先删除原文件
                os.remove(video_path)
                # 然后移动临时文件
                shutil.move(temp_output, final_output)
                
            logger.info(f"成功添加背景音乐到视频: {final_output}")
            return True
            
        except Exception as e:
            logger.error(f"添加背景音乐时出错: {str(e)}")
            # 如果失败且是覆盖模式，确保不删除原视频
            if temp_output != final_output and os.path.exists(temp_output):
                try:
                    os.remove(temp_output)
                except:
                    pass
            return False

    def _get_video_duration_fast(self, file_path):
        """
        快速获取视频时长，不解析完整媒体内容
        
        Args:
            file_path: 视频文件路径
            
        Returns:
            float: 视频时长(秒)，失败返回-1
        """
        try:
            # Windows系统使用wmic命令
            if os.name == 'nt':
                try:
                    # 使用绝对路径，避免路径问题
                    abs_path = os.path.abspath(file_path)
                    # 替换路径中的反斜杠，wmic需要双反斜杠
                    formatted_path = abs_path.replace('\\', '\\\\')
                    
                    # 使用wmic命令获取视频文件属性
                    cmd = f'wmic datafile where name="{formatted_path}" get Duration /value'
                    result = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
                    
                    # 解析输出结果
                    duration_match = re.search(r'Duration=(\d+)', result)
                    if duration_match:
                        # wmic返回的时长单位是100纳秒，需要转换为秒
                        duration_100ns = int(duration_match.group(1))
                        duration_seconds = duration_100ns / 10000000  # 转换为秒
                        return duration_seconds
                except Exception as e:
                    # 如果wmic命令失败，记录日志但继续尝试其他方法
                    logger.debug(f"使用wmic获取视频时长失败: {str(e)}")
            
            # 尝试使用简单的文件头解析（适用于MP4文件）
            try:
                with open(file_path, 'rb') as f:
                    # 读取前16KB数据
                    data = f.read(16384)
                    
                    # 对于MP4文件，查找mvhd box
                    mvhd_pos = data.find(b'mvhd')
                    if mvhd_pos > 0:
                        # 定位到mvhd box后的时间刻度和时长字段
                        version_pos = mvhd_pos + 4
                        version = data[version_pos]
                        
                        if version == 0:  # 32位时间字段
                            time_scale_pos = mvhd_pos + 12
                            time_scale = int.from_bytes(data[time_scale_pos:time_scale_pos+4], byteorder='big')
                            duration_pos = time_scale_pos + 4
                            duration = int.from_bytes(data[duration_pos:duration_pos+4], byteorder='big')
                        else:  # 64位时间字段
                            time_scale_pos = mvhd_pos + 20
                            time_scale = int.from_bytes(data[time_scale_pos:time_scale_pos+4], byteorder='big')
                            duration_pos = time_scale_pos + 4
                            duration = int.from_bytes(data[duration_pos:duration_pos+8], byteorder='big')
                        
                        if time_scale > 0:
                            return duration / time_scale
            except Exception as e:
                logger.debug(f"通过文件头获取视频时长失败: {str(e)}")
            
            # 所有方法都失败，返回-1表示未知时长
            return -1
        except Exception as e:
            logger.warning(f"快速获取视频时长失败: {str(e)}")
            return -1

    def concat_subfolder_videos(self, parent_folder_path: str, output_path: str, bgm_path: str = None) -> bool:
        """
        合成阶段：将所有子文件夹输出的视频按顺序拼接成父文件夹视频
        
        使用FFmpeg的concat demuxer方法，直接拼接视频而不重新编码，实现快速合成
        最终视频时长约等于所有子文件夹中被抽选上的配音的总时长
        
        Args:
            parent_folder_path: 父文件夹路径
            output_path: 输出视频文件路径
            bgm_path: 背景音乐路径(可选)
            
        Returns:
            bool: 是否成功
        """
        if not os.path.exists(parent_folder_path) or not os.path.isdir(parent_folder_path):
            logger.error(f"父文件夹不存在或不是目录: {parent_folder_path}")
            return False
        
        # 获取所有子文件夹
        subfolders = []
        try:
            for item in os.listdir(parent_folder_path):
                item_path = os.path.join(parent_folder_path, item)
                if os.path.isdir(item_path):
                    subfolders.append(item_path)
            
            if not subfolders:
                logger.error(f"父文件夹中没有子文件夹: {parent_folder_path}")
                return False
                
            logger.info(f"找到 {len(subfolders)} 个子文件夹")
        except Exception as e:
            logger.error(f"获取子文件夹列表失败: {str(e)}")
            return False
        
        # 查找每个子文件夹中的输出视频文件
        subfolder_videos = []
        
        for subfolder in subfolders:
            folder_name = os.path.basename(subfolder)
            
            # 检查子文件夹中是否有输出视频文件
            output_dir = os.path.join(subfolder, "output")
            if os.path.exists(output_dir) and os.path.isdir(output_dir):
                # 获取所有视频文件
                video_files = []
                for root, _, files in os.walk(output_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        if self._is_video_file(file_path):
                            video_files.append(file_path)
                
                if video_files:
                    # 如果有多个视频文件，取最新的一个
                    if len(video_files) > 1:
                        video_files.sort(key=os.path.getmtime, reverse=True)
                        logger.info(f"子文件夹 '{folder_name}' 有多个视频，选择最新的一个: {os.path.basename(video_files[0])}")
                    
                    subfolder_videos.append({
                        "folder": folder_name,
                        "path": video_files[0],
                        "mtime": os.path.getmtime(video_files[0])
                    })
                    logger.info(f"子文件夹 '{folder_name}' 找到视频: {os.path.basename(video_files[0])}")
                else:
                    logger.warning(f"子文件夹 '{folder_name}' 的output目录中没有视频文件")
            else:
                logger.warning(f"子文件夹 '{folder_name}' 中没有output目录")
        
        if not subfolder_videos:
            logger.error("没有找到任何子文件夹视频，无法合成")
            return False
        
        # 按照文件修改时间排序，确保按正确顺序组合视频
        subfolder_videos.sort(key=lambda x: x["mtime"])
        logger.info(f"将按时间顺序合成 {len(subfolder_videos)} 个子文件夹视频")
        
        # 创建临时文件列表
        list_file = self._create_temp_file("concat_list", ".txt")
        
        try:
            # 创建文件列表
            with open(list_file, 'w', encoding='utf-8') as f:
                for video_info in subfolder_videos:
                    video_path = video_info["path"]
                    # 处理Windows路径
                    if os.name == 'nt':
                        video_path = video_path.replace('\\', '/')
                    f.write(f"file '{video_path}'\n")
            
            logger.info(f"创建了合并列表文件: {list_file}")
            
            # 获取FFmpeg命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 构建基本合并命令 - 使用concat demuxer
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file
            ]
            
            # 判断是否需要添加背景音乐
            if bgm_path and os.path.exists(bgm_path):
                # 如果需要添加背景音乐，则需要两步处理
                # 1. 先使用concat demuxer合并视频
                temp_merged_video = self._create_temp_file("merged_video", ".mp4")
                
                # 使用copy编解码器直接拼接，避免重新编码
                concat_cmd = cmd + [
                    "-c", "copy",
                    "-movflags", "+faststart",
                    temp_merged_video
                ]
                
                logger.info(f"执行视频拼接命令: {' '.join(concat_cmd)}")
                try:
                    result = subprocess.run(concat_cmd, check=True, capture_output=True, text=True)
                    logger.info("视频拼接成功")
                except subprocess.CalledProcessError as e:
                    logger.error(f"视频拼接失败: {e.stderr}")
                    return False
                
                # 2. 然后添加背景音乐
                return self._add_bgm_to_video(temp_merged_video, bgm_path, output_path)
            else:
                # 如果不需要添加背景音乐，直接使用copy编解码器拼接
                cmd.extend([
                    "-c", "copy",
                    "-movflags", "+faststart",
                    output_path
                ])
                
                logger.info(f"执行视频拼接命令: {' '.join(cmd)}")
                try:
                    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                    logger.info(f"子文件夹视频拼接成功，输出到: {output_path}")
                    return True
                except subprocess.CalledProcessError as e:
                    logger.error(f"视频拼接失败: {e.stderr}")
                    return False
        except Exception as e:
            logger.error(f"合并子文件夹视频时出错: {str(e)}")
            return False
        finally:
            # 清理临时文件
            try:
                if os.path.exists(list_file):
                    os.remove(list_file)
            except Exception:
                pass
