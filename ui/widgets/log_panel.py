"""
控制台日志输出面板
"""
import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor


class LogPanel(QWidget):
    """控制台日志输出面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # 顶部工具栏
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(5, 2, 5, 2)

        title_label = QLabel("运行日志输出")
        title_label.setStyleSheet("font-weight: bold; color: #475569;")
        tb_layout.addWidget(title_label)
        tb_layout.addStretch()

        self.btn_clear = QPushButton("清除日志")
        self.btn_clear.setStyleSheet("""
            QPushButton {
                padding: 2px 10px;
                border: 1px solid #cbd5e1;
                background-color: #f8fafc;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        self.btn_clear.clicked.connect(self.clear_logs)
        tb_layout.addWidget(self.btn_clear)

        self.btn_save = QPushButton("导出...")
        self.btn_save.setStyleSheet("""
            QPushButton {
                padding: 2px 10px;
                border: 1px solid #cbd5e1;
                background-color: #f8fafc;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f1f5f9;
            }
        """)
        self.btn_save.clicked.connect(self.save_logs)
        tb_layout.addWidget(self.btn_save)

        layout.addLayout(tb_layout)

        # 日志文本区 (采用经典暗色护眼主题，更显专业)
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setFont(QFont("Consolas", 10))
        self.log_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                border: 1px solid #cbd5e1;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        layout.addWidget(self.log_edit)

    def append_log(self, text, level="INFO"):
        """追加日志，自动加上时间戳"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # 针对不同等级使用不同的高亮颜色标识
        if level.upper() == "ERROR":
            colored_text = f"[{timestamp}] [ERROR] {text}"
            # 在暗色背景下红色报错
            self.log_edit.appendHtml(f'<span style="color: #ef4444;">{colored_text}</span>')
        elif level.upper() == "WARNING":
            colored_text = f"[{timestamp}] [WARN]  {text}"
            self.log_edit.appendHtml(f'<span style="color: #f59e0b;">{colored_text}</span>')
        elif level.upper() == "SUCCESS":
            colored_text = f"[{timestamp}] [OK]    {text}"
            self.log_edit.appendHtml(f'<span style="color: #10b981;">{colored_text}</span>')
        else:
            colored_text = f"[{timestamp}] [INFO]  {text}"
            self.log_edit.appendPlainText(colored_text)
            
        # 滚动到最底部
        self.log_edit.moveCursor(QTextCursor.End)

    def clear_logs(self):
        """清空日志"""
        self.log_edit.clear()

    def save_logs(self):
        """保存日志到文件"""
        path, _ = QFileDialog.getSaveFileName(
            self, "导出运行日志", "optimizer_run.log", "日志文件 (*.log);;文本文件 (*.txt);;所有文件 (*.*)"
        )
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(self.log_edit.toPlainText())
                QMessageBox.information(self, "成功", f"日志已成功保存至:\n{path}")
            except Exception as e:
                QMessageBox.warning(self, "导出失败", f"无法写入日志文件:\n{e}")
