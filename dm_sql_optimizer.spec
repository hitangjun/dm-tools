# -*- mode: python ; coding: utf-8 -*-
"""
DM SQL优化分析工具 - PyInstaller打包配置

使用方法:
    pyinstaller dm_sql_optimizer.spec

注意事项:
    1. 需要安装PyInstaller: pip install pyinstaller
    2. 需要安装项目依赖: pip install -r requirements.txt
    3. Win7兼容性: 使用Python 3.10 + PySide6 6.4.x (Qt6 6.5+不支持Win7)
    4. dmPython需要DM客户端库(dmdpi.dll/libdmdpi.so)，需单独安装DM客户端
"""

import sys
import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 包含配置文件模板
        ('db_config.ini.template', '.'),
    ],
    hiddenimports=[
        # 确保PySide6模块被正确打包
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        # SQL解析库
        'sqlparse',
        'sqlparse.sql',
        'sqlparse.tokens',
        'sqlparse.keywords',
        # dmPython (可选，运行时动态导入)
        # 'dmPython',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除不需要的大模块
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'PyQt5',
        'PyQt6',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DM_SQL_Optimizer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    # 使用windowed模式，不显示控制台窗口
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # 图标(如果有)
    # icon='icon.ico',
)
