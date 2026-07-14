"""
主窗口 - 重构版

整合所有功能为多Tab布局:
- Tab 1: SQL优化分析 (执行计划/索引/统计/规范/HINT)
- Tab 2: 动态监控 (慢SQL/会话/系统状态/锁等待/节点耗时)
- Tab 3: 配置与排查 (参数/排查指引/最佳实践)
- Tab 4: 文档知识库
"""
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMessageBox, QStatusBar, QMenuBar, QMenu,
    QFileDialog, QTabWidget, QLabel,
)
from PySide6.QtCore import Qt, QThread, Signal
from pathlib import Path
import sys

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import DMConnectionConfig, load_config, save_config, AppConfig
from core.dm_connector import DMConnector
from core.plan_analyzer import PlanAnalyzer
from core.index_advisor import IndexAdvisor
from core.stats_checker import StatsChecker
from core.sql_linter import SQLLinter
from core.troubleshoot import HintAdvisor
from core.doc_knowledge import DocKnowledgeBase
from ui.widgets.connection_panel import ConnectionPanel
from ui.widgets.sql_editor import SQLEditor
from ui.widgets.result_panel import ResultPanel
from ui.widgets.doc_info_widget import DocInfoWidget
from ui.widgets.dynamic_view_panels import (
    SlowSQLPanel, SessionPanel, SystemStatusPanel,
    LockWaitPanel, NodeTimingPanel,
)
from ui.widgets.troubleshoot_panels import (
    ParamPanel, HintPanel, TroubleshootPanel, SQLBestPracticePanel,
)
from ui.widgets.knowledge_panel import KnowledgePanel


class AnalyzeWorker(QThread):
    """后台分析线程"""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, connector: DMConnector, sql: str):
        super().__init__()
        self.connector = connector
        self.sql = sql
        self.plan_analyzer = PlanAnalyzer()
        self.index_advisor = IndexAdvisor()
        self.stats_checker = StatsChecker()
        self.sql_linter = SQLLinter()
        self.hint_advisor = HintAdvisor()

    def run(self):
        try:
            results = {}

            # 1. SQL写法规范检查
            results["lint"] = self.sql_linter.lint(self.sql)

            # 2. HINT建议
            results["hints"] = self.hint_advisor.analyze(self.sql)

            # 3. 索引建议
            results["index"] = self.index_advisor.analyze(self.sql)

            # 4. 执行计划分析
            plan_text = ""
            if self.connector and self.connector.is_connected:
                try:
                    plan_text = self.connector.get_explain_plan(self.sql)
                    results["plan"] = self.plan_analyzer.analyze(plan_text)

                    # 5. 统计信息检查
                    import sqlparse
                    if sqlparse:
                        parsed = sqlparse.parse(self.sql)[0]
                        tables = []
                        from_seen = False
                        for token in parsed.tokens:
                            if token.is_keyword and token.value.upper() in ("FROM", "JOIN", "UPDATE", "INTO"):
                                from_seen = True
                                continue
                            if token.is_keyword and token.value.upper() in ("WHERE", "GROUP", "ORDER", "SET", "HAVING", "LIMIT"):
                                from_seen = False
                                continue
                            if from_seen:
                                from sqlparse.sql import IdentifierList, Identifier
                                if isinstance(token, IdentifierList):
                                    for identifier in token.get_identifiers():
                                        name = identifier.get_real_name()
                                        if name and name.upper() not in ("SELECT",):
                                            tables.append(name)
                                elif isinstance(token, Identifier):
                                    name = token.get_real_name() if hasattr(token, 'get_real_name') else str(token)
                                    if name and name.upper() not in ("SELECT",):
                                        tables.append(name)

                        for table_name in tables[:5]:
                            try:
                                stats = self.connector.get_table_stats(table_name)
                                stats_result = self.stats_checker.check(stats, table_name)
                                if "stats_list" not in results:
                                    results["stats_list"] = []
                                results["stats_list"].append(stats_result)

                                table_stats_dict = {table_name: stats}
                                enhanced_index = self.index_advisor.analyze(
                                    self.sql, table_stats_dict
                                )
                                results["index"] = enhanced_index
                            except Exception:
                                pass

                        if "stats_list" in results and results["stats_list"]:
                            from core.stats_checker import StatsCheckResult
                            merged = StatsCheckResult()
                            for sr in results["stats_list"]:
                                merged.issues.extend(sr.issues)
                                merged.tables_checked += sr.tables_checked
                                merged.tables_ok += sr.tables_ok
                                merged.tables_stale += sr.tables_stale
                                merged.tables_missing += sr.tables_missing
                            if merged.tables_checked > 0:
                                merged.summary = f"共检查 {merged.tables_checked} 张表的统计信息\n"
                                merged.summary += f"正常: {merged.tables_ok} | "
                                merged.summary += f"过期: {merged.tables_stale} | "
                                merged.summary += f"缺失: {merged.tables_missing}\n"
                                critical = sum(1 for i in merged.issues if i.level == "CRITICAL")
                                warning = sum(1 for i in merged.issues if i.level == "WARNING")
                                merged.summary += f"问题: 严重{critical} | 警告{warning}"
                            results["stats"] = merged

                except Exception as e:
                    results["plan_error"] = str(e)
            else:
                results["plan_error"] = "未连接数据库，跳过执行计划分析和统计信息检查"

            results["plan_text"] = plan_text
            self.finished.emit(results)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DM数据库SQL优化分析工具 v2.0")
        self.setMinimumSize(1300, 850)

        self.app_config = load_config()
        self.connector = None
        self.worker = None
        self.kb = DocKnowledgeBase()

        self._init_ui()
        self._init_menu()
        self._init_statusbar()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # 顶部连接面板
        self.conn_panel = ConnectionPanel(self.app_config.connection)
        self.conn_panel.connect_requested.connect(self._on_connect)
        main_layout.addWidget(self.conn_panel)

        # 主Tab区域
        self.main_tabs = QTabWidget()

        # Tab 1: SQL优化分析
        self._init_sql_analysis_tab()

        # Tab 2: 动态监控
        self._init_dynamic_monitor_tab()

        # Tab 3: 配置与排查
        self._init_troubleshoot_tab()

        # Tab 4: 文档知识库
        self._init_knowledge_tab()

        main_layout.addWidget(self.main_tabs, 1)

    def _init_sql_analysis_tab(self):
        """SQL优化分析Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 文档信息(执行计划解读)
        doc_widget = DocInfoWidget(self.kb.get("plan_explain"))
        doc_widget.setMaximumHeight(200)
        layout.addWidget(doc_widget)

        # 左右分割: SQL编辑器 | 结果面板
        splitter = QSplitter(Qt.Horizontal)
        self.sql_editor = SQLEditor()
        self.sql_editor.analyze_requested.connect(self._on_analyze)
        splitter.addWidget(self.sql_editor)

        self.result_panel = ResultPanel()
        splitter.addWidget(self.result_panel)
        splitter.setSizes([450, 650])
        layout.addWidget(splitter, 1)

        self.main_tabs.addTab(widget, "🔍 SQL优化分析")

    def _init_dynamic_monitor_tab(self):
        """动态监控Tab"""
        self.monitor_tabs = QTabWidget()

        self.slow_sql_panel = SlowSQLPanel(self.connector)
        self.monitor_tabs.addTab(self.slow_sql_panel, "慢SQL抓取")

        self.session_panel = SessionPanel(self.connector)
        self.monitor_tabs.addTab(self.session_panel, "会话监控")

        self.system_panel = SystemStatusPanel(self.connector)
        self.monitor_tabs.addTab(self.system_panel, "系统状态")

        self.lock_panel = LockWaitPanel(self.connector)
        self.monitor_tabs.addTab(self.lock_panel, "锁和事务")

        self.node_panel = NodeTimingPanel(self.connector)
        self.monitor_tabs.addTab(self.node_panel, "节点耗时分析")

        self.main_tabs.addTab(self.monitor_tabs, "📊 动态监控")

    def _init_troubleshoot_tab(self):
        """配置与排查Tab"""
        self.troubleshoot_tabs = QTabWidget()

        self.param_panel = ParamPanel(self.connector)
        self.troubleshoot_tabs.addTab(self.param_panel, "配置参数")

        self.hint_panel = HintPanel()
        self.troubleshoot_tabs.addTab(self.hint_panel, "HINT建议")

        self.trouble_panel = TroubleshootPanel()
        self.troubleshoot_tabs.addTab(self.trouble_panel, "问题排查指引")

        self.practice_panel = SQLBestPracticePanel()
        self.troubleshoot_tabs.addTab(self.practice_panel, "SQL最佳实践")

        self.main_tabs.addTab(self.troubleshoot_tabs, "🛠 配置与排查")

    def _init_knowledge_tab(self):
        """文档知识库Tab"""
        self.knowledge_panel = KnowledgePanel()
        self.main_tabs.addTab(self.knowledge_panel, "📚 文档知识库")

    def _init_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("文件")
        open_action = file_menu.addAction("打开SQL文件...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_file)

        save_action = file_menu.addAction("保存分析报告...")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save_report)

        file_menu.addSeparator()
        exit_action = file_menu.addAction("退出")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        help_menu = menubar.addMenu("帮助")
        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self._on_about)

    def _init_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪 - 请连接DM数据库后使用")

    # ------------------------------------------------------------------
    # 事件处理
    # ------------------------------------------------------------------

    def _on_connect(self, config: DMConnectionConfig):
        if self.connector and self.connector.is_connected:
            self.connector.disconnect()
            self.conn_panel.set_connected(False)
            self.status.showMessage("已断开连接")
            return

        self.app_config.connection = config
        self.connector = DMConnector(config)
        try:
            self.connector.connect()
            self.conn_panel.set_connected(True)
            save_config(self.app_config)

            # 更新各面板的connector引用
            self._update_connectors()
            self.status.showMessage(
                f"已连接到 {config.host}:{config.port} (用户: {config.user})"
            )
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            self.status.showMessage("连接失败")

    def _update_connectors(self):
        """更新各功能面板的数据库连接器"""
        self.slow_sql_panel.connector = self.connector
        self.session_panel.connector = self.connector
        self.system_panel.connector = self.connector
        self.lock_panel.connector = self.connector
        self.node_panel.connector = self.connector
        self.param_panel.connector = self.connector

    def _on_analyze(self, sql: str):
        self.result_panel.clear()
        self.status.showMessage("分析中...")

        if not self.connector or not self.connector.is_connected:
            reply = QMessageBox.question(
                self, "未连接数据库",
                "当前未连接数据库，将仅执行SQL写法规范检查和HINT建议。\n"
                "执行计划分析和统计信息检查需要数据库连接。\n\n是否继续?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.No:
                return

        # 等待前一个分析线程完成
        if self.worker and self.worker.isRunning():
            self.worker.wait(5000)

        self.worker = AnalyzeWorker(self.connector, sql)
        self.worker.finished.connect(self._on_analyze_done)
        self.worker.error.connect(self._on_analyze_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_analyze_done(self, results: dict):
        self.result_panel.show_results(
            plan_result=results.get("plan"),
            index_result=results.get("index"),
            stats_result=results.get("stats"),
            lint_result=results.get("lint"),
            plan_text=results.get("plan_text", ""),
            error=results.get("plan_error") if not results.get("plan") else None,
        )

        # 同步SQL到HINT面板
        if "hints" in results:
            self.hint_panel.set_sql(self.sql_editor.get_sql())

        if results.get("plan_error") and results.get("lint"):
            self.status.showMessage(f"部分分析完成: {results['plan_error']}")
        else:
            self.status.showMessage("分析完成")

    def _on_analyze_error(self, error: str):
        self.result_panel.show_results(error=error)
        self.status.showMessage("分析失败")

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开SQL文件", "", "SQL文件 (*.sql);;所有文件 (*.*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.sql_editor.set_sql(f.read())
                self.status.showMessage(f"已加载: {path}")
            except Exception as e:
                QMessageBox.warning(self, "读取失败", str(e))

    def _on_save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存报告", "sql_analysis_report.txt", "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if path:
            try:
                report = self._generate_text_report()
                with open(path, "w", encoding="utf-8") as f:
                    f.write(report)
                self.status.showMessage(f"报告已保存: {path}")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", str(e))

    def _generate_text_report(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("DM数据库SQL优化分析报告")
        lines.append("=" * 70)
        lines.append("")
        overview = self.result_panel.overview_tab.toPlainText()
        if overview:
            lines.append("[总览]")
            lines.append(overview)
            lines.append("")
        plan_text = self.result_panel.plan_text.toPlainText()
        if plan_text:
            lines.append("[执行计划]")
            lines.append(plan_text)
            lines.append("")
        stats_text = self.result_panel.stats_tab.toPlainText()
        if stats_text:
            lines.append("[统计信息]")
            lines.append(stats_text)
            lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)

    def _on_about(self):
        QMessageBox.about(
            self, "关于",
            "<h3>DM数据库SQL优化分析工具 v2.0</h3>"
            "<p>基于达梦官方文档开发，集成以下功能:</p>"
            "<ul>"
            "<li>SQL优化分析 (执行计划/索引/统计/规范/HINT)</li>"
            "<li>动态监控 (慢SQL/会话/系统状态/锁等待/节点耗时)</li>"
            "<li>配置与排查 (参数检查/HINT建议/排查指引/最佳实践)</li>"
            "<li>文档知识库 (5份达梦官方文档知识嵌入)</li>"
            "</ul>"
            "<p>文档来源: eco.dameng.com</p>"
        )

    def closeEvent(self, event):
        if self.connector and self.connector.is_connected:
            self.connector.disconnect()
        event.accept()
