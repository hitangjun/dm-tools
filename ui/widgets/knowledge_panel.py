"""
知识库面板 - 浏览所有达梦官方文档知识
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QHeaderView, QPushButton,
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, Signal

from core.doc_knowledge import DocKnowledgeBase
from ui.widgets.doc_info_widget import DocInfoWidget


class KnowledgePanel(QWidget):
    """知识库浏览面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kb = DocKnowledgeBase()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel("达梦官方文档知识库")
        title.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 5px;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧: 功能列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["功能", "文档来源"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)

        for snippet in self.kb.get_all():
            item = QTreeWidgetItem([snippet.feature_name, snippet.doc_source])
            item.setData(0, Qt.UserRole, snippet.feature_id)
            self.tree.addTopLevelItem(item)

        self.tree.currentItemChanged.connect(self._on_selected)
        splitter.addWidget(self.tree)

        # 右侧: 文档详情
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setFont(QFont("Microsoft YaHei", 10))
        splitter.addWidget(self.detail_text)

        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

    def _on_selected(self, current, previous):
        if not current:
            return
        feature_id = current.data(0, Qt.UserRole)
        snippet = self.kb.get(feature_id)
        if not snippet:
            return

        html = "<html><body style='font-family: Microsoft YaHei; font-size: 10pt; line-height: 1.6;'>"
        html += f"<h2>{snippet.feature_name}</h2>"
        html += f"<p><b>文档来源:</b> <a href='{snippet.doc_url}'>{snippet.doc_source}</a></p>"

        html += "<h3>📄 文档内容</h3>"
        html += f"<div style='background:#f0f9ff; border:1px solid #bae6fd; border-radius:5px; padding:10px;'>"
        html += f"<pre style='white-space:pre-wrap;'>{snippet.doc_content}</pre>"
        html += "</div>"

        html += "<h3>💡 操作提示</h3>"
        html += f"<div style='background:#fffbeb; border:1px solid #fde68a; border-radius:5px; padding:10px;'>"
        html += f"<pre style='white-space:pre-wrap;'>{snippet.tips}</pre>"
        html += "</div>"

        if snippet.sql_examples:
            html += "<h3>📝 SQL示例</h3>"
            html += "<div style='background:#1e1b4b; color:#a5f3fc; border-radius:5px; padding:10px;'>"
            for sql in snippet.sql_examples:
                html += f"<pre style='white-space:pre-wrap;'>{sql}</pre><hr style='border:0; border-top:1px solid #3730a3;'>"
            html += "</div>"

        html += "</body></html>"
        self.detail_text.setHtml(html)
