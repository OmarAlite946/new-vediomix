@echo off
echo 正在清理旧的临时文件夹...
cd /d "D:\视频混剪工具"
rmdir /s /q temp
mkdir temp
echo.
echo 旧的临时文件夹已清理完成！
echo 现在新的临时文件会存放在 D:\Windows_Temp
echo.
pause 