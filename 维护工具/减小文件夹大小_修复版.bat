@echo off
chcp 936 >nul
echo 正在准备减小"视频混剪工具"文件夹的大小...
echo.
echo 此脚本将提供以下选项:
echo 1. 清理临时文件夹 (约116MB)
echo 2. 压缩ffmpeg文件夹 (约225MB)
echo 3. 清理dist和release文件夹 (约391MB)
echo 4. 全部执行
echo 5. 退出
echo.

:menu
set /p choice=请输入您的选择 (1-5): 

if "%choice%"=="1" goto clean_temp
if "%choice%"=="2" goto compress_ffmpeg
if "%choice%"=="3" goto clean_dist
if "%choice%"=="4" goto all
if "%choice%"=="5" goto end

echo 输入无效，请重新选择。
goto menu

:clean_temp
echo.
echo 正在清理临时文件夹...
cd /d "D:\视频混剪工具"
rmdir /s /q temp
mkdir temp
echo 临时文件夹已清理完成！
pause
goto menu

:compress_ffmpeg
echo.
echo 正在准备压缩ffmpeg文件夹...
cd /d "D:\视频混剪工具"
if exist ffmpeg.zip del ffmpeg.zip
echo 创建压缩文件可能需要一些时间，请耐心等待...
powershell -command "Compress-Archive -Path 'ffmpeg' -DestinationPath 'ffmpeg.zip'"
echo.
echo ffmpeg文件夹已压缩为ffmpeg.zip。
echo 原始文件夹仍然保留，如果程序运行正常，您可以选择删除原始文件夹。
echo.
set /p del_ffmpeg=是否删除原始ffmpeg文件夹？(Y/N): 
if /i "%del_ffmpeg%"=="Y" (
    rmdir /s /q ffmpeg
    echo 原始ffmpeg文件夹已删除。
)
pause
goto menu

:clean_dist
echo.
echo 警告：dist和release文件夹可能包含重要的发布版本。
set /p confirm_dist=确定要清理这些文件夹吗？(Y/N): 
if /i not "%confirm_dist%"=="Y" goto menu

echo.
echo 正在清理dist和release文件夹...
cd /d "D:\视频混剪工具"
if exist dist.zip del dist.zip
if exist release.zip del release.zip

echo 正在备份文件夹...
powershell -command "Compress-Archive -Path 'dist' -DestinationPath 'dist.zip'"
powershell -command "Compress-Archive -Path 'release' -DestinationPath 'release.zip'"

echo 正在清空文件夹...
rmdir /s /q dist
rmdir /s /q release
mkdir dist
mkdir release

echo dist和release文件夹已清理并备份为zip文件。
pause
goto menu

:all
call :clean_temp
call :compress_ffmpeg
call :clean_dist
echo 所有操作已完成！
pause
goto menu

:end
echo 感谢使用！请检查您的文件夹大小是否已减小。
pause 