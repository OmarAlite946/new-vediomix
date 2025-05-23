import re
import os

def update_file(filepath):
    print(f"处理文件: {filepath}")
    
    # 读取文件内容
    with open(filepath, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # 计数器
    count = 0
    
    # 更通用的模式，使用非贪婪匹配和捕获组
    pattern = r'self\.user_settings\.set_setting\(([^)]+)\)'
    
    # 定义替换函数
    def replace_function(match):
        nonlocal count
        count += 1
        # 获取匹配的参数部分
        args = match.group(1)
        # 构造新的函数调用
        return f'self.user_settings.update_setting_in_memory({args})'
    
    # 执行替换
    updated = re.sub(pattern, replace_function, content)
    
    # 写入文件
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(updated)
    
    print(f"更新完成！替换了 {count} 处 set_setting 调用。")

# 执行替换
update_file('src/ui/main_window.py') 