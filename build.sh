#!/bin/bash
# ============================================
# DM SQL优化分析工具 - Linux/macOS打包脚本
# ============================================

set -e

echo "============================================"
echo " DM SQL优化分析工具 - 打包脚本"
echo "============================================"
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到Python3"
    exit 1
fi

# 检查PyInstaller
if ! pip show pyinstaller &> /dev/null; then
    echo "[提示] 正在安装PyInstaller..."
    pip install pyinstaller
fi

# 检查依赖
echo "[1/4] 检查依赖..."
pip install -r requirements.txt
echo ""

# 清理旧构建
echo "[2/4] 清理旧构建..."
rm -rf build dist
echo ""

# 执行打包
echo "[3/4] 开始打包..."
pyinstaller dm_sql_optimizer.spec --noconfirm
echo ""

# 复制配置文件
echo "[4/4] 复制配置文件..."
if [ -d dist ]; then
    cp db_config.ini.template dist/db_config.ini
    cp README.md dist/
fi

echo ""
echo "============================================"
echo " 打包完成!"
echo " 输出目录: dist/"
echo "============================================"
echo ""
echo " 使用方法:"
echo " 1. 将dist/目录下所有文件复制到目标机器"
echo " 2. 编辑db_config.ini填写DM数据库连接信息"
echo " 3. 运行 ./DM_SQL_Optimizer"
echo " 4. 目标机器无需安装Python"
echo " 5. 需要安装DM客户端(提供libdmdpi.so等驱动库)"
echo ""
