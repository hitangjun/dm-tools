"""
问题排查和HINT建议面板

包含: 配置参数查看/修改、HINT优化建议、问题排查指引、数据库布局建议
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QPushButton, QSpinBox, QLineEdit, QHeaderView,
    QMessageBox, QInputDialog, QGroupBox,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

from core.dm_connector import DMConnector
from core.troubleshoot import ParamChecker, HintAdvisor, TroubleshootGuide
from core.doc_knowledge import DocKnowledgeBase
from ui.widgets.doc_info_widget import DocInfoWidget


class ParamCheckWorker(QThread):
    """参数查询后台线程"""
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, connector: DMConnector):
        super().__init__()
        self.connector = connector
        self.checker = ParamChecker(connector)

    def run(self):
        try:
            params = self.checker.check_all_key_params()
            self.finished.emit(params)
        except Exception as e:
            self.error.emit(str(e))


class ParamPanel(QWidget):
    """配置参数查看面板"""

    def __init__(self, connector: DMConnector, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.kb = DocKnowledgeBase()
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("param_check"))
        layout.addWidget(doc_widget)

        toolbar = QHBoxLayout()
        self.btn_check = QPushButton("🔍 检查所有关键参数")
        self.btn_check.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; font-weight: bold; padding: 6px 15px; }"
        )
        self.btn_check.clicked.connect(self._check)
        toolbar.addWidget(self.btn_check)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["参数名", "INI值", "内存值", "说明", "推荐值", "状态"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout.addWidget(self.tree)

    def _check(self):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        self.tree.clear()
        self.worker = ParamCheckWorker(self.connector)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, params):
        self.tree.clear()
        for p in params:
            # 判断状态
            status = "✅"
            if p.mem_value in ("N/A", "", None):
                status = "❓"
            elif p.recommend and p.recommend.isdigit() and p.mem_value != p.recommend:
                status = "⚠️"

            item = QTreeWidgetItem([
                p.name, p.ini_value, p.mem_value,
                p.description, p.recommend, status,
            ])
            if status == "⚠️":
                item.setForeground(5, QColor("#f59e0b"))
            elif status == "✅":
                item.setForeground(5, QColor("#16a34a"))
            self.tree.addTopLevelItem(item)

    def _on_error(self, error):
        QMessageBox.warning(self, "查询失败", error)


class HintPanel(QWidget):
    """HINT优化建议面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kb = DocKnowledgeBase()
        self.advisor = HintAdvisor()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("hint_advisor"))
        layout.addWidget(doc_widget)

        # SQL输入
        layout.addWidget(QLabel("输入SQL语句:"))
        self.sql_input = QTextEdit()
        self.sql_input.setFont(QFont("Consolas", 10))
        self.sql_input.setMaximumHeight(100)
        self.sql_input.setPlaceholderText("SELECT * FROM t1, t2 WHERE t1.id = t2.id AND t1.status = 'A';")
        layout.addWidget(self.sql_input)

        toolbar = QHBoxLayout()
        self.btn_analyze = QPushButton("🎯 生成HINT建议")
        self.btn_analyze.setStyleSheet(
            "QPushButton { background-color: #7c3aed; color: white; font-weight: bold; padding: 6px 15px; }"
        )
        self.btn_analyze.clicked.connect(self._analyze)
        toolbar.addWidget(self.btn_analyze)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 结果展示
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Microsoft YaHei", 10))
        layout.addWidget(self.result_text)

    def _analyze(self):
        sql = self.sql_input.toPlainText().strip()
        if not sql:
            QMessageBox.warning(self, "提示", "请输入SQL语句")
            return

        result = self.advisor.analyze(sql)

        html = "<html><body style='font-family: Microsoft YaHei; font-size: 10pt;'>"
        html += f"<p><b>{result.summary}</b></p>"

        for i, s in enumerate(result.suggestions, 1):
            html += f"<div style='background:#f5f3ff; border:1px solid #c4b5fd; border-radius:5px; padding:10px; margin:5px 0;'>"
            html += f"<p><b>建议 {i}:</b> {s.description}</p>"
            html += f"<p style='color:#6b7280;'>原因: {s.reason}</p>"
            html += f"<pre style='background:#1e1b4b; color:#a5f3fc; padding:10px; border-radius:4px; overflow-x:auto;'>{s.sql_with_hint}</pre>"
            html += "</div>"

        html += "</body></html>"
        self.result_text.setHtml(html)

    def set_sql(self, sql: str):
        self.sql_input.setPlainText(sql)


class TroubleshootPanel(QWidget):
    """问题排查指引面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kb = DocKnowledgeBase()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("troubleshoot"))
        layout.addWidget(doc_widget)

        # 排查步骤
        steps = TroubleshootGuide.get_troubleshoot_steps()
        layout.addWidget(QLabel("问题排查步骤:"))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["步骤", "检查项", "说明", "操作命令"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)

        for step in steps:
            commands = "\n".join(step.get("commands", []))
            item = QTreeWidgetItem([
                str(step["step"]),
                step["title"],
                step["detail"],
                commands,
            ])
            self.tree.addTopLevelItem(item)

        layout.addWidget(self.tree)

        # 布局优化建议
        layout.addWidget(QLabel("数据库布局优化建议:"))
        advice_text = QTextEdit()
        advice_text.setReadOnly(True)
        advice_text.setFont(QFont("Microsoft YaHei", 10))
        advice_text.setMaximumHeight(150)

        advice = TroubleshootGuide.get_layout_advice()
        advice_html = "<ul>"
        for a in advice:
            advice_html += f"<li>{a}</li>"
        advice_html += "</ul>"
        advice_text.setHtml(advice_html)
        layout.addWidget(advice_text)


class SQLBestPracticePanel(QWidget):
    """SQL开发最佳实践面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.kb = DocKnowledgeBase()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("sql_best_practice"))
        layout.addWidget(doc_widget)

        info_text = QTextEdit()
        info_text.setReadOnly(True)
        info_text.setFont(QFont("Microsoft YaHei", 10))

        snippet = self.kb.get("sql_best_practice")
        html = "<html><body style='font-family: Microsoft YaHei; font-size: 10pt;'>"
        html += "<pre style='white-space: pre-wrap;'>"
        html += snippet.doc_content.replace("<", "&lt;").replace(">", "&gt;")
        html += "</pre>"

        if snippet.sql_examples:
            html += "<h3>SQL示例:</h3><pre style='white-space: pre-wrap; background:#f0f9ff; padding:10px; border-radius:4px;'>"
            for ex in snippet.sql_examples:
                html += ex.replace("<", "&lt;").replace(">", "&gt;") + "\n"
            html += "</pre>"

        html += "</body></html>"
        info_text.setHtml(html)
        layout.addWidget(info_text)
