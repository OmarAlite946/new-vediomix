@echo off
title 设置临时目录到D盘
echo 正在请求管理员权限...

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

echo 开始设置临时目录到D盘...

:: 运行Python脚本
if exist "block_temp_creation.py" (
    python block_temp_creation.py
) else (
    echo 错误: 找不到 block_temp_creation.py 文件!
    echo 请确保该文件在当前目录下。
    pause
    exit /B
)

:: 如果存在set_d_drive_temp.py，也运行它
if exist "set_d_drive_temp.py" (
    echo 正在运行 set_d_drive_temp.py...
    python set_d_drive_temp.py
)

echo.
echo 操作完成!
echo 如果您没有看到任何错误，则临时目录已成功设置到D盘。
echo 对于某些应用，可能需要重启电脑才能生效。
echo.
pause 