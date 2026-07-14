#!/usr/bin/env python3
"""
DM数据库SQL优化分析工具 - 主入口

使用方法:
    pip install -r requirements.txt
    python main.py
"""
import sys
from pathlib import Path

# 将项目根目录加入sys.path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("DM SQL优化分析工具")

    # 设置全局字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)

    # 设置应用样式
    app.setStyleSheet("""
        QMainWindow { background-color: #f8fafc; }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            padding: 5px 15px;
            border-radius: 4px;
            border: 1px solid #cbd5e1;
            background-color: #f1f5f9;
        }
        QPushButton:hover {
            background-color: #e2e8f0;
        }
        QTreeWidget {
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            alternate-background-color: #f8fafc;
        }
        QTabWidget::pane {
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        }
        QTextEdit, QPlainTextEdit {
            border: 1px solid #e2e8f0;
            border-radius: 4px;
        }
    """)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
