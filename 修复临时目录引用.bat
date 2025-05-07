@echo off
echo 正在修复临时目录引用问题...
echo 这将使所有临时文件存放在系统临时目录，而不是项目目录中的temp文件夹。

rem 确保当前目录是项目根目录
cd /d "%~dp0"

echo.
echo 第1步：修复代码中的临时目录引用
python fix_temp_references.py

echo.
echo 第2步：清理当前的临时文件
python clean_large_files.py cleantemp

echo.
echo 修复完成！现在所有临时文件将存放在系统临时目录: %TEMP%\VideoMixTool
echo 这有助于减少项目目录占用的空间。
echo.
pause 