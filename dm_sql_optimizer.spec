# -*- mode: python ; coding: utf-8 -*-
"""
DM SQL优化分析工具 - PyInstaller打包配置

使用方法:
    pyinstaller dm_sql_optimizer.spec --noconfirm

注意事项:
    1. 需要安装PyInstaller: pip install pyinstaller
    2. 需要安装项目依赖: pip install -r requirements.txt
    3. dmPython用try/except动态导入，必须在hiddenimports中显式声明
    4. dmdpi.dll是DM客户端驱动库，放入项目根目录后会自动打包
       如果项目根目录没有dmdpi.dll，打包时不报错，但目标机器需要安装DM客户端
    5. Win7兼容性: 使用Python 3.10 + PySide6 6.4.x
"""

import os

block_cipher = None

# 检查dmdpi.dll是否存在于项目目录，存在则打包进去
extra_datas = [('db_config.ini.template', '.')]
if os.path.exists('dmdpi.dll'):
    extra_datas.append(('dmdpi.dll', '.'))
    print("[INFO] dmdpi.dll found, will be included in the package")
else:
    print("[WARNING] dmdpi.dll not found in project directory")
    print("[WARNING] Target machines will need DM client installed")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=extra_datas,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'sqlparse',
        'sqlparse.sql',
        'sqlparse.tokens',
        'sqlparse.keywords',
        # dmPython用try/except导入，PyInstaller无法自动检测，必须显式声明
        'dmPython',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
