#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
修复脚本，用于将导入文件夹相关的代码恢复到原始状态
"""

import os
import re

def fix_main_window_py():
    """修复main_window.py文件中的代码问题"""
    # 读取当前文件内容
    with open('src/ui/main_window.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 备份原文件
    with open('src/ui/main_window.py.bak2', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # 1. 移除新添加的_process_folder_shortcuts方法
    process_folder_shortcuts_pattern = re.compile(
        r'# 添加一个新的方法来处理文件夹快捷方式\s*'
        r'def _process_folder_shortcuts.*?'
        r'# 修改 _update_media_counts 方法',
        re.DOTALL
    )
    
    content = process_folder_shortcuts_pattern.sub(
        '# 修改 _update_media_counts 方法',
        content
    )
    
    # 2. 还原_update_media_counts方法，不使用_process_folder_shortcuts
    update_media_counts_pattern = re.compile(
        r'# 修改 _update_media_counts 方法.*?'
        r'def _update_media_counts.*?'
        r'# 已移除重复的_import_material_folder方法实现',
        re.DOTALL
    )
    
    original_update_media_counts = """# 修改 _update_media_counts 方法
    def _update_media_counts(self):
        \"\"\"更新素材表格中每一行的视频和配音数量\"\"\"
        from src.utils.file_utils import list_media_files
        logger.info("正在更新素材数量...")
        
        # 设置鼠标等待状态
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        try:
            for row in range(self.video_table.rowCount()):
                folder_path = self.video_table.item(row, 2).text()
                if not folder_path or not os.path.exists(folder_path):
                    continue
                
                # 检查"视频"子文件夹是否存在
                video_path = os.path.join(folder_path, "视频")
                video_count = 0
                
                if os.path.exists(video_path) and os.path.isdir(video_path):
                    try:
                        media = list_media_files(video_path, recursive=True)
                        video_count = len(media['videos'])
                        logger.info(f"更新素材数量: 找到视频 {video_count} 个，路径: {video_path}")
                    except Exception as e:
                        logger.error(f"扫描视频文件夹失败: {str(e)}")
                
                # 检查"配音"子文件夹是否存在
                audio_path = os.path.join(folder_path, "配音")
                audio_count = 0
                
                if os.path.exists(audio_path) and os.path.isdir(audio_path):
                    try:
                        media = list_media_files(audio_path, recursive=True)
                        audio_count = len(media['audios'])
                        logger.info(f"更新素材数量: 找到配音 {audio_count} 个，路径: {audio_path}")
                    except Exception as e:
                        logger.error(f"扫描音频文件夹失败: {str(e)}")
                
                # 更新表格项
                self.video_table.setItem(row, 3, QTableWidgetItem(str(video_count)))
                self.video_table.setItem(row, 4, QTableWidgetItem(str(audio_count)))
            
            logger.info("素材数量更新完成")
        except Exception as e:
            logger.error(f"更新素材数量时出错: {str(e)}")
        finally:
            # 恢复鼠标指针
            QApplication.restoreOverrideCursor()

    
    # 已移除重复的_import_material_folder方法实现"""
    
    content = update_media_counts_pattern.sub(original_update_media_counts, content)
    
    # 3. 移除showEvent方法
    showevent_pattern = re.compile(
        r'# 添加窗口显示事件处理\s*'
        r'def showEvent.*?'
        r'def force_progress_update',
        re.DOTALL
    )
    
    content = showevent_pattern.sub('def force_progress_update', content)
    
    # 保存修改后的文件
    with open('src/ui/main_window_fixed2.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("修复完成！新文件保存为: src/ui/main_window_fixed2.py")
    print("请将新文件内容复制到main_window.py进行替换")

if __name__ == "__main__":
    fix_main_window_py() 