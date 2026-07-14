@echo off
chcp 65001 >nul 2>&1
REM ============================================
REM DM SQL优化分析工具 - Windows打包脚本
REM ============================================
REM
REM 使用前提:
REM   1. 已安装 Python 3.10 (Win7兼容) 或 3.11+ (Win10/11)
REM   2. 已安装项目依赖: pip install PySide6 sqlparse dmPython
REM   3. 已安装 PyInstaller: pip install pyinstaller
REM
REM Win7兼容性说明:
REM   - Python 3.10 是最后支持Win7的版本
REM   - PySide6 6.4.x 是最后支持Win7的版本 (6.5+需要Win10+)
REM   - 推荐使用 Python 3.10 + PySide6==6.4.3 打包Win7版本
REM
REM ============================================

echo ============================================
echo  DM SQL优化分析工具 - 打包脚本
echo ============================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.10+
    pause
    exit /b 1
)

REM 检查PyInstaller
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装PyInstaller...
    pip install pyinstaller
)

REM 检查依赖
echo [1/5] 检查依赖...
pip install PySide6 sqlparse dmPython pyinstaller
echo.

REM 清理旧构建（完全清理，避免残留导致报错）
echo [2/5] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
REM 注意: 不删除 dm_sql_optimizer.spec —— 这是手工维护的打包配置
REM (Windows文件系统不区分大小写, 删除 DM_SQL_Optimizer.spec 会误删 dm_sql_optimizer.spec)
REM 清理__pycache__
for /d /r %%i in (__pycache__) do (
    if exist "%%i" rmdir /s /q "%%i"
)
echo 清理完成
echo.

REM 检查dmdpi.dll
echo [3/5] 检查dmdpi.dll...
if exist dmdpi.dll (
    echo [INFO] dmdpi.dll 已找到，将一起打包
) else (
    echo [WARNING] dmdpi.dll 未找到
    echo [WARNING] 目标机器需要安装DM客户端，或将dmdpi.dll手动放入dist目录
)
echo.

REM 执行打包
echo [4/5] 开始打包(可能需要几分钟)...
pyinstaller dm_sql_optimizer.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [错误] 打包失败！请检查上方错误信息
    pause
    exit /b 1
)
echo.

REM 复制配置文件
echo [5/5] 复制配置文件...
if exist dist\DM_SQL_Optimizer (
    copy db_config.ini.template dist\DM_SQL_Optimizer\db_config.ini >nul 2>&1
    copy README.md dist\DM_SQL_Optimizer\ >nul 2>&1
    if exist scripts (
        xcopy scripts dist\DM_SQL_Optimizer\scripts\ /e /i /y >nul 2>&1
    )
    echo 配置文件复制完成
)
echo.

echo ============================================
echo  打包完成!
echo ============================================
echo.
echo  输出目录: dist\DM_SQL_Optimizer\
echo  可执行文件: dist\DM_SQL_Optimizer\DM_SQL_Optimizer.exe
echo.
echo  使用方法:
echo  1. 将dist\DM_SQL_Optimizer\目录下所有文件复制到目标机器
echo  2. 编辑db_config.ini填写DM数据库连接信息
echo  3. 运行DM_SQL_Optimizer.exe
echo  4. 目标机器无需安装Python
echo  5. 如果已打包dmdpi.dll，目标机器也无需安装DM客户端
echo  6. 如果未打包dmdpi.dll，目标机器需安装DM客户端
echo  7. Win7需要安装VC++运行库(vcredist_x64.exe)
echo.
pause
