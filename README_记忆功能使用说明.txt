# 视频混剪工具记忆功能使用说明

## 概述

记忆功能使软件能够在下次启动时自动恢复上次关闭前的所有设置和状态，包括：

1. 导入的文件夹路径和素材列表
2. 每个素材文件夹的拼接模式设置
3. 输出路径、编码参数、水印设置等各种参数
4. 窗口大小和位置
5. 当前活动的选项卡

## 自动记忆的内容

### 素材设置
- 上次导入的根文件夹路径
- 素材列表中的所有文件夹（路径有效时）
- 每个文件夹设置的拼接模式（单视频/多视频拼接）

### 输出设置
- 输出保存路径
- 缓存目录路径

### 视频参数
- 分辨率设置
- 比特率设置（包括原始比特率选项）
- 转场效果选择
- GPU加速选项
- 编码模式

### 水印设置
- 水印开关状态
- 水印前缀文本
- 水印大小、颜色
- 水印位置和偏移值

### 音频设置
- 配音音量
- 背景音乐音量
- 背景音乐路径
- 音频处理模式

### 界面状态
- 窗口大小和位置
- 当前活动的选项卡

## 特别说明

1. **素材记忆**: 软件会自动记住上次导入的素材文件夹和每个文件夹的拼接模式，避免每次都要重新导入

2. **路径有效性**: 如果上次记忆的路径已不存在（如移动或删除了文件夹），软件会自动跳过这些无效路径

3. **不会自动扫描**: 与之前不同，本功能仅记忆路径和设置，不会在启动时自动扫描文件夹内容，避免启动缓慢

4. **立即生效**: 所有设置的修改都会立即保存到配置文件中，即使软件意外关闭也能保留设置

## 配置文件位置

记忆功能的配置文件保存在用户主目录下的VideoMixTool文件夹中：

- Windows: C:\Users\用户名\VideoMixTool\user_settings.json

如果需要完全重置所有设置，可以在软件关闭的情况下删除此文件，软件会在下次启动时创建默认设置。

## 故障排除

1. 如果设置加载出现问题，软件会自动创建备份文件并使用默认设置

2. 如果某个导入的文件夹路径不再有效，软件会自动跳过，不会影响其他功能

3. 如果窗口位置记忆有问题导致窗口显示不全，可以尝试删除配置文件重新启动 