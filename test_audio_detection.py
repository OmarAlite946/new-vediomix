import os
import sys
sys.path.append('.')
from src.core.video_processor import VideoProcessor
from src.utils.logger import get_logger

logger = get_logger()

def main():
    """测试音频文件检测和路径处理逻辑"""
    print("开始测试音频文件检测和路径处理逻辑")
    
    # 初始化VideoProcessor
    vp = VideoProcessor({
        'temp_dir': 'temp',
        'ffmpeg_path': 'D:/ffmpeg_compat/ffmpeg.exe',
        'default_audio_duration': 10.0,
        'clean_temp_files': False  # 不清理临时文件，方便查看结果
    })
    
    print("VideoProcessor初始化成功")
    
    # 测试文件夹路径
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
    
    # 调用扫描方法
    print("\n开始扫描材料文件夹...")
    result = vp._scan_material_folders(test_folders)
    
    # 打印结果
    print("\n扫描结果:")
    for folder_name, folder_data in result.items():
        print(f"\n场景: {folder_name}")
        print(f"路径: {folder_data.get('folder_path')}")
        
        videos = folder_data.get('videos', [])
        print(f"视频数量: {len(videos)}")
        if videos:
            print("示例视频:")
            for i, video in enumerate(videos[:3]):  # 只打印前3个
                print(f"  {i+1}. {os.path.basename(video['path'])}, 时长: {video.get('duration', 0):.2f}秒")
            if len(videos) > 3:
                print(f"  ... 以及其他 {len(videos) - 3} 个视频")
        
        audios = folder_data.get('audios', [])
        print(f"音频数量: {len(audios)}")
        if audios:
            print("音频文件:")
            for i, audio in enumerate(audios):
                print(f"  {i+1}. {os.path.basename(audio['path'])}, 时长: {audio.get('duration', 0):.2f}秒")
        else:
            print("  未找到音频文件!")
    
    print("\n测试完成")

if __name__ == "__main__":
    main() 