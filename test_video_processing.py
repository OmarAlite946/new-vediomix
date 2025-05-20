import os
import sys
import time
import shutil
from pathlib import Path
sys.path.append('.')

from src.core.video_processor import VideoProcessor
from src.utils.logger import get_logger

logger = get_logger()

def progress_callback(message, percent):
    """进度回调函数"""
    print(f"进度 {percent:.1f}%: {message}")

def main():
    """测试完整的视频处理流程"""
    print("开始测试视频处理流程")
    
    # 初始化VideoProcessor
    vp = VideoProcessor({
        'temp_dir': 'temp',
        'ffmpeg_path': 'D:/ffmpeg_compat/ffmpeg.exe',
        'default_audio_duration': 10.0,
        'clean_temp_files': False,  # 不清理临时文件，方便查看结果
        'hwaccel': 'nvenc',  # 可选: nvenc, qsv, amf
        'preset': 'medium',
        'crf': 23,
        'bgm_volume': 0.3
    }, progress_callback)
    
    print("VideoProcessor初始化成功")
    
    # 创建输出目录
    output_dir = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # 准备测试场景文件夹
    test_folders = []
    # 请替换为实际存在的路径
    base_folder = "E:/视频/素材/高手接话素材/高手接话003无头版"
    
    if os.path.exists(base_folder):
        sub_folders = [f for f in os.listdir(base_folder) 
                      if os.path.isdir(os.path.join(base_folder, f))]
        
        # 选择前3个子文件夹作为测试
        for i, folder in enumerate(sub_folders[:3]):
            full_path = os.path.join(base_folder, folder)
            test_folders.append({
                "name": f"测试场景{i+1}",
                "folder_path": full_path
            })
    
    if not test_folders:
        print("未找到测试文件夹，使用模拟数据")
        # 模拟数据
        test_folders = [
            {"name": "测试场景1", "folder_path": "E:/视频/素材/测试场景1"},
            {"name": "测试场景2", "folder_path": "E:/视频/素材/测试场景2"},
        ]
    
    print(f"使用 {len(test_folders)} 个测试文件夹")
    for folder in test_folders:
        print(f"- {folder['name']}: {folder['folder_path']}")
    
    # 开始处理视频
    print("\n开始批量处理视频...")
    start_time = time.time()
    
    # 使用背景音乐
    bgm_path = "D:/BGM/轻松背景音乐.mp3"
    if not os.path.exists(bgm_path):
        print(f"背景音乐文件不存在: {bgm_path}")
        bgm_path = None
    
    # 处理视频
    outputs, error = vp.process_batch(
        material_folders=test_folders,
        output_dir=output_dir,
        count=2,  # 每个场景生成2个视频
        bgm_path=bgm_path
    )
    
    # 处理完成
    elapsed = time.time() - start_time
    print(f"\n处理完成，耗时: {elapsed:.2f}秒")
    
    # 检查结果
    if error:
        print(f"处理过程中出错: {error}")
    
    print("生成的视频文件:")
    if outputs:
        for i, output_file in enumerate(outputs):
            file_size = os.path.getsize(output_file) / (1024 * 1024)  # 转换为MB
            print(f"  {i+1}. {os.path.basename(output_file)}, 大小: {file_size:.2f}MB")
            
            # 检查文件是否有效
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                print(f"    文件有效 ✓")
            else:
                print(f"    文件无效 ✗")
    else:
        print("  未生成任何视频文件")
    
    print("\n测试完成")

if __name__ == "__main__":
    main() 