"""
知识库面板 - 浏览所有达梦官方文档知识
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
    QSizePolicy,
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 头部美化区域
        header_widget = QWidget()
        header_widget.setObjectName("header")
        header_widget.setStyleSheet("""
            QWidget#header {
                background-color: #ffffff;
                border-bottom: 1px solid #cbd5e1;
            }
            QLabel#title {
                font-size: 15px;
                font-weight: bold;
                color: #0f172a;
            }
            QLabel#subtitle {
                font-size: 12px;
                color: #64748b;
            }
        """)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(15, 12, 15, 12)
        header_layout.setSpacing(4)

        title_lbl = QLabel("📖 达梦官方文档知识库")
        title_lbl.setObjectName("title")
        subtitle_lbl = QLabel("浏览与检索达梦数据库官方调优指南、性能元数据视图与 SQL 优化最佳实践")
        subtitle_lbl.setObjectName("subtitle")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(subtitle_lbl)
        
        header_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        layout.addWidget(header_widget, 0)

        # 主分割区域
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #cbd5e1;
                width: 1px;
            }
        """)

        # 左侧: 功能列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["功能主题", "分类来源"])
        self.tree.setStyleSheet("""
            QTreeWidget {
                border: none;
                background-color: #ffffff;
            }
        """)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Interactive)

        for snippet in self.kb.get_all():
            item = QTreeWidgetItem([snippet.feature_name, snippet.doc_source])
            item.setData(0, Qt.UserRole, snippet.feature_id)
            self.tree.addTopLevelItem(item)

        # 设置非常合理且好看的初始列宽，支持用户拉伸
        self.tree.setColumnWidth(0, 240)
        self.tree.setColumnWidth(1, 140)

        self.tree.currentItemChanged.connect(self._on_selected)
        splitter.addWidget(self.tree)

        # 右侧: 文档详情 (复用 DocInfoWidget)
        self.detail_widget = DocInfoWidget()
        self.detail_widget.sql_example_clicked.connect(self.sql_example_clicked)
        splitter.addWidget(self.detail_widget)

        splitter.setSizes([340, 760])
        splitter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 将分割器以拉伸因子 1 添加到布局中，保证占满屏幕高度
        layout.addWidget(splitter, 1)

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
