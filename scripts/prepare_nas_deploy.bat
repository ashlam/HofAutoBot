@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

rem 生成用于 NAS 部署的干净压缩包
rem 用法：双击运行，或在 CMD 里执行 scripts\prepare_nas_deploy.bat

set "SRC=%~dp0.."
set "TMP=%TEMP%\HofAutoBot_deploy"
set "ZIP=%USERPROFILE%\Desktop\HofAutoBot_nas_deploy.zip"

echo ========================================
echo  生成 NAS 部署包
echo  源目录: %SRC%
echo  输出:   %ZIP%
echo ========================================
echo.

rem 清理临时目录
if exist "%TMP%" (
    echo [1/5] 清理临时目录...
    rmdir /s /q "%TMP%"
)

rem 复制项目到临时目录，并排除不需要的文件夹
echo [2/5] 复制项目文件（排除 .venv / drivers / logs / scripts\.wdm / __pycache__ / build / dist）...
echo 如果这步卡住，说明文件很多，请耐心等待...
echo.
robocopy "%SRC%" "%TMP%" /E /XD .venv drivers logs scripts\.wdm __pycache__ build dist /XF *.pyc *.pyo *.pid
set ROBOCOPY_RC=%ERRORLEVEL%
echo.
echo robocopy 返回码: %ROBOCOPY_RC%
if %ROBOCOPY_RC% GEQ 8 (
    echo 错误：robocopy 复制失败（返回码大于等于 8）
    pause
    exit /b 1
)

rem 删除可能存在的运行时文件
echo [3/5] 清理运行时文件...
if exist "%TMP%\hof_auto_bot*.pid" del /f /q "%TMP%\hof_auto_bot*.pid" 2> nul
if exist "%TMP%\scripts\.wdm" rmdir /s /q "%TMP%\scripts\.wdm" 2> nul

rem 打包
echo [4/5] 打包为 zip...
if exist "%ZIP%" (
    echo 删除旧的 zip 文件...
    del /f /q "%ZIP%"
)
echo 正在使用 tar 生成标准 zip（Linux 兼容的正斜杠路径）...
tar -a -c -f "%ZIP%" -C "%TMP%" .
set TAR_RC=%ERRORLEVEL%
if %TAR_RC% NEQ 0 (
    echo 错误：tar 压缩失败（返回码 %TAR_RC%）
    echo 临时目录未删除：%TMP%
    pause
    exit /b 1
)

rem 清理临时目录
echo [5/5] 清理临时目录...
rmdir /s /q "%TMP%" 2> nul

if exist "%ZIP%" (
    echo.
    echo ========================================
    echo  完成！部署包已生成：
    echo  %ZIP%
    echo ========================================
) else (
    echo.
    echo 错误：找不到生成的 zip 文件
    pause
    exit /b 1
)

echo.
echo 下一步：把这个 zip 上传到 NAS 解压，然后在 NAS 上执行：
echo   bash scripts/deploy_nas.sh --server-id 1
pause
