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

        self.history_combo = QComboBox()
        self.history_combo.setPlaceholderText("-- 历史分析SQL --")
        self.history_combo.setToolTip("选择之前分析过的 SQL 语句")
        self.history_combo.currentIndexChanged.connect(self._on_history_changed)
        self.history_combo.setMinimumWidth(200)
        toolbar.addWidget(self.history_combo)

        toolbar.addStretch()

        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._on_clear)
        toolbar.addWidget(self.clear_btn)

        self.format_btn = QPushButton("🔧 格式化")
        self.format_btn.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; "
            "font-weight: bold; padding: 6px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #047857; }"
        )
        self.format_btn.setToolTip("使用 sqlparse 对 SQL 语句进行标准化缩进与换行格式化")
        self.format_btn.clicked.connect(self._on_format)
        toolbar.addWidget(self.format_btn)

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

    def _on_format(self):
        """使用 sqlparse 对 SQL 进行标准化格式化"""
        sql = self.editor.toPlainText().strip()
        if not sql:
            return
        try:
            import sqlparse
            formatted = sqlparse.format(
                sql,
                reindent=True,
                keyword_case="upper",
                identifier_case=None,
                indent_width=4,
                wrap_after=80,
            )
            self.editor.setPlainText(formatted)
        except ImportError:
            # sqlparse 未安装时简单清理空白
            import re
            keywords = [
                "SELECT", "FROM", "WHERE", "JOIN", "INNER JOIN",
                "LEFT JOIN", "RIGHT JOIN", "LEFT OUTER JOIN",
                "ON", "AND", "OR", "ORDER BY", "GROUP BY",
                "HAVING", "LIMIT", "UNION", "UNION ALL",
                "INSERT INTO", "VALUES", "UPDATE", "SET", "DELETE FROM",
            ]
            result = re.sub(r'\s+', ' ', sql).strip()
            for kw in sorted(keywords, key=len, reverse=True):
                pattern = re.compile(r'\b' + kw + r'\b', re.IGNORECASE)
                result = pattern.sub(f"\n{kw}", result)
            self.editor.setPlainText(result.strip())



    def set_sql(self, sql: str):
        self.editor.setPlainText(sql)

    def get_sql(self) -> str:
        return self.editor.toPlainText()

    def _on_history_changed(self, index):
        if index < 0:
            return
        sql = self.history_combo.itemData(index)
        if sql:
            self.editor.setPlainText(sql)

    def update_history(self, history_sqls: list[str]):
        """更新历史分析SQL下拉列表"""
        self.history_combo.blockSignals(True)
        self.history_combo.clear()
        self.history_combo.addItem("-- 历史分析SQL --", "")
        for sql in history_sqls:
            # 将换行变为空格并缩写作为展示文本
            short_sql = " ".join(sql.split())[:60] + "..." if len(sql) > 60 else " ".join(sql.split())
            self.history_combo.addItem(short_sql, sql)
        self.history_combo.blockSignals(False)
