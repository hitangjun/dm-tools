# -*- mode: python ; coding: utf-8 -*-
"""
DM SQL优化分析工具 - PyInstaller打包配置

使用方法:
    pyinstaller dm_sql_optimizer.spec --noconfirm

注意事项:
    1. 需要安装PyInstaller: pip install pyinstaller
    2. 需要安装项目依赖: pip install -r requirements.txt
    3. dmPython用try/except动态导入，必须在hiddenimports中显式声明
    4. DM客户端驱动: 把 dmdpi.dll 及其传递依赖放入 dm-dll 子目录后会自动打包；
       目标机器无需安装 DM 客户端。dm-dll 目录应只含 dmdpi.dll 的依赖闭包
       (可用 pefile 解析导入表得出最小集)，避免打包无关的服务端/工具 DLL。
    5. Win7兼容性: 使用Python 3.10 + PySide6 6.4.x
"""

import os

block_cipher = None

# 收集 DM 客户端运行所需的 DLL，一并打包后目标机器无需安装 DM 客户端。
# 优先方案: dm-dll 目录 —— 该目录应存放 dmdpi.dll 及其完整传递依赖闭包
#   (可用 pefile 解析导入表得出最小集；详见项目说明)。
#   存在时打包目录下所有 .dll。
# 回退方案: 项目根目录的 dmdpi.dll —— 仅打包驱动本体，目标机器需自行安装 DM 客户端。
extra_datas = [('db_config.ini.template', '.'), ('assets/app_icon.png', 'assets')]
if os.path.isdir('dm-dll'):
    for name in sorted(os.listdir('dm-dll')):
        if name.lower().endswith('.dll'):
            extra_datas.append((os.path.join('dm-dll', name), '.'))
    print(f"[INFO] dm-dll 目录存在，打包其中 {len(extra_datas) - 1} 个 DLL")
elif os.path.exists('dmdpi.dll'):
    extra_datas.append(('dmdpi.dll', '.'))
    print("[INFO] 仅找到根目录 dmdpi.dll，目标机器需安装 DM 客户端以提供伴随 DLL")
else:
    print("[WARNING] 未找到 dmdpi.dll 及 dm-dll 目录")
    print("[WARNING] 目标机器需安装 DM 客户端")

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
    icon='assets/app_icon.ico',
)
