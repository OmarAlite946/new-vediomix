# 批处理模板参数记忆和排队处理功能修复说明

本次修复解决了两个主要功能问题：

1. **批处理模板参数记忆功能**：每个模板的信息现在可以单独记忆，下次打开时会保持上次设置的参数
2. **排队处理勾选模板功能**：现在可以随机勾选需要的模板，系统能够正常计算并按顺序处理这些模板

## 已完成的修复工作

1. 从旧版本（705374a98e）中复制了`batch_window.py`文件
2. 修复了`UserSettings`类初始化问题，确保正确加载默认设置
3. 清理并备份了旧的设置缓存文件
4. 创建了备份和修复脚本，便于未来使用

## 如何使用修复后的功能

1. 批处理模式下创建多个模板标签页
2. 为每个模板设置不同的参数（输入文件夹、转场效果、水印等）
3. 勾选需要处理的模板（可以随机选择，不必全选）
4. 点击"开始批量处理"按钮
5. 关闭程序后再次打开，您之前的所有模板和设置都会被保留

## 如果功能再次失效

如果将来软件更新后这些功能再次失效，可以使用以下两种方式恢复：

1. 运行`fix_memory_functions.py`脚本，它会自动检查并修复问题
2. 或者运行`memory_backup/restore_memory_functions.py`脚本，它会直接恢复最近备份的功能文件

## 注意事项

- 程序关闭时会自动保存所有模板的状态和参数
- 如果添加了新模板并设置了参数，建议正常关闭程序以确保设置被保存
- 修改设置后请完成正常的关闭操作，避免强制终止程序导致设置丢失

如有任何问题，请重新运行修复脚本。 