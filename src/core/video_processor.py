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
import glob

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
            "hardware_accel": "auto",  # 硬件加速: auto, cuda, qsv, amf, none
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
            percent: 进度百分比(0-100)
        """
        if self.progress_callback:
            try:
                # 确保start_time已经设置，如果尚未设置，则设置为当前时间
                if self.start_time == 0:
                    self.start_time = time.time()
                    # 启动进度定时器
                    self._start_progress_timer()
                
                # 如果处理已经开始，添加已用时间
                elapsed_time = time.time() - self.start_time
                elapsed_str = self._format_time(elapsed_time)
                # 如果有设置合成总数，显示已合成数量
                if self._total_videos > 0:
                    message = f"{message} (已用时间: {elapsed_str}, 已合并 {self._completed_videos}/{self._total_videos})"
                else:
                    message = f"{message} (已用时间: {elapsed_str})"
                
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
        """启动定期进度更新定时器，防止批处理模式中的超时检查"""
        if self._progress_timer is not None:
            return  # 已有定时器在运行
            
        def _timer_func():
            while not self.stop_requested:
                try:
                    # 确保start_time已设置
                    if self.start_time == 0:
                        self.start_time = time.time()
                    
                    elapsed_time = time.time() - self.start_time
                    elapsed_str = self._format_time(elapsed_time)
                    
                    # 即使没有上次进度信息，也尝试更新时间信息
                    if self.progress_callback:
                        if self._last_progress_message:
                            # 如果有最后的进度消息，提取基础消息部分
                            base_message = self._last_progress_message.split('(已用时间')[0].strip()
                            if not base_message:
                                base_message = "处理中..."
                        else:
                            # 如果没有最后进度消息，使用默认消息
                            base_message = "处理中..."
                        
                        # 构建包含时间信息的消息
                        if self._total_videos > 0:
                            message = f"{base_message} (已用时间: {elapsed_str}, 已合并 {self._completed_videos}/{self._total_videos})"
                        else:
                            message = f"{base_message} (已用时间: {elapsed_str})"
                        
                        # 进度百分比，如果没有最后的进度，使用默认值50
                        percent = self._last_progress_percent if self._last_progress_percent > 0 else 50
                        
                        # 发送更新
                        self.progress_callback(message, percent)
                        logger.debug(f"定时更新进度: {percent:.1f}%: {message}")
                except Exception as e:
                    logger.error(f"进度定时器出错: {str(e)}")
                    error_detail = traceback.format_exc()
                    logger.error(f"详细错误信息: {error_detail}")
                
                # 睡眠5秒，减少刷新频率以使界面更稳定
                time.sleep(5)
        
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
        # 确保设置开始时间
        self.start_time = time.time()
        self._total_videos = count
        self._completed_videos = 0
        
        # 启动进度定时器
        self._start_progress_timer()
        
        # 记录开始时间
        batch_start_time = time.time()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成的视频路径列表
        output_videos = []
        
        try:
            # 扫描素材文件...
            self.report_progress("扫描素材文件...", 1)
            
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
            
            # 记录成功情况
            success_rate = (len(output_videos) / count) * 100 if count > 0 else 0
            logger.info(f"批量处理完成，成功率: {success_rate:.1f}%, 总用时: {formatted_time}")
            
            self.report_progress(f"批量处理完成，成功生成{len(output_videos)}/{count} 个视频", 100)
            
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
    
    def _scan_material_folders(self, material_folders, extract_mode="multi_video"):
        """
        扫描素材文件夹，收集视频和音频信息
        
        Args:
            material_folders: 素材文件夹列表
            extract_mode: 提取模式'single_video'或'multi_video'
            
        Returns:
            Dict: 包含每个文件夹的视频和音频信息的字典
        """
        logger.info(f"开始扫描素材文件夹，共 {len(material_folders)} 个文件夹")
        
        # 创建缓存目录
        cache_dir = os.path.join(self.settings["temp_dir"], "media_cache")
        os.makedirs(cache_dir, exist_ok=True)
        
        result = {}
        video_cache = {}  # 缓存已经处理过的视频文件
        audio_cache = {}  # 缓存已经处理过的音频文件
        
        for i, folder_item in enumerate(material_folders):
            # 确定文件夹路径和名称
            if isinstance(folder_item, dict):
                # 如果是字典，从字典中获取路径
                folder_path = folder_item.get("folder_path") or folder_item.get("path")
                folder_name = folder_item.get("name") or (os.path.basename(folder_path) if folder_path else f"文件夹{i+1}")
            else:
                # 如果是字符串，直接使用
                folder_path = folder_item
                folder_name = os.path.basename(folder_path)
            
            # 确保folder_path是字符串
            if folder_path and not isinstance(folder_path, str):
                folder_path = str(folder_path)
                
            if not folder_path or not os.path.exists(folder_path):
                logger.warning(f"跳过不存在的文件夹: {folder_path}")
                continue
                
            # 更新进度
            progress_message = f"正在扫描素材文件夹{i+1}/{len(material_folders)}: {folder_name}"
            if extract_mode == "multi_video":
                progress_message += " [多视频拼接]"
            self.report_progress(progress_message, (i / len(material_folders)) * 100)
            
            logger.info(f"多视频模式 直接处理文件夹: {folder_path}")
            
            # 检查是否有缓存
            folder_cache_key = folder_path.replace("\\", "_").replace("/", "_").replace(":", "_")
            videos_cache_path = os.path.join(cache_dir, f"videos_{folder_cache_key}.json")
            audios_cache_path = os.path.join(cache_dir, f"audios_{folder_cache_key}.json")
            
            videos = []
            audios = []
            
            # 尝试从缓存加载视频信息
            if folder_path in video_cache:
                videos = video_cache[folder_path]
            elif os.path.exists(videos_cache_path):
                try:
                    with open(videos_cache_path, 'r', encoding='utf-8') as f:
                        videos = json.load(f)
                    video_cache[folder_path] = videos
                    logger.info(f"已从缓存加载 {folder_path} 的视频信息 {len(videos)} 个视频")
                except Exception as e:
                    logger.warning(f"加载视频缓存失败: {str(e)}")
            
            # 如果没有有效的缓存，扫描视频文件
            if not videos:
                video_folder = os.path.join(folder_path, "视频")
                videos = self._scan_media_folder(folder_path, "视频")
                
                # 保存视频信息缓存
                try:
                    # 确保所有路径都是字符串
                    videos_json = []
                    for video in videos:
                        video_copy = video.copy()
                        if not isinstance(video_copy["path"], str):
                            video_copy["path"] = str(video_copy["path"])
                        videos_json.append(video_copy)
                        
                    with open(videos_cache_path, 'w', encoding='utf-8') as f:
                        json.dump(videos_json, f, ensure_ascii=False, indent=2)
                    video_cache[folder_path] = videos
                    logger.info(f"已保存{folder_path} 的视频信息缓存 {len(videos)} 个视频")
                except Exception as e:
                    logger.error(f"保存视频信息缓存失败: {str(e)}")
            
            # 尝试从缓存加载音频信息
            if folder_path in audio_cache:
                audios = audio_cache[folder_path]
            elif os.path.exists(audios_cache_path):
                try:
                    with open(audios_cache_path, 'r', encoding='utf-8') as f:
                        audios = json.load(f)
                    audio_cache[folder_path] = audios
                    logger.info(f"已从缓存加载 {folder_path} 的音频信息 {len(audios)} 个音频")
                except Exception as e:
                    logger.warning(f"加载音频缓存失败: {str(e)}")
            
            # 如果没有有效的缓存，扫描音频文件夹并获取轻量级元数据
            if not audios:
                audio_folder = os.path.join(folder_path, "配音")
                audio_files = self._scan_media_folder(folder_path, "配音")
                
                # 只获取基本信息，而不是完整的元数据
                audios = []
                for audio_file in audio_files:
                    audio_info = self._get_audio_metadata_lite(audio_file["path"])
                    if audio_info:
                        audios.append(audio_info)
                
                # 保存音频信息缓存
                try:
                    # 确保所有路径都是字符串
                    audios_json = []
                    for audio in audios:
                        audio_copy = audio.copy()
                        if not isinstance(audio_copy["path"], str):
                            audio_copy["path"] = str(audio_copy["path"])
                        audios_json.append(audio_copy)
                        
                    with open(audios_cache_path, 'w', encoding='utf-8') as f:
                        json.dump(audios_json, f, ensure_ascii=False, indent=2)
                    audio_cache[folder_path] = audios
                    logger.info(f"已保存{folder_path} 的音频信息缓存 {len(audios)} 个音频")
                except Exception as e:
                    logger.error(f"保存音频信息缓存失败: {str(e)}")
            
            # 存储文件夹信息
            if videos or audios:
                result[folder_name] = {
                    "folder_path": folder_path,
                    "videos": videos,
                    "audios": audios,
                    "segment_index": i,
                }
            
            # 更新进度
            self.report_progress(
                f"已扫描{i+1}/{len(material_folders)} 个文件夹",
                ((i + 1) / len(material_folders)) * 100
            )
        
        # 汇总进度
        self.report_progress(
            f"素材扫描完成，共处理 {len(material_folders)} 个文件夹",
            100
        )
        
        # 检查是否有有效的素材
        valid_scenes = sum(1 for folder_data in result.values() if folder_data.get("videos"))
        logger.info(f"素材扫描完成，找到{valid_scenes} 个有效场景（含视频文件）")
        
        if not result:
            logger.warning("没有找到有效的素材文件夹")
        
        return result
    
    def _get_audio_metadata_lite(self, audio_path):
        """
        获取音频基本元数据（轻量版）, 仅获取必要的信息如路径和时长
        
        Args:
            audio_path (str): 音频文件路径
            
        Returns:
            dict: 包含音频基本信息的字典，如果获取失败则返回None
        """
        try:
            # 确保路径是字符串
            if not isinstance(audio_path, str):
                audio_path = str(audio_path)
            
            # 处理文件扩展名大小写问题
            if not os.path.exists(audio_path):
                self.logger.warning(f"原始音频文件不存在: {audio_path}，尝试解决大小写问题")
                
                # 尝试不同的扩展名组合
                basename, ext = os.path.splitext(audio_path)
                possible_exts = [ext.lower(), ext.upper(), '.mp3', '.MP3', '.wav', '.WAV']
                
                for possible_ext in possible_exts:
                    possible_path = basename + possible_ext
                    if os.path.exists(possible_path):
                        self.logger.info(f"找到替代音频文件: {possible_path}")
                        audio_path = possible_path
                        break
            
            # 再次检查文件是否存在
            if not os.path.exists(audio_path):
                self.logger.warning(f"无法找到音频文件，尝试的所有扩展名均失效: {audio_path}")
                return None
            
            # 使用FFprobe获取音频时长
            duration = None
            try:
                # FFprobe命令
                ffprobe_cmd = [
                    self._get_ffmpeg_cmd().replace("ffmpeg", "ffprobe"),
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    audio_path
                ]
                
                result = subprocess.run(
                    ffprobe_cmd, 
                    capture_output=True, 
                    text=True, 
                    check=True
                )
                
                # 解析时长
                if result.stdout.strip():
                    duration = float(result.stdout.strip())
                    self.logger.debug(f"使用FFprobe获取音频时长成功: {audio_path}, 时长: {duration}秒")
            except Exception as e:
                self.logger.warning(f"使用FFprobe获取音频时长失败: {audio_path}, 错误: {str(e)}")
                # 继续尝试其他方法
            
            # 如果FFprobe失败，尝试使用mutagen
            if duration is None:
                try:
                    from mutagen import File
                    audio = File(audio_path)
                    if audio and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
                        duration = audio.info.length
                        self.logger.debug(f"使用mutagen获取音频时长成功: {audio_path}, 时长: {duration}秒")
                except Exception as e:
                    self.logger.warning(f"使用mutagen获取音频时长失败: {audio_path}, 错误: {str(e)}")
            
            # 如果以上方法都失败，设置默认时长
            if duration is None:
                default_duration = self.settings.get('default_audio_duration', 5.0)
                duration = default_duration
                self.logger.warning(f"无法获取音频时长，使用默认时长{duration} 秒 {audio_path}")
            
            # 返回基本音频信息
            audio_info = {
                "path": audio_path,
                "duration": duration,
                "filename": os.path.basename(audio_path)
            }
            
            return audio_info
            
        except Exception as e:
            self.logger.warning(f"获取音频元数据失败: {audio_path}, 错误: {str(e)}")
            return None
    
    def _save_audio_info_cache(self, folder_path, audio_info_list):
        """
        保存音频信息到缓存文件
        
        Args:
            folder_path: 文件夹路径
            audio_info_list: 音频信息列表
        """
        try:
            # 创建缓存目录
            cache_dir = os.path.join(self.settings["temp_dir"], "audio_cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # 生成缓存文件名（基于文件夹路径的哈希值）
            import hashlib
            folder_hash = hashlib.md5(folder_path.encode()).hexdigest()
            cache_file = os.path.join(cache_dir, f"audio_info_{folder_hash}.json")
            
            # 保存音频信息
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "folder_path": folder_path,
                    "timestamp": time.time(),
                    "audios": audio_info_list
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存{len(audio_info_list)} 个音频信息到缓存文件: {cache_file}")
        except Exception as e:
            logger.error(f"保存音频信息缓存失败: {str(e)}")

    def _load_audio_info_cache(self, folder_path):
        """
        从缓存文件加载音频信息
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            list: 音频信息列表，如果缓存不存在或已过期则返回None
        """
        try:
            # 确保缓存目录存在
            cache_dir = os.path.join(self.settings["temp_dir"], "audio_cache")
            
            # 生成缓存文件名（基于文件夹路径的哈希值）
            import hashlib
            folder_hash = hashlib.md5(folder_path.encode()).hexdigest()
            cache_file = os.path.join(cache_dir, f"audio_info_{folder_hash}.json")
            
            # 检查缓存文件是否存在
            if not os.path.exists(cache_file):
                return None
            
            # 读取缓存数据
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期（默认7天）
            cache_age = time.time() - cache_data.get("timestamp", 0)
            if cache_age > 7 * 24 * 60 * 60:  # 7天
                logger.info(f"音频缓存已过期: {cache_file}")
                return None
            
            # 验证路径是否存在
            audios = cache_data.get("audios", [])
            logger.info(f"已从缓存加载 {len(audios)} 个音频信息 {cache_file}")
            return audios
        except Exception as e:
            logger.warning(f"加载音频信息缓存失败: {str(e)}")
            return None

    def _scan_media_folder(self, folder_path, folder_type, target_folder_name=None):
        """
        扫描媒体文件夹（视频或配音）
        
        Args:
            folder_path (str): 父文件夹路径
            folder_type (str): 文件夹类型，"视频"或"配音"
            target_folder_name (str, optional): 目标子文件夹名称，默认None使用folder_type
            
        Returns:
            list: 包含媒体文件信息的列表
        """
        self.logger.info(f"检查目标文件夹: {os.path.normpath(folder_path)}")
        
        # 确保folder_path是字符串
        if not isinstance(folder_path, str):
            folder_path = str(folder_path)
            
        # 如果未指定目标文件夹名称，使用文件夹类型
        if target_folder_name is None:
            target_folder_name = folder_type
            
        result = []
        # 尝试直接访问目标子文件夹
        target_folder = os.path.join(folder_path, target_folder_name)
        
        # 如果目标子文件夹存在，直接扫描它
        if os.path.exists(target_folder) and os.path.isdir(target_folder):
            try:
                files = self._scan_media_files(target_folder, folder_type)
                
                # 处理找到的文件
                if folder_type == "视频":
                    for file_path in files:
                        try:
                            # 获取视频信息（路径必须是字符串）
                            file_info = {
                                "path": str(file_path),
                                "filename": os.path.basename(file_path)
                            }
                            
                            # 获取视频时长
                            try:
                                duration = self._get_video_duration(file_path)
                                file_info["duration"] = duration
                            except Exception as e:
                                self.logger.warning(f"获取视频时长失败: {file_path}, 错误: {str(e)}")
                                file_info["duration"] = 3.0  # 默认3秒
                                
                            result.append(file_info)
                        except Exception as e:
                            self.logger.warning(f"处理视频文件失败: {file_path}, 错误: {str(e)}")
                
                elif folder_type == "配音":
                    for file_path in files:
                        try:
                            # 音频文件使用轻量级元数据获取方法
                            audio_info = self._get_audio_metadata_lite(file_path)
                            if audio_info:
                                result.append(audio_info)
                        except Exception as e:
                            self.logger.warning(f"处理音频文件失败: {file_path}, 错误: {str(e)}")
                
                if result:
                    self.logger.info(f"在文件夹 {target_folder} 中找到{len(result)} 个{folder_type}文件")
                else:
                    self.logger.warning(f"在文件夹 {target_folder} 中未找到有效的{folder_type}文件")
                
                return result
            except Exception as e:
                self.logger.warning(f"扫描文件夹失败: {str(e)}")
        
        # 如果直接访问失败，尝试查找快捷方式
        shortcut_pattern = f"{target_folder_name}*.lnk"
        shortcut_files = glob.glob(os.path.join(folder_path, shortcut_pattern))
        
        if shortcut_files:
            shortcut_path = shortcut_files[0]  # 使用第一个找到的快捷方式
            try:
                # 解析快捷方式
                target_path = self._resolve_shortcut(shortcut_path)
                self.logger.info(f"解析{folder_type}快捷方式: {shortcut_path} -> {target_path}")
                
                if os.path.isdir(target_path):
                    # 递归调用扫描解析后的目标路径
                    return self._scan_media_folder(target_path, folder_type, "")
                else:
                    self.logger.warning(f"快捷方式目标不是文件: {target_path}")
            except Exception as e:
                self.logger.warning(f"解析快捷方式失败: {shortcut_path}, 错误: {str(e)}")
        
        # 如果所有尝试都失败，尝试搜索类似名称的文件
        similar_folders = [
            d for d in os.listdir(folder_path) 
            if os.path.isdir(os.path.join(folder_path, d)) and 
            (target_folder_name.lower() in d.lower() or folder_type.lower() in d.lower())
        ]
        
        if similar_folders:
            similar_folder = similar_folders[0]  # 使用第一个相似的文件
            self.logger.info(f"使用相似名称的文件夹: {similar_folder} 代替 {target_folder_name}")
            return self._scan_media_folder(os.path.join(folder_path, similar_folder), folder_type, "")
        
        # 如果无法找到相关文件夹，返回空列表
        self.logger.warning(f"找不到有效的{folder_type}文件: {target_folder}")
        return result

    def _save_video_info_cache(self, folder_path, video_info_list):
        """
        保存视频信息到缓存文件
        
        Args:
            folder_path: 文件夹路径
            video_info_list: 视频信息列表
        """
        try:
            # 创建缓存目录
            cache_dir = os.path.join(self.settings["temp_dir"], "video_cache")
            os.makedirs(cache_dir, exist_ok=True)
            
            # 生成缓存文件名（基于文件夹路径的哈希值）
            import hashlib
            folder_hash = hashlib.md5(folder_path.encode()).hexdigest()
            cache_file = os.path.join(cache_dir, f"video_info_{folder_hash}.json")
            
            # 保存视频信息
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "folder_path": folder_path,
                    "timestamp": time.time(),
                    "videos": video_info_list
                }, f, ensure_ascii=False, indent=2)
            
            logger.info(f"已保存{len(video_info_list)} 个视频信息到缓存文件: {cache_file}")
        except Exception as e:
            logger.error(f"保存视频信息缓存失败: {str(e)}")

    def _load_video_info_cache(self, folder_path):
        """
        从缓存文件加载视频信息
        
        Args:
            folder_path: 文件夹路径
            
        Returns:
            list: 视频信息列表，如果缓存不存在或已过期则返回None
        """
        try:
            # 创建缓存目录
            cache_dir = os.path.join(self.settings["temp_dir"], "video_cache")
            
            # 生成缓存文件名（基于文件夹路径的哈希值）
            import hashlib
            folder_hash = hashlib.md5(folder_path.encode()).hexdigest()
            cache_file = os.path.join(cache_dir, f"video_info_{folder_hash}.json")
            
            # 检查缓存文件是否存在
            if not os.path.exists(cache_file):
                return None
            
            # 读取缓存文件
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 检查缓存是否过期（默认7天）
            cache_age = time.time() - cache_data.get("timestamp", 0)
            if cache_age > 7 * 24 * 60 * 60:  # 7天
                logger.info(f"缓存已过期: {cache_file}")
                return None
            
            # 检查文件夹路径是否匹配
            if cache_data.get("folder_path") != folder_path:
                logger.warning(f"缓存文件夹路径不匹配: {cache_data.get('folder_path')} != {folder_path}")
                return None
            
            videos = cache_data.get("videos", [])
            logger.info(f"已从缓存加载 {len(videos)} 个视频信息 {cache_file}")
            return videos
        except Exception as e:
            logger.error(f"加载视频信息缓存失败: {str(e)}")
            return None
    
    def _scan_media_files(self, folder_path, folder_type, max_depth=3, _current_depth=0):
        """
        扫描给定文件夹中的媒体文件
        
        Args:
            folder_path (str): 要扫描的文件夹路径
            folder_type (str): "视频"或"配音"
            max_depth (int, optional): 最大递归深度
            _current_depth (int, optional): 当前递归深度，内部使用
            
        Returns:
            list: 媒体文件路径列表
        """
        # 确保文件夹路径是字符串
        if not isinstance(folder_path, str):
            folder_path = str(folder_path)
            
        # 检查文件夹是否存在
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            self.logger.warning(f"文件夹不存在或不是目录: {folder_path}")
            return []
            
        # 检查递归深度
        if _current_depth > max_depth:
            self.logger.debug(f"达到最大递归深度 {max_depth}，停止扫描: {folder_path}")
            return []
            
        # 初始化媒体文件列表
        media_files = []
        
        # 根据文件夹类型设置文件扩展名
        if folder_type == "视频":
            # 不区分大小写的视频扩展名
            extensions = ['.mp4', '.MP4', '.mov', '.MOV', '.avi', '.AVI', '.mkv', '.MKV', '.wmv', '.WMV']
        else:  # 配音
            # 不区分大小写的音频扩展名
            extensions = ['.mp3', '.MP3', '.wav', '.WAV', '.aac', '.AAC', '.m4a', '.M4A', '.ogg', '.OGG']
            
        try:
            # 使用os.scandir高效遍历文件
            for entry in os.scandir(folder_path):
                try:
                    # 处理快捷方式文件
                    if entry.is_file() and entry.name.lower().endswith('.lnk'):
                        try:
                            # 解析快捷方式获取目标路径
                            target_path = self._resolve_shortcut(entry.path)
                            
                            # 检查目标是否为目录
                            if os.path.isdir(target_path):
                                # 递归扫描快捷方式指向的目录
                                self.logger.debug(f"递归扫描快捷方式目标目录: {target_path}")
                                sub_files = self._scan_media_files(
                                    target_path, folder_type, max_depth, _current_depth + 1
                                )
                                media_files.extend(sub_files)
                            elif os.path.isfile(target_path):
                                # 检查文件扩展名
                                _, ext = os.path.splitext(target_path.lower())
                                if ext in [e.lower() for e in extensions]:
                                    media_files.append(target_path)
                                    
                        except Exception as e:
                            self.logger.warning(f"解析快捷方式失败: {entry.path}, 错误: {str(e)}")
                            
                    # 处理普通文件
                    elif entry.is_file():
                        _, ext = os.path.splitext(entry.name.lower())
                        if ext in [e.lower() for e in extensions]:
                            media_files.append(entry.path)
                            
                    # 递归处理子目录
                    elif entry.is_dir() and _current_depth < max_depth:
                        sub_files = self._scan_media_files(
                            entry.path, folder_type, max_depth, _current_depth + 1
                        )
                        media_files.extend(sub_files)
                        
                except Exception as e:
                    self.logger.warning(f"处理文件/文件夹失败: {entry.path if hasattr(entry, 'path') else '未知'}, 错误: {str(e)}")
                    
        except Exception as e:
            self.logger.warning(f"扫描文件夹失败: {folder_path}, 错误: {str(e)}")
            
        # 确保所有路径都是字符串
        media_files = [str(file_path) for file_path in media_files]
        
        self.logger.info(f"在文件夹 {folder_path} 中找到{len(media_files)} 个{folder_type}文件")
        return media_files

    def _get_video_duration_fast(self, video_path):
        """
        快速获取视频时长，优先使用FFprobe，然后是OpenCV
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            float: 视频时长（秒）
        """
        duration = 0.0
        
        # 尝试使用FFprobe获取时长（最快）
        try:
            import subprocess
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                   "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                duration = float(result.stdout.strip())
                logger.debug(f"使用FFprobe获取视频时长: {video_path}, 时长: {duration:.2f}秒")
                return duration
        except Exception as e:
            logger.debug(f"使用FFprobe获取视频时长失败: {str(e)}")
        
        # 尝试使用OpenCV获取时长
        try:
            cap = cv2.VideoCapture(video_path)
            if cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if fps > 0 and frame_count > 0:
                    duration = frame_count / fps
                    logger.debug(f"使用OpenCV获取视频时长: {video_path}, 时长: {duration:.2f}秒")
                cap.release()
                return duration
        except Exception as e:
            logger.debug(f"使用OpenCV获取视频时长失败: {str(e)}")
        
        # 尝试使用moviepy获取时长（最慢但最可靠）
        try:
            from moviepy.editor import VideoFileClip
            with VideoFileClip(video_path) as clip:
                duration = clip.duration
                logger.debug(f"使用MoviePy获取视频时长: {video_path}, 时长: {duration:.2f}秒")
                return duration
        except Exception as e:
            logger.debug(f"使用MoviePy获取视频时长失败: {str(e)}")
        
        # 最后尝试使用wmic获取时长（仅Windows）
        if sys.platform == 'win32':
            try:
                import subprocess
                # 修复f-string中的反斜杠问题
                path_escaped = video_path.replace("/", "\\\\")
                cmd = 'wmic path CIM_DataFile where name="' + path_escaped + '" get Duration /value'
                result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True, timeout=5)
                if result.returncode == 0 and result.stdout:
                    duration_str = result.stdout.strip()
                    if "Duration=" in duration_str:
                        duration_val = duration_str.split("=")[1].strip()
                        if duration_val and duration_val.isdigit():
                            duration = int(duration_val) / 10000000  # 转换为秒
                            logger.debug(f"使用WMIC获取视频时长: {video_path}, 时长: {duration:.2f}秒")
                            return duration
            except Exception as e:
                logger.debug(f"使用WMIC获取视频时长失败: {str(e)}")
        
        logger.warning(f"无法获取视频时长: {video_path}")
        return 0.0

    def _process_folder_shortcuts(self, parent_folder, folder_type, max_depth=3):
        """
        处理文件夹中的快捷方式，查找特定类型的子文件
        
        Args:
            parent_folder: 父文件夹路径
            folder_type: 文件夹类型，"视频"或"配音"
            max_depth: 最大搜索深度
            
        Returns:
            list: 找到的文件夹路径列表
        """
        from src.utils.file_utils import resolve_shortcut
        
        logger.debug(f"在{parent_folder}中查找{folder_type}文件...")
        
        # 检查父文件夹是否存在
        if not os.path.exists(parent_folder):
            logger.warning(f"父文件夹不存在: {parent_folder}")
            return []
        
        # 查找可能的文件夹名称
        possible_names = [
            folder_type,
            folder_type.lower(),
            folder_type.upper(),
            f"{folder_type}_文件",
            f"{folder_type.lower()}_文件",
            f"{folder_type.upper()}_文件"
        ]
        
        # 英文名称映射
        english_map = {
            "视频": ["video", "videos", "movie", "movies"],
            "配音": ["audio", "voice", "sound", "sounds"]
        }
        
        # 添加英文名称
        if folder_type in english_map:
            possible_names.extend(english_map[folder_type])
        
        # 找到的文件夹列表
        found_folders = []
        
        # 首先检查直接子文件
        try:
            for item in os.listdir(parent_folder):
                item_path = os.path.join(parent_folder, item)
                
                # 如果是目录，检查名称是否匹配
                if os.path.isdir(item_path):
                    item_lower = item.lower()
                    if any(name.lower() in item_lower for name in possible_names):
                        logger.debug(f"找到匹配的文件夹: {item_path}")
                        found_folders.append(item_path)
                
                # 如果是快捷方式，解析并检查
                elif item.lower().endswith('.lnk'):
                    try:
                        target = resolve_shortcut(item_path)
                        if target and os.path.exists(target) and os.path.isdir(target):
                            target_name = os.path.basename(target).lower()
                            if any(name.lower() in target_name for name in possible_names):
                                logger.debug(f"找到匹配的快捷方式文件夹: {item_path} -> {target}")
                                found_folders.append(target)
                    except Exception as e:
                        logger.debug(f"解析快捷方式失败: {item_path}, 错误: {str(e)}")
        except Exception as e:
            logger.warning(f"处理文件夹快捷方式时出错: {parent_folder}, 错误: {str(e)}")
        
        # 如果找到了文件夹，返回结果
        if found_folders:
            logger.info(f"在{parent_folder}中找到{len(found_folders)}个{folder_type}文件")
            return found_folders
        
        # 如果没有找到，尝试在父文件夹中查找
        if max_depth > 0:
            logger.debug(f"在{parent_folder}中未找到{folder_type}文件夹，尝试在父目录中查找")
            parent_dir = os.path.dirname(parent_folder)
            if parent_dir and parent_dir != parent_folder:
                parent_folders = self._process_folder_shortcuts(parent_dir, folder_type, max_depth - 1)
                if parent_folders:
                    return parent_folders
        
        logger.debug(f"未找到任何{folder_type}文件")
        return []

    def _get_audio_metadata(self, audio_path):
        """
        获取音频文件的元数据
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            dict: 音频元数据，包含路径、时长等信息
        """
        logger.debug(f"获取音频元数据: {audio_path}")
        
        # 确保路径是字符串并标准化
        if not isinstance(audio_path, str):
            audio_path = str(audio_path)
        
        audio_path = os.path.normpath(audio_path)
        
        # 检查文件是否存在
        if not os.path.exists(audio_path):
            # 尝试替换扩展名后再次检查
            base, ext = os.path.splitext(audio_path)
            if ext:
                # 尝试不同大小写的扩展名
                alt_exts = [ext.lower(), ext.upper()]
                for alt_ext in alt_exts:
                    if alt_ext != ext:  # 不要重复检查相同的扩展名
                        alt_path = base + alt_ext
                        if os.path.exists(alt_path):
                            logger.info(f"使用替代路径找到音频文件: {alt_path} (原路径: {audio_path})")
                            audio_path = alt_path
                            break
            
            # 如果仍然找不到文件
            if not os.path.exists(audio_path):
                logger.warning(f"音频文件不存在: {audio_path}")
                return None
        
        # 初始化元数据
        audio_info = {
            "path": audio_path,
            "duration": 0,
            "sample_rate": 0,
            "channels": 0
        }
        
        # 尝试使用FFprobe获取时长（最快）
        try:
            import subprocess
            ffprobe_cmd = self._get_ffmpeg_cmd().replace("ffmpeg", "ffprobe")
            cmd = [ffprobe_cmd, "-v", "error", "-show_entries", 
                   "format=duration : stream=sample_rate,channels", 
                   "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 3:
                    audio_info["duration"] = float(lines[0])
                    audio_info["sample_rate"] = int(float(lines[1]))
                    audio_info["channels"] = int(lines[2])
                    logger.debug(f"使用FFprobe获取音频元数据: {audio_path}, 时长: {audio_info['duration']:.2f}秒")
                    return audio_info
        except Exception as e:
            logger.debug(f"使用FFprobe获取音频元数据失败: {str(e)}")
        
        # 尝试使用moviepy获取时长
        try:
            from moviepy.editor import AudioFileClip
            with AudioFileClip(audio_path) as clip:
                audio_info["duration"] = clip.duration
                logger.debug(f"使用MoviePy获取音频时长: {audio_path}, 时长: {audio_info['duration']:.2f}秒")
                return audio_info
        except Exception as e:
            logger.debug(f"使用MoviePy获取音频元数据失败: {str(e)}")
        
        # 如果无法获取时长，返回None
        if audio_info["duration"] <= 0:
            logger.warning(f"无法获取音频时长: {audio_path}")
            return None
        
        return audio_info

    def _process_single_video(self, 
                             material_data: Dict[str, Dict[str, Any]], 
                             output_path: str, 
                             bgm_path: str = None,
                             progress_start: float = 0,
                             progress_end: float = 100) -> str:
        """
        处理单个视频，按照工作原理文档实现
        1. 分场景选择视频（单视频或多视频模式由用户设置决定）
        2. 根据配音时长裁剪视频（不变速）
        3. 将场景视频按顺序拼接
        
        Args:
            material_data: 素材数据字典，包含每个场景的视频和音频信息
            output_path: 输出视频路径
            bgm_path: 背景音乐路径，可为None
            progress_start: 进度起始百分比
            progress_end: 进度结束百分比
            
        Returns:
            str: 处理后的视频路径，失败时返回None
        """
        logger.info(f"开始处理单个视频 {output_path}")
        
        # 确保设置开始时间（如果尚未设置）
        if self.start_time == 0:
            self.start_time = time.time()
            # 启动进度定时器
            self._start_progress_timer()
        
        # 处理输出路径 - 在Windows上使用短路径格式以避免Unicode问题
        if os.name == 'nt':
            try:
                import win32api
                output_path = win32api.GetShortPathName(output_path)
                logger.debug(f"将输出路径转换为短路径: {output_path}")
            except Exception as e:
                logger.warning(f"无法将输出路径转换为短路径: {str(e)}")
        
        # 创建临时目录
        temp_dir = os.path.join(self.settings["temp_dir"], f"process_{int(time.time())}")
        os.makedirs(temp_dir, exist_ok=True)
        logger.info(f"创建临时目录: {temp_dir}")
        
        try:
            # 阶段1: 准备阶段 - 收集所有需要处理的场景
            scenes = []
            scene_concat_files = []
            
            # 计算每个场景的进度
            progress_range = progress_end - progress_start
            
            # 收集所有场景
            scene_count = len(material_data)
            
            # 记录总音频时长，用于确定是否需要视频混剪（音频较长）或单视频处理（音频较短）
            total_audio_duration = 0
            
            # 检查是否需要重新扫描音频文件 - 如果所有场景都没有找到音频
            audio_missing = True
            for folder_key, folder_data in material_data.items():
                if folder_data.get("audios"):
                    audio_missing = False
                    break
            
            if audio_missing:
                logger.warning("所有场景都没有找到音频文件，尝试重新扫描配音文件夹")
                for folder_key, folder_data in material_data.items():
                    folder_path = folder_data.get("folder_path")
                    if folder_path and os.path.exists(folder_path):
                        audio_folder = os.path.join(folder_path, "配音")
                        if os.path.exists(audio_folder):
                            logger.info(f"尝试再次扫描配音文件夹: {audio_folder}")
                            # 支持的音频扩展名（大小写都包含）
                            audio_extensions = ['.mp3', '.MP3', '.wav', '.WAV', '.aac', '.AAC', 
                                              '.ogg', '.OGG', '.flac', '.FLAC', '.m4a', '.M4A']
                            audios = []
                            # 直接列出所有文件
                            for file in os.listdir(audio_folder):
                                file_path = os.path.join(audio_folder, file)
                                if os.path.isfile(file_path):
                                    ext = os.path.splitext(file)[1]
                                    if any(file.endswith(ext) for ext in audio_extensions):
                                        audio_info = self._get_audio_metadata_lite(file_path)
                                        if audio_info:
                                            audios.append(audio_info)
                                            logger.info(f"找到音频文件: {file_path}")
                        
                            if audios:
                                material_data[folder_key]["audios"] = audios
                                logger.info(f"为场景{folder_key} 找到 {len(audios)} 个音频文件")
            
            for folder_key, folder_data in material_data.items():
                if not folder_data.get("videos"):
                    logger.warning(f"跳过没有视频文件的场景: {folder_key}")
                    continue
                
                # 添加场景
                scenes.append({
                    "key": folder_key,
                    "videos": folder_data.get("videos", []),
                    "audios": folder_data.get("audios", []),
                    "extract_mode": folder_data.get("extract_mode", "single_video")  # 从用户设置中获取抽取模式
                })
                
                # 计算场景音频时长
                for audio in folder_data.get("audios", []):
                    total_audio_duration += audio.get("duration", 0)
                    
            # 没有有效场景，提前返回
            if not scenes:
                logger.error("没有找到有效场景，处理结束")
                return None
                
            # 创建拼接文件目录
            concat_dir = os.path.join(temp_dir, "concat")
            os.makedirs(concat_dir, exist_ok=True)
            
            # 阶段2: 视频处理阶段 - 创建每个场景的临时输出
            scene_videos = []
            
            # 处理每个场景
            for i, scene in enumerate(scenes):
                # 计算当前场景的进度范围
                scene_progress_start = progress_start + (progress_range * i / len(scenes))
                scene_progress_end = progress_start + (progress_range * (i + 1) / len(scenes))
                
                # 创建场景临时输出文件
                scene_output = os.path.join(temp_dir, f"scene_{i+1}.mp4")
                
                # 准备场景的视频和音频
                scene_videos_list = scene["videos"]
                scene_audios_list = scene["audios"]
                
                # 确定场景的音频时长 - 如果有多个音频，随机选择一个或使用默认时长
                scene_audio_duration = 0
                scene_audio_file = None
                
                if scene_audios_list:
                    # 随机选择一个音频文件
                    import random
                    selected_audio = random.choice(scene_audios_list)
                    scene_audio_duration = selected_audio.get("duration", 0)
                    scene_audio_file = selected_audio.get("path")
                    logger.info(f"场景 {i+1} 选择配音: {os.path.basename(scene_audio_file)}, 时长: {scene_audio_duration:.2f}秒")
                else:
                    # 使用默认的音频时长
                    scene_audio_duration = self.settings.get("default_audio_duration", 10.0)
                    logger.info(f"场景 {i+1} 使用默认配音时长: {scene_audio_duration:.2f}秒")
                
                # 【工作原理实现】使用用户设置的抽取模式，而不是自动决定
                use_multi_video = scene.get("extract_mode") == "multi_video"
                logger.info(f"场景 {i+1} 使用抽取模式: {'多视频混剪' if use_multi_video else '单视频'}")
                
                # 根据模式处理视频
                if use_multi_video:
                    # 多视频模式 - 随机选择多个视频直到总时长超过配音时长
                    logger.info(f"场景 {i+1} 使用多视频混剪模式 配音时长 {scene_audio_duration:.2f}秒")
                    if scene_videos_list:
                        # 随机打乱视频列表
                        import random
                        shuffled_videos = list(scene_videos_list)
                        random.shuffle(shuffled_videos)
                        
                        # 选择视频直到总时长超过音频时长
                        selected_videos = []
                        total_video_duration = 0
                        
                        for video in shuffled_videos:
                            video_duration = video.get("duration", 0)
                            selected_videos.append(video)
                            total_video_duration += video_duration
                            if total_video_duration >= scene_audio_duration:
                                break
                        
                        if not selected_videos:
                            logger.warning(f"场景 {i+1} 没有找到足够的视频，跳过")
                            continue
                        
                        logger.info(f"为场景{i+1} 选择{len(selected_videos)} 个视频，总时长{total_video_duration:.2f}秒")
                        
                        # 创建concat文件
                        concat_file_path = os.path.join(concat_dir, f"scene_{i+1}_concat.txt")
                        scene_concat_files.append(concat_file_path)
                        
                        with open(concat_file_path, 'w', encoding='utf-8') as concat_file:
                            # 写入除最后一个视频外的所有视频（不裁剪）
                            for j, video in enumerate(selected_videos[:-1]):
                                video_file = video["path"]
                                if not isinstance(video_file, str):
                                    video_file = str(video_file)
                                video_file_escaped = video_file.replace("'", "\\'")
                                concat_file.write(f"file '{video_file_escaped}'\n")
                            
                            # 处理最后一个视频 - 如果需要裁剪
                            if selected_videos:
                                last_video = selected_videos[-1]
                                last_video_path = last_video["path"]
                                if not isinstance(last_video_path, str):
                                    last_video_path = str(last_video_path)
                                
                                # 计算最后一个视频应该的时长
                                previous_videos_duration = sum(v.get("duration", 0) for v in selected_videos[:-1])
                                last_video_needed_duration = scene_audio_duration - previous_videos_duration
                                
                                # 如果需要裁剪最后一个视频（只有当需要裁剪的时长小于视频原始时长）
                                last_video_duration = last_video.get("duration", 0)
                                
                                if 0 < last_video_needed_duration < last_video_duration:
                                    # 裁剪最后一个视频
                                    trimmed_last_video = os.path.join(temp_dir, f"trimmed_last_video_{i+1}.mp4")
                                    
                                    # 使用FFmpeg裁剪（不改变速度，只裁剪时长）
                                    trim_cmd = [
                                        self._get_ffmpeg_cmd(),
                                        "-y",
                                        "-i", last_video_path,
                                        "-t", str(last_video_needed_duration + 0.1),  # 添加0.1秒缓冲
                                        "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                                        "-r", "30",  # 强制使用30fps的输出帧率
                                        "-fflags", "+genpts",  # 生成准确的时间戳
                                        "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                                        "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                                        "-c:v", "copy",  # 不重新编码视频
                                        "-c:a", "copy",  # 不重新编码音频
                                        trimmed_last_video
                                    ]
                                    
                                    try:
                                        logger.info(f"裁剪最后一个视频到 {last_video_needed_duration:.2f}秒 {' '.join(trim_cmd)}")
                                        subprocess.run(trim_cmd, check=True)
                                        
                                        # 在concat文件中使用裁剪后的视频
                                        trimmed_path_escaped = trimmed_last_video.replace("'", "\\'")
                                        concat_file.write(f"file '{trimmed_path_escaped}'\n")
                                    except Exception as e:
                                        logger.warning(f"裁剪最后一个视频失败: {str(e)}，使用原始视频")
                                        video_file_escaped = last_video_path.replace("'", "\\'")
                                        concat_file.write(f"file '{video_file_escaped}'\n")
                                else:
                                    # 不需要裁剪，直接使用原始视频
                                    video_file_escaped = last_video_path.replace("'", "\\'")
                                    concat_file.write(f"file '{video_file_escaped}'\n")
                        
                        # 执行拼接，生成场景视频
                        concat_cmd = [
                            self._get_ffmpeg_cmd(),
                            "-y",
                            "-f", "concat",
                            "-safe", "0",
                            "-i", concat_file_path,
                            "-c", "copy"  # 直接复制，不重新编码
                        ]
                        
                        # 如果有音频，替换音频
                        if scene_audio_file:
                            # 先拼接视频到临时文件
                            temp_video = os.path.join(temp_dir, f"temp_scene_{i+1}.mp4")
                            concat_cmd.append(temp_video)
                            
                            try:
                                logger.info(f"拼接视频: {' '.join(concat_cmd)}")
                                subprocess.run(concat_cmd, check=True)
                                
                                # 替换音频
                                audio_cmd = [
                                    self._get_ffmpeg_cmd(),
                                    "-y",
                                    "-i", temp_video,  # 视频输入
                                    "-i", scene_audio_file,  # 音频输入
                                    "-map", "0:v:0",  # 使用第一个输入的视频
                                    "-map", "1:a:0",  # 使用第二个输入的音频
                                    "-c:v", "copy",  # 不重新编码视频
                                    "-c:a", "aac",  # 音频转AAC格式（兼容性好）
                                    "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                                    "-r", "30",  # 强制使用30fps的输出帧率
                                    "-fflags", "+genpts",  # 生成准确的时间戳
                                    "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                                    "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                                    "-async", "1",  # 音频同步处理
                                    "-t", str(scene_audio_duration + 0.1),  # 添加0.1秒缓冲
                                    scene_output
                                ]
                                
                                logger.info(f"替换音频: {' '.join(audio_cmd)}")
                                subprocess.run(audio_cmd, check=True)
                                
                                # 添加到场景视频列表
                                scene_videos.append(scene_output)
                                logger.info(f"场景 {i+1} 处理完成")
                            except Exception as e:
                                logger.error(f"处理场景 {i+1} 失败: {str(e)}")
                        else:
                            # 没有音频，直接输出到场景视频文件
                            concat_cmd.append(scene_output)
                            
                            try:
                                logger.info(f"拼接视频: {' '.join(concat_cmd)}")
                                subprocess.run(concat_cmd, check=True)
                                
                                # 添加到场景视频列表
                                scene_videos.append(scene_output)
                                logger.info(f"场景 {i+1} 处理完成")
                            except Exception as e:
                                logger.error(f"处理场景 {i+1} 失败: {str(e)}")
                    else:
                        logger.warning(f"场景 {i+1} 没有视频文件，跳过")
                else:
                    # 单视频模式 - 随机选择一个时长足够的视频
                    logger.info(f"场景 {i+1} 使用单视频模式 配音时长 {scene_audio_duration:.2f}秒")
                    
                    if scene_videos_list:
                        # 过滤出时长大于等于音频时长的视频
                        suitable_videos = [v for v in scene_videos_list if v.get("duration", 0) >= scene_audio_duration]
                        
                        # 如果没有足够长的视频，使用所有视频
                        if not suitable_videos:
                            logger.warning(f"场景 {i+1} 没有足够长的视频，使用所有视频")
                            suitable_videos = scene_videos_list
                        
                        # 随机选择一个视频
                        import random
                        selected_video = random.choice(suitable_videos)
                        video_file = selected_video["path"]
                        video_duration = selected_video.get("duration", 0)
                        
                        # 检查视频时长是否足够，如果不足配音时长的一半，则切换到多视频模式
                        if video_duration < scene_audio_duration * 0.5:
                            logger.warning(f"场景 {i+1} 所选视频时长({video_duration:.2f}秒)不足配音时长的一半({scene_audio_duration:.2f}秒)，强制切换到多视频模式")
                            
                            # 以下代码实现多视频模式，类似于上面的多视频处理逻辑
                            # 随机打乱视频列表
                            shuffled_videos = list(scene_videos_list)
                            random.shuffle(shuffled_videos)
                            
                            # 选择视频直到总时长超过音频时长
                            selected_videos = []
                            total_video_duration = 0
                            
                            for video in shuffled_videos:
                                video_duration = video.get("duration", 0)
                                selected_videos.append(video)
                                total_video_duration += video_duration
                                if total_video_duration >= scene_audio_duration:
                                    break
                            
                            if not selected_videos:
                                logger.warning(f"场景 {i+1} 没有找到足够的视频，跳过")
                                continue
                            
                            logger.info(f"为场景{i+1} 选择{len(selected_videos)} 个视频，总时长{total_video_duration:.2f}秒")
                            
                            # 创建concat文件
                            concat_file_path = os.path.join(concat_dir, f"scene_{i+1}_concat.txt")
                            scene_concat_files.append(concat_file_path)
                            
                            with open(concat_file_path, 'w', encoding='utf-8') as concat_file:
                                # 写入除最后一个视频外的所有视频（不裁剪）
                                for j, video in enumerate(selected_videos[:-1]):
                                    video_file = video["path"]
                                    if not isinstance(video_file, str):
                                        video_file = str(video_file)
                                    video_file_escaped = video_file.replace("'", "\\'")
                                    concat_file.write(f"file '{video_file_escaped}'\n")
                                
                                # 处理最后一个视频 - 如果需要裁剪
                                if selected_videos:
                                    last_video = selected_videos[-1]
                                    last_video_path = last_video["path"]
                                    if not isinstance(last_video_path, str):
                                        last_video_path = str(last_video_path)
                                    
                                    # 计算最后一个视频应该的时长
                                    previous_videos_duration = sum(v.get("duration", 0) for v in selected_videos[:-1])
                                    last_video_needed_duration = scene_audio_duration - previous_videos_duration
                                    
                                    # 如果需要裁剪最后一个视频（只有当需要裁剪的时长小于视频原始时长）
                                    last_video_duration = last_video.get("duration", 0)
                                    
                                    if 0 < last_video_needed_duration < last_video_duration:
                                        # 裁剪最后一个视频
                                        trimmed_last_video = os.path.join(temp_dir, f"trimmed_last_video_{i+1}.mp4")
                                        
                                        # 使用FFmpeg裁剪（不改变速度，只裁剪时长）
                                        trim_cmd = [
                                            self._get_ffmpeg_cmd(),
                                            "-y",
                                            "-i", last_video_path,
                                            "-t", str(last_video_needed_duration + 0.1),  # 添加0.1秒缓冲
                                            "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                                            "-r", "30",  # 强制使用30fps的输出帧率
                                            "-fflags", "+genpts",  # 生成准确的时间戳
                                            "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                                            "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                                            "-c:v", "copy",  # 不重新编码视频
                                            "-c:a", "copy",  # 不重新编码音频
                                            trimmed_last_video
                                        ]
                                        
                                        try:
                                            logger.info(f"裁剪最后一个视频到 {last_video_needed_duration:.2f}秒 {' '.join(trim_cmd)}")
                                            subprocess.run(trim_cmd, check=True)
                                            
                                            # 在concat文件中使用裁剪后的视频
                                            trimmed_path_escaped = trimmed_last_video.replace("'", "\\'")
                                            concat_file.write(f"file '{trimmed_path_escaped}'\n")
                                        except Exception as e:
                                            logger.warning(f"裁剪最后一个视频失败: {str(e)}，使用原始视频")
                                            video_file_escaped = last_video_path.replace("'", "\\'")
                                            concat_file.write(f"file '{video_file_escaped}'\n")
                                    else:
                                        # 不需要裁剪，直接使用原始视频
                                        video_file_escaped = last_video_path.replace("'", "\\'")
                                        concat_file.write(f"file '{video_file_escaped}'\n")
                            
                            # 执行拼接，生成场景视频
                            concat_cmd = [
                                self._get_ffmpeg_cmd(),
                                "-y",
                                "-f", "concat",
                                "-safe", "0",
                                "-i", concat_file_path,
                                "-c", "copy"  # 直接复制，不重新编码
                            ]
                            
                            # 如果有音频，替换音频
                            if scene_audio_file:
                                # 先拼接视频到临时文件
                                temp_video = os.path.join(temp_dir, f"temp_scene_{i+1}.mp4")
                                concat_cmd.append(temp_video)
                                
                                try:
                                    logger.info(f"拼接视频: {' '.join(concat_cmd)}")
                                    subprocess.run(concat_cmd, check=True)
                                    
                                    # 替换音频
                                    audio_cmd = [
                                        self._get_ffmpeg_cmd(),
                                        "-y",
                                        "-i", temp_video,  # 视频输入
                                        "-i", scene_audio_file,  # 音频输入
                                        "-map", "0:v:0",  # 使用第一个输入的视频
                                        "-map", "1:a:0",  # 使用第二个输入的音频
                                        "-c:v", "copy",  # 不重新编码视频
                                        "-c:a", "aac",  # 音频转AAC格式（兼容性好）
                                        "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                                        "-r", "30",  # 强制使用30fps的输出帧率
                                        "-fflags", "+genpts",  # 生成准确的时间戳
                                        "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                                        "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                                        "-async", "1",  # 音频同步处理
                                        "-t", str(scene_audio_duration + 0.1),  # 添加0.1秒缓冲
                                        scene_output
                                    ]
                                    
                                    logger.info(f"替换音频: {' '.join(audio_cmd)}")
                                    subprocess.run(audio_cmd, check=True)
                                    
                                    # 添加到场景视频列表
                                    scene_videos.append(scene_output)
                                    logger.info(f"场景 {i+1} 处理完成")
                                except Exception as e:
                                    logger.error(f"处理场景 {i+1} 失败: {str(e)}")
                            else:
                                # 没有音频，直接输出到场景视频文件
                                concat_cmd.append(scene_output)
                                
                                try:
                                    logger.info(f"拼接视频: {' '.join(concat_cmd)}")
                                    subprocess.run(concat_cmd, check=True)
                                    
                                    # 添加到场景视频列表
                                    scene_videos.append(scene_output)
                                    logger.info(f"场景 {i+1} 处理完成")
                                except Exception as e:
                                    logger.error(f"处理场景 {i+1} 失败: {str(e)}")
                            
                            # 跳过常规单视频模式处理
                            continue
                        
                        logger.info(f"为场景{i+1} 选择视频: {os.path.basename(video_file)}, 时长: {video_duration:.2f}秒")
                        
                        # 确保视频文件路径是字符串
                        if not isinstance(video_file, str):
                            video_file = str(video_file)
                        
                        # 处理视频 - 裁剪到配音时长
                        try:
                            # 如果有音频，同时处理视频和音频
                            if scene_audio_file:
                                cmd = [
                                    self._get_ffmpeg_cmd(),
                                    "-y",
                                    "-i", video_file,  # 视频输入
                                    "-i", scene_audio_file,  # 音频输入
                                    "-map", "0:v:0",  # 使用第一个输入的视频
                                    "-map", "1:a:0",  # 使用第二个输入的音频
                                    "-c:v", "copy",  # 不重新编码视频
                                    "-c:a", "aac",  # 音频转AAC格式
                                    "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                                    "-r", "30",  # 强制使用30fps的输出帧率
                                    "-fflags", "+genpts",  # 生成准确的时间戳
                                    "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                                    "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                                    "-async", "1",  # 音频同步处理
                                    "-t", str(scene_audio_duration + 0.1),  # 添加0.1秒缓冲
                                    scene_output
                                ]
                            else:
                                # 没有音频，只处理视频
                                cmd = [
                                    self._get_ffmpeg_cmd(),
                                    "-y",
                                    "-i", video_file,
                                    "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                                    "-r", "30",  # 强制使用30fps的输出帧率
                                    "-fflags", "+genpts",  # 生成准确的时间戳
                                    "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                                    "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                                    "-t", str(scene_audio_duration + 0.1),
                                    "-c:v", "copy",  # 不重新编码视频
                                    "-c:a", "copy",  # 不重新编码音频
                                    scene_output
                                ]
                            
                            logger.info(f"处理视频: {' '.join(cmd)}")
                            subprocess.run(cmd, check=True)
                            
                            # 添加到场景视频列表
                            scene_videos.append(scene_output)
                            logger.info(f"场景 {i+1} 处理完成")
                        except Exception as e:
                            logger.error(f"处理场景 {i+1} 失败: {str(e)}")
                    else:
                        logger.warning(f"场景 {i+1} 没有视频文件，跳过")
            
            # 没有处理好的场景视频，提前返回
            if not scene_videos:
                logger.error("没有生成任何场景视频，处理结束")
                return None
            
            # 阶段3: 最终合并阶段 - 拼接所有场景视频
            logger.info(f"开始拼接{len(scene_videos)} 个场景视频...")
            
            # 创建最终concat文件
            concat_file = os.path.join(temp_dir, "final_concat.txt")
            try:
                with open(concat_file, "w", encoding="utf-8") as f:
                    for scene_video in scene_videos:
                        # 确保路径是字符串
                        if not isinstance(scene_video, str):
                            scene_video = str(scene_video)
                        
                        # 处理路径中的单引号
                        scene_video_escaped = scene_video.replace("'", "\\'")
                        f.write(f"file '{scene_video_escaped}'\n")
            except Exception as e:
                logger.error(f"创建concat文件失败: {str(e)}")
                return None
            
            # 拼接所有视频
            merge_cmd = [
                self._get_ffmpeg_cmd(),
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                "-r", "30",  # 强制使用30fps的输出帧率
                "-fflags", "+genpts",  # 生成准确的时间戳
                "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                "-async", "1",  # 音频同步处理
                "-c:v", "copy",  # 不重新编码视频
                "-c:a", "aac"  # 音频强制编码为AAC以提高兼容性
            ]
            
            # 添加背景音乐
            if bgm_path and os.path.exists(bgm_path):
                # 拼接没有音频的视频版本
                temp_merge_without_audio = os.path.join(temp_dir, "temp_merged_no_audio.mp4")
                temp_merge_cmd = merge_cmd.copy()
                temp_merge_cmd.append("-an")  # 去除音频
                temp_merge_cmd.append(temp_merge_without_audio)
                
                try:
                    logger.info(f"创建无音频临时合并视频: {' '.join(temp_merge_cmd)}")
                    subprocess.run(temp_merge_cmd, check=True)
                    
                    # 修改此部分，直接使用concat合并的视频音频
                    # 不再单独提取音频，而是使用原始场景视频的音频（含配音和缓冲）
                    temp_with_original_audio = os.path.join(temp_dir, "temp_with_original_audio.mp4")
                    
                    # 先合并所有场景视频（保留原始配音+缓冲）
                    original_audio_cmd = merge_cmd.copy()
                    original_audio_cmd.append(temp_with_original_audio)
                    
                    logger.info(f"合并保留原始音频（配音+缓冲）的场景视频: {' '.join(original_audio_cmd)}")
                    subprocess.run(original_audio_cmd, check=True)
                    
                    # 从合并视频中提取音频（保留了每个配音间的缓冲）
                    temp_audio = os.path.join(temp_dir, "temp_original_audio.aac")
                    audio_extract_cmd = [
                        self._get_ffmpeg_cmd(),
                        "-y",
                        "-i", temp_with_original_audio,  # 合并后的含原始音频的视频
                        "-c:a", "aac",
                        "-vn",  # 不包含视频
                        temp_audio
                    ]
                    
                    logger.info(f"提取合并视频的原始音频（保留每个配音间的0.1秒留白）: {' '.join(audio_extract_cmd)}")
                    subprocess.run(audio_extract_cmd, check=True)
                    
                    # 添加背景音乐和原始音频
                    audio_mix_cmd = [
                        self._get_ffmpeg_cmd(),
                        "-y",
                        "-i", temp_merge_without_audio,  # 视频（无音频）
                        "-i", temp_audio,  # 原始音频（已包含配音间的留白）
                        "-i", bgm_path,  # 背景音乐
                        "-filter_complex",
                        f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={self.settings.get('voice_volume', 1.0)}[voice];" +
                        f"[2:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={self.settings.get('bgm_volume', 0.3)}[bgm];" +
                        "[voice][bgm]amix=inputs=2:duration=first[aout]",
                        "-map", "0:v:0",  # 使用第一个输入的视频流
                        "-map", "[aout]",  # 使用混合后的音频流
                        "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                        "-r", "30",  # 强制使用30fps的输出帧率
                        "-fflags", "+genpts",  # 生成准确的时间戳
                        "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                        "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                        "-async", "1",  # 音频同步处理
                        "-c:v", "copy",  # 不重新编码视频
                        "-c:a", "aac",  # 音频使用AAC编码
                        output_path
                    ]
                    
                    logger.info(f"添加背景音乐: {' '.join(audio_mix_cmd)}")
                    subprocess.run(audio_mix_cmd, check=True)
                    
                    return output_path
                except Exception as e:
                    logger.error(f"添加背景音乐失败: {str(e)}")
                    # 如果背景音乐处理失败，尝试使用原始合并视频
                    try:
                        import shutil
                        logger.warning("尝试使用无背景音乐的版本...")
                        shutil.copy(temp_merge_without_audio, output_path)
                        return output_path
                    except Exception as copy_error:
                        logger.error(f"复制备份视频失败: {str(copy_error)}")
                        return None
            else:
                # 没有背景音乐，直接输出
                merge_cmd.append(output_path)
                
                try:
                    logger.info(f"合并所有场景视频: {' '.join(merge_cmd)}")
                    subprocess.run(merge_cmd, check=True)
                    return output_path
                except Exception as e:
                    logger.error(f"合并视频失败: {str(e)}")
                    return None
                
        except Exception as e:
            logger.error(f"处理视频时出错: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
        
        finally:
            # 清理临时文件
            if self.settings.get("clean_temp_files", True):
                try:
                    import shutil
                    logger.info(f"清理临时文件: {temp_dir}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"清理临时文件失败: {str(e)}")
            
            # 释放内存
            gc.collect()

    def _get_ffmpeg_cmd(self):
        """
        获取FFmpeg命令
        
        Returns:
            str: FFmpeg命令路径
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
                        logger.debug(f"使用自定义FFmpeg路径: {custom_path}")
                        return custom_path
        except Exception as e:
            logger.warning(f"读取自定义FFmpeg路径时出错: {str(e)}")
        
        return ffmpeg_cmd

    def _resolve_shortcut(self, shortcut_path):
        """
        解析Windows快捷方式(.lnk)，获取目标路径
        
        Args:
            shortcut_path (str): 快捷方式文件路径
            
        Returns:
            str: 快捷方式指向的目标路径
        """
        try:
            # 确保路径是字符串
            if not isinstance(shortcut_path, str):
                shortcut_path = str(shortcut_path)
                
            # 使用file_utils中的方法
            from src.utils.file_utils import resolve_shortcut
            target_path = resolve_shortcut(shortcut_path)
            
            # 确保返回的也是字符串
            if target_path and not isinstance(target_path, str):
                target_path = str(target_path)
                
            return target_path
            
        except Exception as e:
            self.logger.warning(f"解析快捷方式失败: {shortcut_path}, 错误: {str(e)}")
            return None

    def direct_process_parent_folder(self, parent_folder_path: str, output_path: str, bgm_path: str = None) -> bool:
        # ... existing code ...
        # 构建基本合并命令 - 使用concat demuxer
        cmd = [
            ffmpeg_cmd,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
            "-r", "30",  # 强制使用30fps的输出帧率
            "-fflags", "+genpts",  # 添加生成正确时间戳的参数
            "-avoid_negative_ts", "make_zero",  # 避免负时间戳
            "-max_muxing_queue_size", "1024",  # 增加复用队列大小
            "-i", list_file
        ]
        
        # 默认音频时长 - 避免未定义的变量错误
        max_duration = 30.0  # 默认30秒
        
        # 尝试获取所有音频的总时长作为限制
        try:
            audios_durations = []
            for i, subfolder in enumerate(subfolders):
                audio_folder = os.path.join(subfolder, "配音")
                if os.path.exists(audio_folder) and os.path.isdir(audio_folder):
                    for root, _, files in os.walk(audio_folder):
                        for file in files:
                            if file.lower().endswith((".mp3", ".wav", ".aac", ".ogg", ".flac")):
                                audio_path = os.path.join(root, file)
                                # 使用FFprobe获取音频时长
                                try:
                                    ffprobe_cmd = self._get_ffmpeg_cmd().replace("ffmpeg", "ffprobe")
                                    cmd_duration = [ffprobe_cmd, "-v", "error", "-show_entries", 
                                                  "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
                                    result = subprocess.run(cmd_duration, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                                    if result.returncode == 0 and result.stdout.strip():
                                        audios_durations.append(float(result.stdout.strip()))
                                except Exception as e:
                                    logger.warning(f"获取音频时长失败: {audio_path}, {str(e)}")
                
                # 计算所有音频的总时长
                if audios_durations:
                    max_duration = sum(audios_durations)
                    logger.info(f"计算出所有音频总时长: {max_duration:.2f}秒")
        except Exception as e:
            logger.warning(f"计算音频总时长出错: {str(e)}")
        
        # 添加输出时长限制参数
        cmd.extend(["-t", str(max_duration + 0.2)])  # 增加0.2秒余量避免视频定格
        
        # 判断是否需要添加背景音乐
        if bgm_path and os.path.exists(bgm_path):
            # 如果需要添加背景音乐，则需要两步处理
            # 1. 先使用concat demuxer合并视频并保留原始音频
            temp_merged_video = self._create_temp_file("direct_merged_video", ".mp4")
            
            # 使用copy编解码器直接拼接，避免重新编码
            concat_cmd = cmd + [
                "-c", "copy",  # 保持原有音频和视频
                "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                "-r", "30",  # 强制使用30fps的输出帧率
                "-fflags", "+genpts",  # 添加生成正确时间戳的参数
                "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                "-movflags", "+faststart",
                temp_merged_video
            ]

    def _fallback_concat_videos(self, videos, output_path, bgm_path=None):
        """当常规合并方法失败时的备用方法"""
        self.report_progress("尝试使用备用方法合成视频...", 85)
        
        # 提取所有视频路径
        video_paths = []
        for video in videos:
            path = video.get("path", "")
            if path and os.path.exists(path):
                video_paths.append(path)
        
        if not video_paths:
            logger.error("没有有效的视频路径，无法使用备用方法合成")
            return False
            
        # 获取第一个视频的路径
        first_video = video_paths[0]
        
        # 使用FFmpeg直接将所有视频连接起来
        try:
            # 获取FFmpeg命令
            ffmpeg_cmd = self._get_ffmpeg_cmd()
            
            # 创建临时文件列表
            temp_list_file = self._create_temp_file("fallback_list", ".txt")
            with open(temp_list_file, "w", encoding="utf-8") as f:
                for vid_path in video_paths:
                    # 处理路径中的单引号，避免f-string中使用反斜杠
                    vid_path_escaped = vid_path.replace("'", r"\'")
                    f.write(f"file '{vid_path_escaped}'\n")
            
            # 构建命令
            cmd = [
                ffmpeg_cmd,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", temp_list_file,
                "-fps_mode", "cfr",  # 使用恒定帧率模式代替旧的vsync
                "-r", "30",  # 强制使用30fps的输出帧率
                "-fflags", "+genpts",  # 添加生成正确时间戳的参数
                "-avoid_negative_ts", "make_zero",  # 避免负时间戳
                "-max_muxing_queue_size", "1024",  # 增加复用队列大小
                "-c", "copy",
                "-movflags", "+faststart",
                output_path
            ]
            
            logger.info(f"执行备用视频拼接命令: {' '.join(cmd)}")
            
            try:
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info(f"备用方法成功，输出到: {output_path}")
                self.report_progress("视频合成完成！", 100)
                return True
            except subprocess.CalledProcessError as e:
                logger.error(f"备用方法失败: {e.stderr}")
                
                # 如果FFmpeg失败，尝试直接复制文件
                import shutil
                shutil.copy2(first_video, output_path)
                logger.info(f"已直接复制第一个视频 {first_video} 到 {output_path}")
                return True
                
        except Exception as e:
            logger.error(f"备用合成方法失败: {str(e)}")
            return False
