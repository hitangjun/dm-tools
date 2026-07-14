"""
文档信息展示组件

在每个功能面板上方显示对应的达梦官方文档内容和操作提示。
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTextEdit, QGroupBox,
    QPushButton, QHBoxLayout,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QColor


class DocInfoWidget(QGroupBox):
    """
    文档信息展示组件

    在功能面板上方显示:
    - 文档来源和链接
    - 文档核心内容
    - 操作提示
    - SQL示例(可复制)
    """

    sql_example_clicked = Signal(str)  # 点击SQL示例时发出信号

    def __init__(self, doc_snippet, parent=None):
        """
        Args:
            doc_snippet: DocSnippet对象，包含文档知识
        """
        title = f"📖 {doc_snippet.feature_name} - 文档参考"
        super().__init__(title, parent)
        self._snippet = doc_snippet
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 文档来源
        source_label = QLabel(
            f'<b>来源:</b> <a href="{self._snippet.doc_url}">'
            f'{self._snippet.doc_source}</a>'
        )
        source_label.setOpenExternalLinks(True)
        layout.addWidget(source_label)

        # 文档内容
        content_label = QLabel("文档内容:")
        content_label.setStyleSheet("font-weight: bold; color: #374151;")
        layout.addWidget(content_label)

        self.content_text = QTextEdit()
        self.content_text.setPlainText(self._snippet.doc_content)
        self.content_text.setReadOnly(True)
        self.content_text.setMaximumHeight(180)
        self.content_text.setFont(QFont("Microsoft YaHei", 9))
        self.content_text.setStyleSheet(
            "QTextEdit { background-color: #f0f9ff; "
            "border: 1px solid #bae6fd; border-radius: 4px; padding: 5px; }"
        )
        layout.addWidget(self.content_text)

        # 操作提示
        tips_label = QLabel("💡 操作提示:")
        tips_label.setStyleSheet("font-weight: bold; color: #b45309;")
        layout.addWidget(tips_label)

        self.tips_text = QTextEdit()
        self.tips_text.setPlainText(self._snippet.tips)
        self.tips_text.setReadOnly(True)
        self.tips_text.setMaximumHeight(120)
        self.tips_text.setFont(QFont("Microsoft YaHei", 9))
        self.tips_text.setStyleSheet(
            "QTextEdit { background-color: #fffbeb; "
            "border: 1px solid #fde68a; border-radius: 4px; padding: 5px; }"
        )
        layout.addWidget(self.tips_text)

        # SQL示例
        if self._snippet.sql_examples:
            sql_label = QLabel("📝 SQL示例 (点击复制到编辑器):")
            sql_label.setStyleSheet("font-weight: bold; color: #1e40af;")
            layout.addWidget(sql_label)

            for i, sql in enumerate(self._snippet.sql_examples):
                if sql.strip().startswith("--"):
                    # 注释行作为标签
                    note = QLabel(sql.strip())
                    note.setStyleSheet("color: #6b7280; font-style: italic; margin-left: 10px;")
                    layout.addWidget(note)
                else:
                    btn = QPushButton(sql[:80] + ("..." if len(sql) > 80 else ""))
                    btn.setToolTip(sql)
                    btn.setStyleSheet(
                        "QPushButton { text-align: left; background-color: #eff6ff; "
                        "border: 1px solid #bfdbfe; padding: 3px 8px; "
                        "border-radius: 3px; font-family: Consolas; }"
                        "QPushButton:hover { background-color: #dbeafe; }"
                    )
                    btn.clicked.connect(lambda checked, s=sql: self.sql_example_clicked.emit(s))
                    layout.addWidget(btn)

    def get_snippet(self):
        return self._snippet
