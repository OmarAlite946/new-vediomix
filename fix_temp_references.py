#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
修复临时目录引用脚本
用于扫描并修复项目中所有硬编码的temp目录引用
将它们替换为使用系统临时目录
"""

import os
import re
import sys
from pathlib import Path
import tempfile
import logging

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 需要替换的模式和替换内容
PATTERNS = [
    # 硬编码的临时目录创建
    (r'temp_dir\s*=\s*Path\(["\']temp["\']\)', 'temp_dir = get_system_temp_dir()'),
    (r'TEMP_DIR\s*=\s*Path\(["\']temp["\']\)', 'TEMP_DIR = get_system_temp_dir()'),
    # 硬编码的临时目录字符串
    (r'["\']temp/([^"\']+)["\']', r'os.path.join(get_system_temp_dir(), "\1")'),
    (r'["\'](temp\\[^"\']+)["\']', r'os.path.join(get_system_temp_dir(), "\1")'),
]

# 需要添加的系统临时目录获取函数
TEMP_DIR_FUNCTION = '''
# 获取系统临时目录
def get_system_temp_dir():
    """获取系统临时目录，优先使用非C盘路径"""
    # 优先尝试使用D盘
    d_drive_path = "D:\\\\VideoMixTool_Temp"
    if os.path.exists("D:\\\\") or os.access("D:\\\\", os.W_OK):
        try:
            os.makedirs(d_drive_path, exist_ok=True)
            return Path(d_drive_path)
        except Exception as e:
            pass
    
    # 其次尝试使用环境变量中的临时目录
    temp_dir = os.environ.get("TEMP") or os.environ.get("TMP")
    if temp_dir and os.path.exists(temp_dir):
        # 检查是否在C盘
        if temp_dir.lower().startswith("c:"):
            # 尝试查找其他可用的磁盘
            for drive in ["D:", "E:", "F:", "G:"]:
                try:
                    if os.path.exists(f"{drive}\\\\"):
                        alt_path = f"{drive}\\\\VideoMixTool_Temp"
                        os.makedirs(alt_path, exist_ok=True)
                        return Path(alt_path)
                except Exception:
                    continue
        else:
            # 不在C盘，可以直接使用
            temp_path = os.path.join(temp_dir, "VideoMixTool")
            os.makedirs(temp_path, exist_ok=True)
            return Path(temp_path)
    
    # 最后使用本地temp目录作为备选
    local_temp = Path("temp")
    local_temp.mkdir(exist_ok=True)
    return local_temp
'''

# 检查是否需要导入的模块
IMPORTS_NEEDED = [
    ('os', 'import os'),
    ('Path', 'from pathlib import Path'),
]

def check_and_add_imports(content):
    """检查并添加需要的导入语句"""
    modified = False
    
    for module, import_stmt in IMPORTS_NEEDED:
        # 检查模块是否已经导入
        if module not in content or import_stmt not in content:
            # 查找导入语句块
            import_section_end = 0
            for match in re.finditer(r'^import .*$|^from .* import .*$', content, re.MULTILINE):
                import_section_end = max(import_section_end, match.end())
            
            # 如果找到导入块，在其后添加导入语句；否则在文件开头添加
            if import_section_end > 0:
                content = content[:import_section_end] + '\n' + import_stmt + content[import_section_end:]
            else:
                content = import_stmt + '\n' + content
            
            modified = True
    
    return content, modified

def add_temp_dir_function(content):
    """添加获取系统临时目录的函数"""
    # 检查函数是否已存在
    if 'def get_system_temp_dir(' in content:
        return content, False
    
    # 查找合适的位置添加函数
    # 尝试在导入语句后面添加
    import_section_end = 0
    for match in re.finditer(r'^import .*$|^from .* import .*$', content, re.MULTILINE):
        import_section_end = max(import_section_end, match.end())
    
    if import_section_end > 0:
        return content[:import_section_end] + '\n' + TEMP_DIR_FUNCTION + content[import_section_end:], True
    
    # 如果没找到导入语句，在文件开头添加
    return TEMP_DIR_FUNCTION + content, True

def fix_file(file_path):
    """修复单个文件中的临时目录引用"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        modified = False
        
        # 应用所有替换模式
        for pattern, replacement in PATTERNS:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True
        
        # 如果内容被修改，添加所需的导入和函数
        if modified:
            content, imports_modified = check_and_add_imports(content)
            content, function_added = add_temp_dir_function(content)
            
            # 保存修改后的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"已修复文件: {file_path}")
            return True
        
        return False
    
    except Exception as e:
        logger.error(f"处理文件 {file_path} 时出错: {str(e)}")
        return False

def scan_and_fix_directory(directory='.'):
    """扫描并修复目录中的所有Python文件"""
    fixed_count = 0
    error_count = 0
    
    for root, dirs, files in os.walk(directory):
        # 跳过 .git 目录
        if '.git' in dirs:
            dirs.remove('.git')
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    if fix_file(file_path):
                        fixed_count += 1
                except Exception as e:
                    logger.error(f"修复文件 {file_path} 时出错: {str(e)}")
                    error_count += 1
    
    return fixed_count, error_count

if __name__ == "__main__":
    print("===== 开始修复临时目录引用 =====")
    
    # 检查输入的目录参数
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = '.'
    
    fixed_count, error_count = scan_and_fix_directory(directory)
    
    print(f"\n修复完成! 已修复 {fixed_count} 个文件，遇到 {error_count} 个错误。")
    print("所有硬编码的temp目录引用已修改为使用系统临时目录。")
    print("请重新运行'清理旧临时文件.bat'脚本来清理临时文件。") 