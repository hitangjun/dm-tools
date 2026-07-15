"""
分析结果展示面板

用Tab页展示四类分析结果:
1. 总览 - 综合评分和关键问题摘要
2. 执行计划 - 执行计划文本 + 问题高亮
3. 索引建议 - 建议列表 + DDL
4. 统计信息 - 表/索引统计状态
5. SQL规范 - 写法问题列表
"""
import re
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QProgressBar, QHeaderView, QGroupBox, QSplitter,
    QApplication, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QTextCharFormat, QShortcut, QKeySequence

from core.dm_connector import QueryResult


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

        # 左侧：执行计划展示（层级计划树与原始执行计划 Tab 切换）
        self.plan_left_tabs = QTabWidget()
        
        self.plan_text = QTextEdit()
        self.plan_text.setReadOnly(True)
        self.plan_text.setFont(QFont("Consolas", 10))
        self.plan_left_tabs.addTab(self.plan_text, "层级计划树")
        
        self.plan_raw_text = QTextEdit()
        self.plan_raw_text.setReadOnly(True)
        self.plan_raw_text.setFont(QFont("Consolas", 10))
        self.plan_raw_text.setLineWrapMode(QTextEdit.NoWrap)  # 禁止折行以适应原始大表排版
        self.plan_left_tabs.addTab(self.plan_raw_text, "原始执行计划")
        
        plan_splitter.addWidget(self.plan_left_tabs)

        # 右侧：问题列表 + 深度解析建议
        right_splitter = QSplitter(Qt.Vertical)

        issues_group = QGroupBox("执行计划潜在缺陷/性能瓶颈")
        issues_layout = QVBoxLayout(issues_group)
        
        # 按钮栏：导入外部计划进行离线分析
        btn_layout = QHBoxLayout()
        self.btn_import_plan = QPushButton("📥 导入外部计划进行离线分析")
        self.btn_import_plan.setStyleSheet(
            "QPushButton { background-color: #f1f5f9; font-weight: bold; padding: 4px 10px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #e2e8f0; }"
        )
        self.btn_import_plan.clicked.connect(self._on_import_plan_clicked)
        btn_layout.addWidget(self.btn_import_plan)
        btn_layout.addStretch()
        issues_layout.addLayout(btn_layout)

        self.plan_issues_tree = QTreeWidget()
        self.plan_issues_tree.setHeaderLabels(["级别", "缺陷类别", "节点位置", "具体描述"])
        for col in range(4):
            self.plan_issues_tree.header().setSectionResizeMode(col, QHeaderView.Interactive)
        self._setup_copy_menu(self.plan_issues_tree)
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
        for col in range(7):
            self.existing_index_tree.header().setSectionResizeMode(col, QHeaderView.Interactive)
        self._setup_copy_menu(self.existing_index_tree)
        existing_layout.addWidget(self.existing_index_tree)
        index_splitter.addWidget(existing_group)

        # 下半部分：推荐的优化索引建议
        recommend_group = QGroupBox("推荐优化索引建议")
        recommend_layout = QVBoxLayout(recommend_group)
        self.index_tree = QTreeWidget()
        self.index_tree.setHeaderLabels([
            "优先级", "表名", "建议类型", "建议列", "建议原因", "建议DDL语句"
        ])
        for col in range(6):
            self.index_tree.header().setSectionResizeMode(col, QHeaderView.Interactive)
        self._setup_copy_menu(self.index_tree, is_recommend_index=True)
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
        for col in range(4):
            self.lint_tree.header().setSectionResizeMode(col, QHeaderView.Interactive)
        self._setup_copy_menu(self.lint_tree)
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
        plan_raw_text="",
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
        self._show_plan(plan_result, plan_text, plan_raw_text)

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

    def _show_plan(self, plan_result, plan_text, plan_raw_text=""):
        """执行计划"""
        self.plan_text.setPlainText(plan_text)
        self.plan_raw_text.setPlainText(plan_raw_text or "暂无原始执行计划表格。")
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

        # 插入动态生成的算子释义词典，极大提升离线模式下的易用性
        glossary_html = self._generate_operator_glossary(plan_text)
        if glossary_html:
            html += glossary_html

        html += "</body></html>"
        
        self.plan_explanation.setHtml(html)

        # 动态自适应调整列宽，但保持可交互拉伸
        for i in range(self.plan_issues_tree.columnCount()):
            self.plan_issues_tree.resizeColumnToContents(i)
            self.plan_issues_tree.setColumnWidth(i, max(self.plan_issues_tree.columnWidth(i) + 15, 80))

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

        # 动态自适应调整列宽，但保持可交互拉伸
        for i in range(self.existing_index_tree.columnCount()):
            self.existing_index_tree.resizeColumnToContents(i)
            self.existing_index_tree.setColumnWidth(i, max(self.existing_index_tree.columnWidth(i) + 15, 80))
        for i in range(self.index_tree.columnCount()):
            self.index_tree.resizeColumnToContents(i)
            self.index_tree.setColumnWidth(i, max(self.index_tree.columnWidth(i) + 15, 80))

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

        # 动态自适应调整列宽，但保持可交互拉伸
        for i in range(self.lint_tree.columnCount()):
            self.lint_tree.resizeColumnToContents(i)
            self.lint_tree.setColumnWidth(i, max(self.lint_tree.columnWidth(i) + 15, 80))

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

    def _setup_copy_menu(self, tree_widget: QTreeWidget, is_recommend_index: bool = False):
        """为 QTreeWidget 安装右键菜单和 Ctrl+C 复制支持"""
        tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        tree_widget.customContextMenuRequested.connect(
            lambda pos: self._show_tree_context_menu(tree_widget, pos, is_recommend_index)
        )
        
        # 绑定 Ctrl+C 快捷键
        shortcut = QShortcut(QKeySequence("Ctrl+C"), tree_widget)
        shortcut.activated.connect(lambda: self._copy_tree_selection_to_clipboard(tree_widget))

    def _show_tree_context_menu(self, tree, pos, is_recommend_index=False):
        item = tree.itemAt(pos)
        if not item:
            return
        
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self)
        
        # 1. 复制选中行
        act_copy_row = QAction("📋 复制选中行 (表格格式)", self)
        act_copy_row.triggered.connect(lambda: self._copy_tree_row(tree, item))
        menu.addAction(act_copy_row)
        
        # 2. 如果是推荐索引，添加一键复制 DDL 选项
        if is_recommend_index:
            # 建议 DDL 在最后一列 (Column 5)
            ddl_text = item.text(5)
            if ddl_text and ddl_text != "N/A":
                act_copy_ddl = QAction("⚡ 复制推荐索引 DDL 语句", self)
                act_copy_ddl.triggered.connect(lambda: self._copy_text_to_clipboard(ddl_text))
                menu.addAction(act_copy_ddl)
                
        # 3. 复制特定单元格内容 (基于右击时选中的列)
        col_idx = tree.columnAt(pos.x())
        if 0 <= col_idx < tree.columnCount():
            cell_text = item.text(col_idx)
            col_name = tree.headerItem().text(col_idx)
            act_copy_cell = QAction(f"📄 复制单元格: {col_name}", self)
            act_copy_cell.triggered.connect(lambda: self._copy_text_to_clipboard(cell_text))
            menu.addAction(act_copy_cell)
            
        menu.exec(tree.viewport().mapToGlobal(pos))

    def _copy_tree_row(self, tree, item):
        cells = []
        for col in range(tree.columnCount()):
            cells.append(item.text(col))
        row_text = "\t".join(cells)
        self._copy_text_to_clipboard(row_text)

    def _copy_tree_selection_to_clipboard(self, tree):
        selected = tree.selectedItems()
        if not selected:
            return
        rows_text = []
        for item in selected:
            cells = [item.text(col) for col in range(tree.columnCount())]
            rows_text.append("\t".join(cells))
        self._copy_text_to_clipboard("\n".join(rows_text))

    def _copy_text_to_clipboard(self, text):
        if text:
            QApplication.clipboard().setText(text)
            parent = self.window()
            if hasattr(parent, "log"):
                parent.log(f"已成功复制到剪贴板: {text[:100]}...", "SUCCESS")

    def _generate_operator_glossary(self, plan_text: str) -> str:
        """从计划文本中提取出现的算子并生成其通俗解释"""
        if not plan_text:
            return ""
            
        # 查找所有大写字母组成的算子名字，通常是└─后面的英文单词，如 CSCN2, BLKUP2, SSEK2
        operators = set(re.findall(r'└─\s*([A-Z0-9_\s]+?)(?:\s*\[|$)', plan_text))
        cleaned_ops = set()
        for op in operators:
            op_clean = op.strip()
            op_first = op_clean.split()[0]
            if op_first.isupper() and len(op_first) >= 3:
                cleaned_ops.add(op_first)
                
        if not cleaned_ops:
            return ""
            
        glossary = {
            "NSET": ("结果集收集", "最终结果集的输出节点。通常是计划树的根节点。"),
            "NSET2": ("结果集收集", "最终结果集的输出节点。通常是计划树的根节点。"),
            "PRJT": ("投影算子", "选择输出列或计算表达式。将下层算子传递的数据做投影处理。"),
            "PRJT2": ("投影算子", "选择输出列或计算表达式。将下层算子传递的数据做投影处理。"),
            "SLCT": ("选择过滤", "根据 WHERE 条件过滤下层传递的数据行，只保留符合条件的记录。"),
            "SLCT2": ("选择过滤", "根据 WHERE 条件过滤下层传递的数据行，只保留符合条件的记录。"),
            "CSCN": ("聚集索引全表扫描", "<b style='color:red;'>高危操作！</b>读取整张表的所有数据。在大表上极消耗磁盘 I/O。建议在过滤条件列上建立索引。"),
            "CSCN2": ("聚集索引全表扫描", "<b style='color:red;'>高危操作！</b>读取整张表的所有数据。在大表上极消耗磁盘 I/O。建议在过滤条件列上建立索引。"),
            "SSCN": ("二级索引全扫描", "扫描整个二级索引树。通常比 CSCN（全表扫描）快，但读取整棵索引树依然代价不小。建议评估是否可优化过滤条件。"),
            "SSCN2": ("二级索引全扫描", "扫描整个二级索引树。通常比 CSCN（全表扫描）快，但读取整棵索引树依然代价不小。建议评估是否可优化过滤条件。"),
            "SSEK": ("二级索引等值定位", "通过二级索引树进行等值查找定位行。性能极佳，是理想的数据读取方式。"),
            "SSEK2": ("二级索引等值定位", "通过二级索引树进行等值查找定位行。性能极佳，是理想的数据读取方式。"),
            "CSEK": ("聚集索引范围定位", "在聚集索引（主键）上进行范围扫描。性能良好。"),
            "CSEK2": ("聚集索引范围定位", "在聚集索引（主键）上进行范围扫描。性能良好。"),
            "BLKUP": ("回表查找", "二级索引只存储了索引列和主键(ROWID)。当需要读取其他列时，必须使用主键返回主表再次读取记录。如果回表行数过多，I/O 开销非常大。建议使用<b>覆盖索引</b>（将 SELECT 列也加入索引中）以消除回表。"),
            "BLKUP2": ("回表查找", "二级索引只存储了索引列和主键(ROWID)。当需要读取其他列时，必须使用主键返回主表再次读取记录。如果回表行数过多，I/O 开销非常大。建议使用<b>覆盖索引</b>（将 SELECT 列也加入索引中）以消除回表。"),
            "SORT": ("排序算子", "对数据进行排序（由 ORDER BY / GROUP BY / DISTINCT 触发）。大数据量排序会使用临时表空间，降低速度。建议通过索引来避免排序。"),
            "SORT3": ("排序算子", "对数据进行排序（由 ORDER BY / GROUP BY / DISTINCT 触发）。大数据量排序会使用临时表空间，降低速度。建议通过索引来避免排序。"),
            "HAGR": ("哈希分组聚集", "通过构建哈希表执行 GROUP BY 聚合计算。速度通常较快，但会消耗较多内存。"),
            "HAGR2": ("哈希分组聚集", "通过构建哈希表执行 GROUP BY 聚合计算。速度通常较快，但会消耗较多内存。"),
            "AAGR": ("简单聚集", "在没有分组时计算聚集函数（如单独的 COUNT / SUM / AVG）。直接计算并输出单行结果。"),
            "AAGR2": ("简单聚集", "在没有分组时计算聚集函数（如单独的 COUNT / SUM / AVG）。直接计算并输出单行结果。"),
            "FAGR": ("快速聚集", "利用索引元数据快速计算 COUNT(*) 或 MAX/MIN。性能极高，不需要扫描全表。"),
            "FAGR2": ("快速聚集", "利用索引元数据快速计算 COUNT(*) 或 MAX/MIN。性能极高，不需要扫描全表。"),
            "NLJOIN": ("嵌套循环连接", "两表关联的一种方式。对外表的每一行，扫描一次内表。适用于外表行数极少、且内表关联列有索引的场景。若两表很大，性能极差。"),
            "NLJOIN2": ("嵌套循环连接", "两表关联的一种方式。对外表的每一行，扫描一次内表。适用于外表行数极少、且内表关联列有索引的场景。若两表很大，性能极差。"),
            "HJIN": ("哈希连接", "大表等值关联的常用方式。在内存中对小表构建哈希表，然后扫描大表进行匹配。速度较快，但较消耗内存。"),
            "HJIN2": ("哈希连接", "大表等值关联的常用方式。在内存中对小表构建哈希表，然后扫描大表进行匹配。速度较快，但较消耗内存。"),
            "MJIN": ("归并连接", "两表关联方式，两表均已按连接列排好序，像双指针一样合并。如果关联列有索引，性能极佳。"),
            "MJIN3": ("归并连接", "两表关联方式，两表均已按连接列排好序，像双指针一样合并。如果关联列有索引，性能极佳。"),
        }
        
        html = "<br/><h3>🔍 本计划包含算子名词释义 (通俗解说)</h3>"
        html += "<table style='width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 9.5pt;'>"
        html += "  <tr style='background-color: #f1f5f9;'>"
        html += "    <th style='border: 1px solid #cbd5e1; padding: 6px; text-align: left; width: 100px;'>算子名称</th>"
        html += "    <th style='border: 1px solid #cbd5e1; padding: 6px; text-align: left; width: 110px;'>标准中文名</th>"
        html += "    <th style='border: 1px solid #cbd5e1; padding: 6px; text-align: left;'>通俗运行解释与调优方针</th>"
        html += "  </tr>"
        
        found_any = False
        for op in sorted(cleaned_ops):
            if op in glossary:
                found_any = True
                ch_name, explain = glossary[op]
                html += f"  <tr>"
                html += f"    <td style='border: 1px solid #cbd5e1; padding: 6px; font-family: Consolas, monospace; font-weight: bold; color: #1e3a8a;'>{op}</td>"
                html += f"    <td style='border: 1px solid #cbd5e1; padding: 6px; font-weight: bold; color: #334155;'>{ch_name}</td>"
                html += f"    <td style='border: 1px solid #cbd5e1; padding: 6px; line-height: 1.5; color: #475569;'>{explain}</td>"
                html += f"  </tr>"
                
        html += "</table>"
        return html if found_any else ""

    def _parse_raw_explain_text(self, text: str) -> Optional[QueryResult]:
        """解析达梦数据库 EXPLAIN 原始表格输出文本"""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return None
        
        # 查找表头行
        header_idx = -1
        delimiter = None
        for idx, line in enumerate(lines):
            line_upper = line.upper()
            if "LEVEL_ID" in line_upper and "OPERATION" in line_upper:
                header_idx = idx
                if "|" in line:
                    delimiter = "|"
                elif "\t" in line:
                    delimiter = "\t"
                break
                
        if header_idx == -1:
            return None
            
        header_line = lines[header_idx]
        if delimiter:
            columns = [col.strip().upper() for col in header_line.split(delimiter)]
        else:
            columns = [col.strip().upper() for col in re.split(r'\s{2,}', header_line) if col.strip()]
            
        rows = []
        for line in lines[header_idx + 1:]:
            # 忽略分隔线 (例如 ---+---+---)
            if set(line.replace("+", "").replace("-", "").replace("|", "").replace(" ", "")) <= {""}:
                continue
            if delimiter:
                parts = [p.strip() for p in line.split(delimiter)]
            else:
                parts = [p.strip() for p in re.split(r'\s{2,}', line) if p.strip()]
                
            if len(parts) < len(columns):
                parts += ["NULL"] * (len(columns) - len(parts))
            else:
                parts = parts[:len(columns)]
                
            row_cells = []
            for p in parts:
                if p == "NULL" or p == "" or p.upper() == "NULL":
                    row_cells.append(None)
                else:
                    row_cells.append(p)
            rows.append(row_cells)
            
        return QueryResult(columns=columns, rows=rows, row_count=len(rows), elapsed_ms=0.0)

    def _on_import_plan_clicked(self):
        """导入外部执行计划文本进行离线分析的对话框"""
        from PySide6.QtWidgets import QDialog, QPlainTextEdit, QDialogButtonBox, QLabel
        
        dialog = QDialog(self)
        dialog.setWindowTitle("📥 导入外部达梦执行计划进行离线分析")
        dialog.setMinimumSize(700, 500)
        
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(QLabel(
            "请在下方粘贴从达梦 Manager、dmsql 或其他工具复制的原始 EXPLAIN 文本表格\n"
            "（需包含 LEVEL_ID, OPERATION 等列的表格）或缩进树文本："
        ))
        
        text_edit = QPlainTextEdit()
        text_edit.setPlaceholderText(
            "支持粘贴以下格式：\n"
            "1. 带有表头的原始表格文本，例如：\n"
            "PLAN_ID | LEVEL_ID | OPERATION | ...\n"
            "1       | 0        | NSET2     | ...\n\n"
            "2. 带行号或不带行号的层级缩进文本，例如：\n"
            " 1 | └─ NSET2\n"
            " 2 |   └─ PRJT2"
        )
        text_edit.setFont(QFont("Consolas", 10))
        dialog_layout.addWidget(text_edit)
        
        dialog_layout.addWidget(QLabel("（可选）请输入该执行计划对应的原始 SQL 语句（用于关联分析 WHERE/JOIN 条件）："))
        sql_edit = QPlainTextEdit()
        sql_edit.setMaximumHeight(100)
        sql_edit.setPlaceholderText("在此输入对应的 SQL 语句（留空则不进行条件映射关联）")
        sql_edit.setFont(QFont("Consolas", 10))
        dialog_layout.addWidget(sql_edit)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        dialog_layout.addWidget(button_box)
        
        if dialog.exec() == QDialog.Accepted:
            raw_text = text_edit.toPlainText().strip()
            sql_text = sql_edit.toPlainText().strip()
            if not raw_text:
                return
            
            # 解析导入
            query_result = self._parse_raw_explain_text(raw_text)
            from core.dm_connector import DMConnector
            from core.plan_analyzer import PlanAnalyzer
            
            dummy_conn = DMConnector(None)
            
            if query_result:
                plan_text = dummy_conn._format_explain(query_result)
                plan_raw_text = dummy_conn._format_raw_table(query_result)
            else:
                plan_text = raw_text
                plan_raw_text = "（离线直接导入层级缩进文本，无原始表格字段数据）"
                
            analyzer = PlanAnalyzer()
            plan_result = analyzer.analyze(plan_text, sql_text)
            
            self.show_results(
                plan_result=plan_result,
                plan_text=plan_text,
                plan_raw_text=plan_raw_text,
            )
            
            self.setCurrentWidget(self.plan_tab)
            
            parent = self.window()
            if hasattr(parent, "log"):
                parent.log("成功导入并离线分析外部执行计划文本！", "SUCCESS")
