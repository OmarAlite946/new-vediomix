#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re

def modify_audio_selection():
    # 文件路径
    file_path = 'src/core/video_processor.py'
    
    # 确保文件存在
    if not os.path.exists(file_path):
        print(f"错误: 文件 {file_path} 不存在")
        return False
        
    # 读取文件内容
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return False
        
    # 定义要替换的模式（选择第一个配音的代码块）
    old_pattern = r'# 选择第一个配音\s+audio_info = audios\[0\]'
    
    # 定义替换内容（随机选择配音的逻辑）
    new_code = """# 随机选择一个配音
                        import random
                        if len(audios) > 1:
                            audio_info = random.choice(audios)
                            logger.info(f"从{len(audios)}个可用配音中随机选择")
                        else:
                            audio_info = audios[0]"""
    
    # 执行替换
    new_content = re.sub(old_pattern, new_code, content)
    
    # 检查是否发生了变化
    if new_content == content:
        print("未找到需要修改的代码块，请检查文件内容或匹配模式")
        return False
    
    # 创建备份
    backup_path = file_path + '.bak'
    try:
        with open(backup_path, 'w', encoding='utf-8') as file:
            file.write(content)
        print(f"已创建备份: {backup_path}")
    except Exception as e:
        print(f"创建备份时出错: {str(e)}")
        # 继续执行，即使备份失败
    
    # 写回修改后的内容
    try:
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(new_content)
        print(f"成功修改文件: {file_path}")
        print("音频选择逻辑已从'选择第一个'更改为'随机选择'")
        return True
    except Exception as e:
        print(f"写入文件时出错: {str(e)}")
        return False

if __name__ == "__main__":
    result = modify_audio_selection()
    if result:
        print("修改成功完成！")
    else:
        print("修改失败，请检查错误信息") 