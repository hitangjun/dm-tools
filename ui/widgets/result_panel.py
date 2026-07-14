"""
分析结果展示面板

用Tab页展示四类分析结果:
1. 总览 - 综合评分和关键问题摘要
2. 执行计划 - 执行计划文本 + 问题高亮
3. 索引建议 - 建议列表 + DDL
4. 统计信息 - 表/索引统计状态
5. SQL规范 - 写法问题列表
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QProgressBar, QHeaderView, QGroupBox, QSplitter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat


# 颜色定义
LEVEL_COLORS = {
    "CRITICAL": "#dc2626",
    "WARNING": "#f59e0b",
    "INFO": "#3b82f6",
    "GOOD": "#16a34a",
}

LEVEL_LABELS = {
    "CRITICAL": "严重",
    "WARNING": "警告",
    "INFO": "提示",
    "GOOD": "正常",
}


class ResultPanel(QWidget):
    """分析结果展示面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 综合评分条
        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel("综合评分:"))
        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setFixedWidth(200)
        self.score_bar.setFormat("%v / 100")
        score_layout.addWidget(self.score_bar)
        self.score_label = QLabel("等待分析...")
        self.score_label.setStyleSheet("font-weight: bold;")
        score_layout.addWidget(self.score_label)
        score_layout.addStretch()
        layout.addLayout(score_layout)

        # Tab页
        self.tabs = QTabWidget()

        # Tab 1: 总览
        self.overview_tab = QTextEdit()
        self.overview_tab.setReadOnly(True)
        self.overview_tab.setFont(QFont("Microsoft YaHei", 10))
        self.tabs.addTab(self.overview_tab, "总览")

        # Tab 2: 执行计划
        self.plan_tab = QWidget()
        plan_layout = QVBoxLayout(self.plan_tab)
        self.plan_issues_tree = QTreeWidget()
        self.plan_issues_tree.setHeaderLabels(["级别", "类别", "问题描述", "建议"])
        self.plan_issues_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.plan_issues_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.plan_issues_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.plan_issues_tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        plan_layout.addWidget(QLabel("发现的问题:"))
        plan_layout.addWidget(self.plan_issues_tree)

        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(True)
        self.plan_text.setFont(QFont("Consolas", 10))
        plan_layout.addWidget(QLabel("执行计划:"))
        plan_layout.addWidget(self.plan_text)
        self.tabs.addTab(self.plan_tab, "执行计划分析")

        # Tab 3: 索引建议
        self.index_tab = QWidget()
        index_layout = QVBoxLayout(self.index_tab)
        self.index_tree = QTreeWidget()
        self.index_tree.setHeaderLabels([
            "优先级", "表名", "建议类型", "列", "原因", "DDL"
        ])
        self.index_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.index_tree.header().setSectionResizeMode(5, QHeaderView.Stretch)
        index_layout.addWidget(self.index_tree)
        self.tabs.addTab(self.index_tab, "索引建议")

        # Tab 4: 统计信息
        self.stats_tab = QTextEdit()
        self.stats_tab.setReadOnly(True)
        self.stats_tab.setFont(QFont("Microsoft YaHei", 10))
        self.tabs.addTab(self.stats_tab, "统计信息")

        # Tab 5: SQL规范
        self.lint_tab = QWidget()
        lint_layout = QVBoxLayout(self.lint_tab)
        self.lint_tree = QTreeWidget()
        self.lint_tree.setHeaderLabels(["级别", "规则", "问题描述", "建议"])
        self.lint_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.lint_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.lint_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.lint_tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        lint_layout.addWidget(self.lint_tree)
        self.tabs.addTab(self.lint_tab, "SQL写法规范")

        layout.addWidget(self.tabs)

    # ------------------------------------------------------------------
    # 结果展示方法
    # ------------------------------------------------------------------

    def clear(self):
        """清空所有结果"""
        self.score_bar.setValue(0)
        self.score_label.setText("等待分析...")
        self.overview_tab.clear()
        self.plan_issues_tree.clear()
        self.plan_text.clear()
        self.index_tree.clear()
        self.stats_tab.clear()
        self.lint_tree.clear()

    def show_results(
        self,
        plan_result=None,
        index_result=None,
        stats_result=None,
        lint_result=None,
        plan_text="",
        error=None,
    ):
        """展示所有分析结果"""

        if error:
            self.overview_tab.setPlainText(f"分析失败:\n\n{error}")
            self.score_bar.setValue(0)
            self.score_label.setText("分析失败")
            self.score_label.setStyleSheet("font-weight: bold; color: red;")
            return

        # 计算综合评分
        scores = []
        if plan_result:
            scores.append(plan_result.cost_score)
        if lint_result:
            scores.append(lint_result.score)
        avg_score = int(sum(scores) / len(scores)) if scores else 0

        self.score_bar.setValue(avg_score)
        if avg_score >= 80:
            color = "green"
            rating = "良好"
        elif avg_score >= 60:
            color = "#f59e0b"
            rating = "一般"
        else:
            color = "red"
            rating = "需优化"
        self.score_label.setText(f"{rating}")
        self.score_label.setStyleSheet(f"font-weight: bold; color: {color};")

        # 总览
        self._show_overview(plan_result, index_result, stats_result, lint_result)

        # 执行计划
        self._show_plan(plan_result, plan_text)

        # 索引建议
        self._show_index(index_result)

        # 统计信息
        self._show_stats(stats_result)

        # SQL规范
        self._show_lint(lint_result)

    def _show_overview(self, plan_result, index_result, stats_result, lint_result):
        """总览"""
        html = "<html><body style='font-family: Microsoft YaHei; font-size: 11pt;'>"
        html += "<h2>分析总览</h2>"

        if plan_result:
            color = "green" if plan_result.cost_score >= 60 else "red"
            html += f"<h3>执行计划</h3>"
            html += f"<p>评分: <b style='color:{color}'>{plan_result.cost_score}/100</b></p>"
            html += f"<pre style='background:#f5f5f5; padding:10px; border-radius:5px;'>{plan_result.summary}</pre>"

        if lint_result:
            color = "green" if lint_result.score >= 60 else "red"
            html += f"<h3>SQL规范</h3>"
            html += f"<p>评分: <b style='color:{color}'>{lint_result.score}/100</b></p>"
            html += f"<pre style='background:#f5f5f5; padding:10px; border-radius:5px;'>{lint_result.summary}</pre>"

        if index_result:
            html += f"<h3>索引建议</h3>"
            html += f"<p>{index_result.summary}</p>"

        if stats_result:
            html += f"<h3>统计信息</h3>"
            html += f"<pre style='background:#f5f5f5; padding:10px; border-radius:5px;'>{stats_result.summary}</pre>"

        # 关键问题摘要
        html += "<h3>关键问题</h3><ul>"
        has_issues = False
        if plan_result:
            for issue in plan_result.issues:
                if issue.level.value == "CRITICAL":
                    html += f"<li style='color:red;'>【执行计划】{issue.category}: {issue.description}</li>"
                    has_issues = True
        if lint_result:
            for rule in lint_result.rules:
                if rule.level in ("CRITICAL", "WARNING"):
                    color = "#dc2626" if rule.level == "CRITICAL" else "#f59e0b"
                    html += f"<li style='color:{color};'>【SQL规范】{rule.rule_name}: {rule.description}</li>"
                    has_issues = True
        if not has_issues:
            html += "<li style='color:green;'>未发现严重问题</li>"
        html += "</ul>"
        html += "</body></html>"

        self.overview_tab.setHtml(html)

    def _show_plan(self, plan_result, plan_text):
        """执行计划"""
        self.plan_text.setPlainText(plan_text)
        if plan_result:
            for issue in plan_result.issues:
                level_text = LEVEL_LABELS.get(issue.level.value, issue.level.value)
                item = QTreeWidgetItem([
                    level_text,
                    issue.category,
                    issue.description,
                    issue.suggestion,
                ])
                color = LEVEL_COLORS.get(issue.level.value, "black")
                item.setForeground(0, QColor(color))
                self.plan_issues_tree.addTopLevelItem(item)

    def _show_index(self, index_result):
        """索引建议"""
        if not index_result:
            return
        for s in index_result.suggestions:
            priority_text = "★" * s.priority + "☆" * (5 - s.priority)
            item = QTreeWidgetItem([
                priority_text,
                s.table_name,
                s.suggestion_type,
                ", ".join(s.columns),
                s.reason,
                s.ddl,
            ])
            if s.existing_index_conflict:
                item.setForeground(5, QColor("#808080"))
            self.index_tree.addTopLevelItem(item)

    def _show_stats(self, stats_result):
        """统计信息"""
        if not stats_result:
            self.stats_tab.setPlainText("未获取到统计信息(可能未连接数据库)")
            return
        text = stats_result.summary + "\n\n"
        text += "=" * 60 + "\n\n"
        for issue in stats_result.issues:
            text += f"[{issue.level}] {issue.issue_type}\n"
            text += f"  表: {issue.table_name}\n"
            text += f"  问题: {issue.description}\n"
            text += f"  建议: {issue.suggestion}\n\n"
        self.stats_tab.setPlainText(text)

    def _show_lint(self, lint_result):
        """SQL规范"""
        if not lint_result:
            return
        for rule in lint_result.rules:
            item = QTreeWidgetItem([
                LEVEL_LABELS.get(rule.level, rule.level),
                rule.rule_name,
                rule.description,
                rule.suggestion,
            ])
            color = LEVEL_COLORS.get(rule.level, "black")
            item.setForeground(0, QColor(color))
            self.lint_tree.addTopLevelItem(item)
