@echo off
title 全面修复临时文件问题
echo ===== 全面修复临时文件问题 =====
echo.

:: 检查是否有管理员权限
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo 需要管理员权限来运行此脚本
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

echo 这个脚本将进行以下操作:
echo 1. 设置D盘临时目录
echo 2. 阻止原位置创建临时文件
echo 3. 修复代码中的临时目录引用
echo 4. 清理旧临时文件
echo.
echo 按任意键开始...
pause > nul

:: 第一步：设置D盘临时目录
echo.
echo [1/4] 设置D盘临时目录...
echo.
if exist "set_d_drive_temp.py" (
    python set_d_drive_temp.py
) else (
    echo 错误: 找不到 set_d_drive_temp.py 文件!
    goto Error
)

:: 第二步：阻止原位置创建临时文件
echo.
echo [2/4] 阻止原位置创建临时文件...
echo.
if exist "block_temp_creation.py" (
    python block_temp_creation.py
) else (
    echo 错误: 找不到 block_temp_creation.py 文件!
    goto Error
)

:: 第三步：修复代码中的临时目录引用
echo.
echo [3/4] 修复代码中的临时目录引用...
echo.
if exist "fix_temp_references.py" (
    python fix_temp_references.py
) else (
    echo 错误: 找不到 fix_temp_references.py 文件!
    goto Error
)

:: 第四步：清理旧临时文件
echo.
echo [4/4] 清理旧临时文件...
echo.

:: 创建临时Python脚本清理旧文件
echo import os, shutil > temp_clean.py
echo from pathlib import Path >> temp_clean.py
echo. >> temp_clean.py
echo # 要清理的目录 >> temp_clean.py
echo dirs_to_clean = [ >> temp_clean.py
echo     "temp", >> temp_clean.py
echo     os.path.join(os.environ.get("TEMP", ""), "VideoMixTool"), >> temp_clean.py
echo ] >> temp_clean.py
echo. >> temp_clean.py
echo print("开始清理旧临时文件...") >> temp_clean.py
echo. >> temp_clean.py
echo for dir_path in dirs_to_clean: >> temp_clean.py
echo     if os.path.exists(dir_path) and os.path.isdir(dir_path): >> temp_clean.py
echo         try: >> temp_clean.py
echo             print(f"清理目录: {dir_path}") >> temp_clean.py
echo             # 尝试删除整个目录 >> temp_clean.py
echo             shutil.rmtree(dir_path, ignore_errors=True) >> temp_clean.py
echo             print(f"已成功清理目录: {dir_path}") >> temp_clean.py
echo         except Exception as e: >> temp_clean.py
echo             print(f"清理目录 {dir_path} 时出错: {e}") >> temp_clean.py
echo. >> temp_clean.py
echo print("清理完成!") >> temp_clean.py

:: 运行清理脚本
python temp_clean.py
:: 删除临时脚本
del temp_clean.py

:: 成功完成
echo.
echo ===== 全部操作已完成! =====
echo.
echo 临时文件问题已全面修复:
echo - D盘临时目录已设置
echo - 原位置临时文件已被阻止
echo - 代码中的临时目录引用已修复
echo - 旧临时文件已清理
echo.
echo 重要: 对于某些应用，可能需要重启电脑才能生效。
echo.
goto End

:Error
echo.
echo 执行过程中出现错误，请检查上述错误信息。
echo.

:End
pause 