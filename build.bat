@echo off
REM ============================================
REM DM SQL优化分析工具 - Windows打包脚本
REM ============================================
REM
REM 使用前提:
REM   1. 已安装 Python 3.10 (Win7兼容) 或 3.11+ (Win10/11)
REM   2. 已安装项目依赖: pip install -r requirements.txt
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
echo [1/4] 检查依赖...
pip install -r requirements.txt
echo.

REM 清理旧构建
echo [2/4] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.

REM 执行打包
echo [3/4] 开始打包(可能需要几分钟)...
pyinstaller dm_sql_optimizer.spec --noconfirm
echo.

REM 复制配置文件
echo [4/4] 复制配置文件...
if exist dist (
    copy db_config.ini.template dist\db_config.ini >nul 2>&1
    copy README.md dist\ >nul 2>&1
    copy docs\design.md dist\docs\ >nul 2>&1
)

echo.
echo ============================================
echo  打包完成!
echo  输出目录: dist\
echo  可执行文件: dist\DM_SQL_Optimizer.exe
echo ============================================
echo.
echo  使用方法:
echo  1. 将dist\目录下所有文件复制到目标机器
echo  2. 编辑db_config.ini填写DM数据库连接信息
echo  3. 运行DM_SQL_Optimizer.exe
echo  4. 目标机器无需安装Python
echo  5. Win7需要安装VC++运行库(vcredist_x64.exe)
echo  6. 需要安装DM客户端(提供dmdpi.dll等驱动库)
echo.
pause
