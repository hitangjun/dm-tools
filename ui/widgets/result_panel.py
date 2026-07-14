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
        plan_layout = QHBoxLayout(self.plan_tab)
        plan_layout.setContentsMargins(6, 6, 6, 6)

        plan_splitter = QSplitter(Qt.Horizontal)

        # 左侧：执行计划原始树
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("达梦执行计划树 (层级缩进):"))
        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(True)
        self.plan_text.setFont(QFont("Consolas", 10))
        left_layout.addWidget(self.plan_text)
        plan_splitter.addWidget(left_widget)

        # 右侧：问题列表 + 深度解析建议
        right_splitter = QSplitter(Qt.Vertical)

        issues_group = QGroupBox("执行计划潜在缺陷/性能瓶颈")
        issues_layout = QVBoxLayout(issues_group)
        self.plan_issues_tree = QTreeWidget()
        self.plan_issues_tree.setHeaderLabels(["级别", "缺陷类别", "节点位置", "具体描述"])
        self.plan_issues_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.plan_issues_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.plan_issues_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.plan_issues_tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        issues_layout.addWidget(self.plan_issues_tree)
        right_splitter.addWidget(issues_group)

        explanation_group = QGroupBox("执行计划节点深度解释与调优指导")
        explanation_layout = QVBoxLayout(explanation_group)
        self.plan_explanation = QTextEdit()
        self.plan_explanation.setReadOnly(True)
        self.plan_explanation.setFont(QFont("Microsoft YaHei", 10))
        explanation_layout.addWidget(self.plan_explanation)
        right_splitter.addWidget(explanation_group)

        right_splitter.setSizes([180, 320])
        plan_splitter.addWidget(right_splitter)

        plan_splitter.setSizes([450, 550])
        plan_layout.addWidget(plan_splitter)
        self.tabs.addTab(self.plan_tab, "执行计划分析")

        # Tab 3: 索引建议
        self.index_tab = QWidget()
        index_layout = QVBoxLayout(self.index_tab)
        index_layout.setContentsMargins(6, 6, 6, 6)

        # 用 QSplitter 上下分割: 上为已有索引，下为优化建议
        index_splitter = QSplitter(Qt.Vertical)

        # 上半部分：当前已有索引
        existing_group = QGroupBox("当前表结构已有索引 (数据库真实状态)")
        existing_layout = QVBoxLayout(existing_group)
        self.existing_index_tree = QTreeWidget()
        self.existing_index_tree.setHeaderLabels([
            "表名", "索引名", "类型", "唯一性", "包含的列", "索引行数", "上次分析时间"
        ])
        self.existing_index_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.existing_index_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.existing_index_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.existing_index_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.existing_index_tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.existing_index_tree.header().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.existing_index_tree.header().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        existing_layout.addWidget(self.existing_index_tree)
        index_splitter.addWidget(existing_group)

        # 下半部分：推荐的优化索引建议
        recommend_group = QGroupBox("推荐优化索引建议")
        recommend_layout = QVBoxLayout(recommend_group)
        self.index_tree = QTreeWidget()
        self.index_tree.setHeaderLabels([
            "优先级", "表名", "建议类型", "建议列", "建议原因", "建议DDL语句"
        ])
        self.index_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.index_tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.index_tree.header().setSectionResizeMode(5, QHeaderView.Stretch)
        recommend_layout.addWidget(self.index_tree)
        index_splitter.addWidget(recommend_group)

        index_splitter.setSizes([200, 350])
        index_layout.addWidget(index_splitter)
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

        # Tab 6: 表结构 DDL
        self.ddl_tab = QWidget()
        ddl_layout = QVBoxLayout(self.ddl_tab)
        ddl_layout.setContentsMargins(6, 6, 6, 6)

        ddl_splitter = QSplitter(Qt.Horizontal)

        self.ddl_tables_tree = QTreeWidget()
        self.ddl_tables_tree.setHeaderLabels(["表名"])
        self.ddl_tables_tree.currentItemChanged.connect(self._on_ddl_table_changed)
        ddl_splitter.addWidget(self.ddl_tables_tree)

        self.ddl_text = QTextEdit()
        self.ddl_text.setReadOnly(True)
        self.ddl_text.setFont(QFont("Consolas", 10))
        ddl_splitter.addWidget(self.ddl_text)

        ddl_splitter.setSizes([150, 500])
        ddl_layout.addWidget(ddl_splitter)
        self.tabs.addTab(self.ddl_tab, "表结构 DDL")

        self.ddls = {}  # 存储表 DDL 数据

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
        self.plan_explanation.clear()
        self.index_tree.clear()
        self.existing_index_tree.clear()
        self.ddl_tables_tree.clear()
        self.ddl_text.clear()
        self.ddls = {}
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
        ddls=None,
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

        # 展示 DDL
        self._show_ddl(ddls)

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
        self.plan_issues_tree.clear()
        self.plan_explanation.clear()

        if not plan_result:
            self.plan_explanation.setPlainText("未获取到执行计划分析结果。")
            return

        # 1. 填充问题树
        for issue in plan_result.issues:
            level_text = LEVEL_LABELS.get(issue.level.value, issue.level.value)
            item = QTreeWidgetItem([
                level_text,
                issue.category,
                issue.location,
                issue.description,
            ])
            color = LEVEL_COLORS.get(issue.level.value, "black")
            item.setForeground(0, QColor(color))
            self.plan_issues_tree.addTopLevelItem(item)

        # 2. 生成深度解析与调优建议 HTML
        html = "<html><body style='font-family: Microsoft YaHei; font-size: 10pt; line-height: 1.45;'>"
        html += "<h3>🔍 优化器执行计划评估分析</h3>"
        html += f"<p><b>综合评估评分</b>: <span style='font-size: 12pt; font-weight: bold; color: {'green' if plan_result.cost_score >= 80 else ('#f59e0b' if plan_result.cost_score >= 60 else 'red')}'>{plan_result.cost_score} / 100</span></p>"
        html += f"<p><b>关键算子特征统计</b>: 全表扫描(SSCN/CSCN) <b>{plan_result.table_scans}</b> 次，多表连接 <b>{plan_result.join_count}</b> 次，内存/磁盘排序 <b>{plan_result.sort_count}</b> 次。</p>"
        
        html += "<h3>💡 执行计划节点缺陷定位说明</h3>"
        if plan_result.issues:
            html += "<ol style='padding-left: 20px;'>"
            for issue in plan_result.issues:
                html += f"<li style='margin-bottom: 12px;'><b>[{issue.category}]</b> (节点处于 {issue.location}):<br/>"
                html += f"  <span style='color: #4b5563;'>算子特征: {issue.operation}</span><br/>"
                html += f"  <span style='color: #b91c1c;'>影响危害: {issue.description}</span><br/>"
                html += f"  <span style='color: #15803d; font-weight: bold;'>优化建议: {issue.suggestion}</span>"
                html += "</li>"
            html += "</ol>"
        else:
            html += "<p style='color: #16a34a; font-weight: bold;'>🎉 该执行计划无高危算子，执行路径良好，未检测到全表扫描或高危笛卡尔积。</p>"
            
        html += "<h3>🛠️ 达梦执行计划调优常规方针</h3>"
        html += "<ul style='padding-left: 20px; line-height: 1.6;'>"
        html += "  <li><b>表/索引统计信息收集</b>: 达梦是基于代价的优化器 (CBO)，执行计划里的“估算代价”(Cost) 是相对值。若估算代价或行数与实际物理情况发生巨大偏差，常导致错选执行路径。请尝试执行 <code>DBMS_STATS.GATHER_TABLE_STATS</code> 重新收集统计信息。</li>"
        html += "  <li><b>使用 HINT 引导优化器</b>: 达梦支持类似 <code>/*+ USE_HASH(表名) */</code>，<code>/*+ INDEX(表名 索引名) */</code> 等 HINT 语法，可强制纠正由于 CBO 估算失准造成的连接类型/扫描路径选错。</li>"
        html += "  <li><b>优化全表扫描 (SSCN/CSCN)</b>: SSCN 为索引全扫描，CSCN 为聚集索引扫描（即全表扫描）。对有 CSCN 的大表，应检查 WHERE 条件列上是否遗漏了非聚集索引，或是否对索引列使用了函数计算（例如 <code>TO_CHAR(COL)</code>）导致索引失效。</li>"
        html += "</ul>"
        html += "</body></html>"
        
        self.plan_explanation.setHtml(html)

    def _show_index(self, index_result):
        """索引建议"""
        self.index_tree.clear()
        self.existing_index_tree.clear()
        if not index_result:
            return

        # 展示当前已有索引
        if hasattr(index_result, "existing_indexes") and index_result.existing_indexes:
            for idx in index_result.existing_indexes:
                columns_str = ", ".join(idx.get("columns", []))
                uniqueness = "唯一" if idx.get("uniqueness") == "UNIQUE" else "非唯一"
                analyzed = idx.get("last_analyzed") or "未分析"
                rows = f"{idx.get('num_rows'):,}" if idx.get("num_rows") is not None else "N/A"
                
                item = QTreeWidgetItem([
                    idx.get("table_name", "UNKNOWN"),
                    idx.get("name", ""),
                    idx.get("type", ""),
                    uniqueness,
                    columns_str,
                    rows,
                    analyzed,
                ])
                self.existing_index_tree.addTopLevelItem(item)
        else:
            item = QTreeWidgetItem([
                "未获取到已有索引信息（可能未连接数据库或表无索引）"
            ])
            self.existing_index_tree.addTopLevelItem(item)

        # 展示推荐优化建议
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

    def _show_ddl(self, ddls):
        """展示表 DDL"""
        self.ddl_tables_tree.clear()
        self.ddl_text.clear()
        self.ddls = ddls or {}

        if not self.ddls:
            item = QTreeWidgetItem(["无关联表 DDL 信息"])
            self.ddl_tables_tree.addTopLevelItem(item)
            return

        for table_name in sorted(self.ddls.keys()):
            item = QTreeWidgetItem([table_name])
            self.ddl_tables_tree.addTopLevelItem(item)

        # 默认选中第一个
        if self.ddl_tables_tree.topLevelItemCount() > 0:
            self.ddl_tables_tree.setCurrentItem(self.ddl_tables_tree.topLevelItem(0))

    def _on_ddl_table_changed(self, current, previous):
        if not current:
            self.ddl_text.clear()
            return
        table_name = current.text(0)
        ddl = self.ddls.get(table_name, "")
        self.ddl_text.setPlainText(ddl)
