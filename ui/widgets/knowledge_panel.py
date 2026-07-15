"""
知识库面板 - 浏览所有达梦官方文档知识
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
)
from PySide6.QtCore import Qt, Signal

from core.doc_knowledge import DocKnowledgeBase
from ui.widgets.doc_info_widget import DocInfoWidget


class KnowledgePanel(QWidget):
    """知识库浏览面板"""
    sql_example_clicked = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kb = DocKnowledgeBase()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        title = QLabel("达梦官方文档知识库")
        title.setStyleSheet("font-size: 13pt; font-weight: bold; padding: 5px; color: #1e293b;")
        layout.addWidget(title)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧: 功能列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["功能", "文档来源"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)

        for snippet in self.kb.get_all():
            item = QTreeWidgetItem([snippet.feature_name, snippet.doc_source])
            item.setData(0, Qt.UserRole, snippet.feature_id)
            self.tree.addTopLevelItem(item)

        for i in range(self.tree.columnCount()):
            self.tree.resizeColumnToContents(i)
            self.tree.setColumnWidth(i, max(self.tree.columnWidth(i) + 25, 120))

        self.tree.currentItemChanged.connect(self._on_selected)
        splitter.addWidget(self.tree)

        # 右侧: 文档详情 (复用 DocInfoWidget)
        self.detail_widget = DocInfoWidget()
        self.detail_widget.sql_example_clicked.connect(self.sql_example_clicked)
        splitter.addWidget(self.detail_widget)

        splitter.setSizes([320, 780])
        layout.addWidget(splitter)

        # 默认选中第一个
        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))

    def _on_selected(self, current, previous):
        if not current:
            self.detail_widget.set_snippet(None)
            return
        feature_id = current.data(0, Qt.UserRole)
        snippet = self.kb.get(feature_id)
        self.detail_widget.set_snippet(snippet)
