import re

# 读取原始文件
with open('src/core/video_processor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 修复编码问题的模式
content = content.replace('视�?', '视频')
content = content.replace('音�?', '音频')
content = content.replace('合�?', '合并')
content = content.replace('单视频模�?', '单视频模式')
content = content.replace('没有足够长的视频，使用所有视�?', '没有足够长的视频，使用所有视频')
content = content.replace('为场�?', '为场景')
content = content.replace('没有视频文件，跳�?', '没有视频文件，跳过')
content = content.replace('场景视频列�?', '场景视频列表')
content = content.replace('没有生成任何场景视频，处理终�?', '没有生成任何场景视频，处理终止')
content = content.replace('阶段3: 最终合并阶�?', '阶段3: 最终合并阶段')
content = content.replace('拼接所有场景视�?', '拼接所有场景视频')
content = content.replace('没有足够长的视频，使用所有视�?', '没有足够长的视频，使用所有视频')
content = content.replace('开始合�?', '开始合并')
content = content.replace('个场景视�?', '个场景视频')
content = content.replace('处理路径中的单引�?', '处理路径中的单引号')
content = content.replace('没有背景音乐，直接输�?', '没有背景音乐，直接输出')
content = content.replace('如果背景音乐处理失败，尝试使用原始合并视�?', '如果背景音乐处理失败，尝试使用原始合并视频')
content = content.replace('配音时长 ', '配音时长 ')
content = content.replace('：auto', ': auto')

# 写回文件
with open('src/core/video_processor.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("编码问题修复完成！") 