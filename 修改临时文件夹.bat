 @echo off
echo 正在修改系统环境变量...
setx TEMP "D:\Windows_Temp" /M
setx TMP "D:\Windows_Temp" /M
echo.
echo 临时文件夹已修改为: D:\Windows_Temp
echo.
echo 请重启计算机以使所有程序能够使用新的临时文件夹路径。
pause
