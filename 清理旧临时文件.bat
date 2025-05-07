@echo off
title 清理旧临时文件
echo ===== 清理旧临时文件 =====
echo.

:: 检查是否有管理员权限
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo 需要管理员权限来清理某些目录
    echo 请求 UAC 提升权限...
    goto UACPrompt
) else (
    goto gotAdmin
)

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"

    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" (
        del "%temp%\getadmin.vbs"
    )
    cd /d "%~dp0"

echo 此脚本将清理以下位置的临时文件:
echo - 当前目录中的temp文件夹
echo - 系统临时目录中的VideoMixTool文件夹
echo.
echo 按任意键开始清理...
pause > nul

echo.
echo 开始清理临时文件...

:: 创建清理脚本
echo import os, shutil > temp_clean.py
echo from pathlib import Path >> temp_clean.py
echo. >> temp_clean.py
echo # 要清理的目录列表 >> temp_clean.py
echo dirs_to_clean = [ >> temp_clean.py
echo     "temp", >> temp_clean.py
echo     os.path.join(os.environ.get("TEMP", ""), "VideoMixTool"), >> temp_clean.py
echo ] >> temp_clean.py
echo. >> temp_clean.py
echo cleaned_count = 0 >> temp_clean.py
echo error_count = 0 >> temp_clean.py
echo. >> temp_clean.py
echo print("开始清理旧临时文件...") >> temp_clean.py
echo. >> temp_clean.py
echo for dir_path in dirs_to_clean: >> temp_clean.py
echo     if os.path.exists(dir_path) and os.path.isdir(dir_path): >> temp_clean.py
echo         try: >> temp_clean.py
echo             print(f"清理目录: {dir_path}") >> temp_clean.py
echo             # 尝试删除整个目录 >> temp_clean.py
echo             before_size = sum(f.stat().st_size for f in Path(dir_path).rglob('*') if f.is_file()) >> temp_clean.py
echo             file_count = sum(1 for _ in Path(dir_path).rglob('*') if _.is_file()) >> temp_clean.py
echo             shutil.rmtree(dir_path, ignore_errors=True) >> temp_clean.py
echo             # 确保目录存在，以备后用 >> temp_clean.py
echo             os.makedirs(dir_path, exist_ok=True) >> temp_clean.py
echo             cleaned_count += 1 >> temp_clean.py
echo             before_size_mb = before_size / (1024 * 1024) >> temp_clean.py
echo             print(f"已清理: {file_count} 个文件，约 {before_size_mb:.2f} MB") >> temp_clean.py
echo         except Exception as e: >> temp_clean.py
echo             print(f"清理目录 {dir_path} 时出错: {e}") >> temp_clean.py
echo             error_count += 1 >> temp_clean.py
echo. >> temp_clean.py
echo print(f"清理完成! 已清理 {cleaned_count} 个目录，遇到 {error_count} 个错误。") >> temp_clean.py
echo if error_count > 0: >> temp_clean.py
echo     print("有些文件可能无法删除，请确保没有程序正在使用这些文件。") >> temp_clean.py
echo. >> temp_clean.py
echo # 确保D盘临时目录存在 >> temp_clean.py
echo d_drive_temp = "D:\\VideoMixTool_Temp" >> temp_clean.py
echo try: >> temp_clean.py
echo     os.makedirs(d_drive_temp, exist_ok=True) >> temp_clean.py
echo     print(f"已确保D盘临时目录存在: {d_drive_temp}") >> temp_clean.py
echo except Exception as e: >> temp_clean.py
echo     print(f"创建D盘临时目录时出错: {e}") >> temp_clean.py

:: 运行清理脚本
python temp_clean.py
:: 删除临时脚本
del temp_clean.py

echo.
echo ===== 清理操作已完成! =====
echo.
echo 如果某些文件无法删除，可能是因为:
echo 1. 有程序正在使用这些文件
echo 2. 文件被锁定或需要特殊权限
echo.
echo 请尝试关闭所有相关程序后再运行此脚本。
echo.
pause 