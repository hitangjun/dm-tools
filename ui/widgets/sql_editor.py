"""
SQL编辑器组件

提供SQL输入、语法高亮(基础)、分析按钮
"""
import re
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QLabel, QComboBox,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QTextCharFormat, QSyntaxHighlighter, QColor


class SQLHighlighter(QSyntaxHighlighter):
    """简单的SQL语法高亮"""

    KEYWORDS = {
        "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT",
        "OUTER", "ON", "AND", "OR", "NOT", "IN", "IS", "NULL", "LIKE",
        "BETWEEN", "GROUP", "BY", "ORDER", "HAVING", "LIMIT", "TOP",
        "UNION", "ALL", "AS", "DISTINCT", "CASE", "WHEN", "THEN", "ELSE",
        "END", "INSERT", "INTO", "VALUES", "UPDATE", "SET", "DELETE",
        "CREATE", "TABLE", "INDEX", "DROP", "ALTER", "ADD", "EXPLAIN",
        "ASC", "DESC", "EXISTS", "COUNT", "SUM", "AVG", "MAX", "MIN",
    }

    # 预编译正则
    _keyword_re = re.compile(r'\b(' + '|'.join(KEYWORDS) + r')\b', re.IGNORECASE)
    _string_re = re.compile(r"'[^']*'")
    _comment_re = re.compile(r'--.*$')

    def __init__(self, document):
        super().__init__(document)
        self._keyword_format = QTextCharFormat()
        self._keyword_format.setForeground(QColor("#0000FF"))
        self._keyword_format.setFontWeight(QFont.Bold)

        self._string_format = QTextCharFormat()
        self._string_format.setForeground(QColor("#008000"))

        self._comment_format = QTextCharFormat()
        self._comment_format.setForeground(QColor("#808080"))
        self._comment_format.setFontItalic(True)

    def highlightBlock(self, text):
        # 关键字 (使用词边界匹配，避免匹配单词内部)
        for m in self._keyword_re.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._keyword_format)

        # 字符串
        for m in self._string_re.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._string_format)

        # 注释
        for m in self._comment_re.finditer(text):
            self.setFormat(m.start(), m.end() - m.start(), self._comment_format)


class SQLEditor(QWidget):
    """SQL编辑器"""

    analyze_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("SQL语句:"))

        self.example_combo = QComboBox()
        self.example_combo.addItem("-- 选择示例SQL --", "")
        self.example_combo.addItem("全表扫描示例",
            "SELECT * FROM orders WHERE customer_name = '张三';")
        self.example_combo.addItem("JOIN无索引示例",
            "SELECT a.order_id, b.customer_name FROM orders a "
            "JOIN customers b ON a.customer_id = b.customer_id "
            "WHERE a.status = 'PENDING';")
        self.example_combo.addItem("函数导致索引失效示例",
            "SELECT * FROM users WHERE UPPER(username) = 'ADMIN' "
            "AND create_time > '2024-01-01';")
        self.example_combo.addItem("LIKE前导通配符示例",
            "SELECT * FROM products WHERE product_name LIKE '%手机%' "
            "AND status = 'ACTIVE';")
        self.example_combo.currentIndexChanged.connect(self._on_example_changed)
        toolbar.addWidget(self.example_combo)
        toolbar.addStretch()

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self.clear_btn)

        self.analyze_btn = QPushButton("▶ 分析")
        self.analyze_btn.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; "
            "font-weight: bold; padding: 6px 20px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #1d4ed8; }"
        )
        self.analyze_btn.clicked.connect(self._on_analyze)
        toolbar.addWidget(self.analyze_btn)

        layout.addLayout(toolbar)

        # SQL编辑区
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Consolas", 11))
        self.editor.setPlaceholderText(
            "在此输入要分析的SQL语句...\n\n"
            "支持SELECT/UPDATE/DELETE/INSERT语句\n"
            "工具将分析执行计划、索引建议、统计信息和SQL写法规范"
        )
        self.highlighter = SQLHighlighter(self.editor.document())
        layout.addWidget(self.editor)

    def _on_analyze(self):
        sql = self.editor.toPlainText().strip()
        if sql:
            self.analyze_requested.emit(sql)

    def _on_clear(self):
        self.editor.clear()

    def _on_example_changed(self, index):
        sql = self.example_combo.itemData(index)
        if sql:
            self.editor.setPlainText(sql)

    def set_sql(self, sql: str):
        self.editor.setPlainText(sql)

    def get_sql(self) -> str:
        return self.editor.toPlainText()
