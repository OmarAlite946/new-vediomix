import re

file_path = 'src/ui/main_window.py'
with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()

# 替换单视频模式的自动保存
pattern1 = r'(self\.folder_extract_modes\[folder_path\] = "single_video".*?status_item\.set_status\("待处理"\)\n\s+self\.video_table\.setItem\(row, 5, status_item\)\n\s+)\n\s+# 保存用户设置\n\s+self\._save_user_settings\(\)'
replacement1 = r'\1\n            # 移除自动保存设置代码\n            # self._save_user_settings()\n            \n            QMessageBox.information(self, "设置抽取模式", "已设置为单视频模式，您可以点击\"保存当前所有设置\"按钮保存这些设置")'

modified_content = re.sub(pattern1, replacement1, content, flags=re.DOTALL)

# 替换多视频拼接模式的自动保存
pattern2 = r'(self\.folder_extract_modes\[folder_path\] = "multi_video".*?status_item\.set_status\("待处理"\)\n\s+self\.video_table\.setItem\(row, 5, status_item\)\n\s+)\n\s+# 保存用户设置\n\s+self\._save_user_settings\(\)'
replacement2 = r'\1\n            # 移除自动保存设置代码\n            # self._save_user_settings()\n            \n            QMessageBox.information(self, "设置抽取模式", "已设置为多视频拼接模式，您可以点击\"保存当前所有设置\"按钮保存这些设置")'

modified_content = re.sub(pattern2, replacement2, modified_content, flags=re.DOTALL)

# 替换重置为默认模式的自动保存
pattern3 = r'(del self\.folder_extract_modes\[folder_path\].*?status_item\.set_status\("待处理"\)\n\s+self\.video_table\.setItem\(row, 5, status_item\)\n\s+)\n\s+# 保存用户设置\n\s+self\._save_user_settings\(\)'
replacement3 = r'\1\n                # 移除自动保存设置代码\n                # self._save_user_settings()\n                \n                QMessageBox.information(self, "重置抽取模式", "已重置为默认的单视频模式，您可以点击\"保存当前所有设置\"按钮保存这些设置")'

modified_content = re.sub(pattern3, replacement3, modified_content, flags=re.DOTALL)

print(f'替换完成，正在写入文件...')
with open(file_path, 'w', encoding='utf-8') as file:
    file.write(modified_content)

print('文件更新完成！') 