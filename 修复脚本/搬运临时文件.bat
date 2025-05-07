@echo off
echo 正在搬运临时文件，请稍等...
echo 这可能需要一些时间，取决于文件大小和数量。

:: 确保目标文件夹存在
if not exist "D:\Windows_Temp" mkdir "D:\Windows_Temp"

:: 复制所有文件和文件夹
xcopy "D:\视频混剪工具\temp\*" "D:\Windows_Temp\" /E /H /C /I /Y

echo.
echo 临时文件已成功搬运！
echo 原始文件保留在 D:\视频混剪工具\temp
echo 复制后的文件位于 D:\Windows_Temp
echo.
echo 新的临时文件会自动存放在 D:\Windows_Temp
echo.
pause 