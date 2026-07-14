"""
主窗口 - 布局与日志重构版

整合所有功能为多Tab布局，并使用Dock参考文档面板、Dock日志输出面板和菜单管理连接。
- Tab 1: SQL优化分析 (执行计划/索引/统计/规范/HINT)
- Tab 2: 动态监控 (慢SQL/会话/系统状态/锁等待/节点耗时)
- Tab 3: 配置与排查 (参数/排查指引/最佳实践)
- Tab 4: 文档知识库
"""
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMessageBox, QStatusBar, QTabWidget, QLabel, QComboBox,
    QPushButton, QDockWidget, QDialog, QFileDialog,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

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
from ui.widgets.connection_manager_dialog import ConnectionManagerDialog
from ui.widgets.sql_editor import SQLEditor
from ui.widgets.result_panel import ResultPanel
from ui.widgets.doc_info_widget import DocInfoWidget
from ui.widgets.log_panel import LogPanel
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
    log_message = Signal(str, str)  # 信号: (日志内容, 日志级别)

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
            self.log_message.emit("开始执行 SQL 深度优化分析...", "INFO")
            results = {}

            # 1. SQL写法规范检查
            self.log_message.emit("步骤 1/5: 正在进行 SQL 写法规范与静态缺陷审查...", "INFO")
            results["lint"] = self.sql_linter.lint(self.sql)
            if results["lint"] and results["lint"].rules:
                self.log_message.emit(f"SQL 规范检查完成，共发现 {len(results['lint'].rules)} 项不规范写法/潜在性能隐患。", "WARNING")
            else:
                self.log_message.emit("SQL 写法规范检查通过，符合开发最佳实践标准。", "SUCCESS")

            # 2. HINT建议
            self.log_message.emit("步骤 2/5: 正在扫描 SQL 结构生成 HINT 联接/路径优化建议...", "INFO")
            results["hints"] = self.hint_advisor.analyze(self.sql)
            self.log_message.emit("HINT 优化方案分析完成。", "INFO")

            # 3. 索引建议
            self.log_message.emit("步骤 3/5: 正在根据 WHERE / JOIN 条件分析物理索引匹配...", "INFO")
            results["index"] = self.index_advisor.analyze(self.sql)
            if results["index"] and results["index"].suggestions:
                self.log_message.emit(f"索引分析完成，已推荐创建 {len(results['index'].suggestions)} 个高价值索引以加速查询。", "SUCCESS")
            else:
                self.log_message.emit("索引匹配分析完成，当前索引已足够或无推荐索引。", "INFO")

            # 4. 执行计划分析
            self.log_message.emit("步骤 4/5: 正在连接达梦数据库获取动态执行计划树...", "INFO")
            plan_text = ""
            if self.connector and self.connector.is_connected:
                try:
                    plan_text = self.connector.get_explain_plan(self.sql)
                    self.log_message.emit("成功捕获执行计划文本，正在对其算子深度解析...", "INFO")
                    results["plan"] = self.plan_analyzer.analyze(plan_text)
                    if results["plan"] and results["plan"].issues:
                        self.log_message.emit(f"执行计划解析完成，识别到 {len(results['plan'].issues)} 处潜在严重的性能瓶颈（如全表扫描/笛卡尔积）。", "WARNING")
                    else:
                        self.log_message.emit("执行计划解析完成，算子树执行路径健康。", "SUCCESS")

                    # 5. 统计信息检查
                    self.log_message.emit("步骤 5/5: 正在提取关联表的元数据和统计信息更新状态...", "INFO")
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

                        table_stats_dict = {}
                        results["ddls"] = {}
                        for table_name in tables[:5]:
                            try:
                                self.log_message.emit(f"分析表 {table_name} 的统计时效性与数据量...", "INFO")
                                stats = self.connector.get_table_stats(table_name)
                                stats_result = self.stats_checker.check(stats, table_name)
                                if "stats_list" not in results:
                                    results["stats_list"] = []
                                results["stats_list"].append(stats_result)
                                table_stats_dict[table_name] = stats
                                
                                # 获取表的 DDL 定义
                                self.log_message.emit(f"提取表 {table_name} 的 DDL 结构定义...", "INFO")
                                ddl = self.connector.get_table_ddl(table_name)
                                results["ddls"][table_name] = ddl
                            except Exception as e:
                                self.log_message.emit(f"获取表 {table_name} 属性/DDL 异常: {e}", "WARNING")

                        if table_stats_dict:
                            try:
                                self.log_message.emit("结合所有关联表结构，进行联合多表索引优化建议分析...", "INFO")
                                enhanced_index = self.index_advisor.analyze(
                                    self.sql, table_stats_dict
                                )
                                results["index"] = enhanced_index
                            except Exception as e:
                                self.log_message.emit(f"生成优化索引建议异常: {e}", "WARNING")

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
                            
                            if merged.tables_stale > 0 or merged.tables_missing > 0:
                                self.log_message.emit(f"检查完毕：发现 {merged.tables_stale} 张表统计信息过期，{merged.tables_missing} 张表缺失统计信息，建议收集统计信息！", "WARNING")
                            else:
                                self.log_message.emit("检查完毕：关联表统计信息均未过期且处于最新健康状态。", "SUCCESS")

                except Exception as e:
                    results["plan_error"] = str(e)
                    self.log_message.emit(f"达梦执行计划抓取失败: {e}，将跳过执行计划分析和表统计校验。", "ERROR")
            else:
                results["plan_error"] = "未连接数据库，跳过执行计划分析和统计信息检查"
                self.log_message.emit("当前未连接到达梦数据库，已自动跳过步骤 4 (执行计划) 与步骤 5 (表统计校验)。", "WARNING")

            results["plan_text"] = plan_text
            self.log_message.emit("SQL深度优化分析流程全部完成。", "SUCCESS")
            self.finished.emit(results)

        except Exception as e:
            self.log_message.emit(f"优化分析后台线程异常中断: {e}", "ERROR")
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DM数据库SQL优化分析工具 v2.0")
        self.setMinimumSize(1300, 900)

        self.app_config = load_config()
        self.connector = None
        self.worker = None
        self.kb = DocKnowledgeBase()

        self._init_ui()
        self._init_menu()
        self._init_statusbar()
        
        self.log("DM SQL优化分析工具已就绪。")

    def log(self, text, level="INFO"):
        """追加运行日志"""
        if hasattr(self, 'log_panel') and self.log_panel:
            self.log_panel.append_log(text, level)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # 1. 顶部连接工具栏 (Connection Bar) - 窄条设计
        self.conn_bar = QWidget()
        self.conn_bar.setStyleSheet("""
            QWidget {
                background-color: #f1f5f9;
                border-bottom: 1px solid #cbd5e1;
            }
            QLabel {
                font-weight: bold;
                color: #475569;
            }
        """)
        conn_layout = QHBoxLayout(self.conn_bar)
        conn_layout.setContentsMargins(10, 6, 10, 6)
        conn_layout.setSpacing(10)

        conn_layout.addWidget(QLabel("数据库连接:"))
        self.conn_combo = QComboBox()
        self.conn_combo.setMinimumWidth(180)
        self._update_conn_combo()
        conn_layout.addWidget(self.conn_combo)

        self.btn_connect = QPushButton("连接")
        self.btn_connect.setStyleSheet("""
            QPushButton {
                background-color: #2563eb;
                color: white;
                font-weight: bold;
                padding: 4px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1d4ed8;
            }
        """)
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        conn_layout.addWidget(self.btn_connect)

        self.btn_manage_conn = QPushButton("管理连接...")
        self.btn_manage_conn.clicked.connect(self._on_manage_connections)
        conn_layout.addWidget(self.btn_manage_conn)

        self.conn_status_label = QLabel("● 未连接")
        self.conn_status_label.setStyleSheet("color: #64748b; font-weight: bold;")
        conn_layout.addWidget(self.conn_status_label)
        conn_layout.addStretch()

        main_layout.addWidget(self.conn_bar)

        # 2. 主Tab区域
        self.main_tabs = QTabWidget()
        self.main_tabs.currentChanged.connect(self._on_tab_changed)

        # Tab 1: SQL优化分析
        self._init_sql_analysis_tab()

        # Tab 2: 动态监控
        self._init_dynamic_monitor_tab()

        # Tab 3: 配置与排查
        self._init_troubleshoot_tab()

        # Tab 4: 文档知识库
        self._init_knowledge_tab()

        main_layout.addWidget(self.main_tabs, 1)

        # 3. 初始化右侧文档参考 Dock 面板
        self._init_doc_dock()

        # 4. 初始化底部运行日志 Dock 面板
        self._init_log_dock()

    def _init_sql_analysis_tab(self):
        """SQL优化分析Tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        # 左右分割: SQL编辑器 | 结果面板 (移除了原内嵌 doc_widget)
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
        self.monitor_tabs.currentChanged.connect(self._on_tab_changed)

        self.slow_sql_panel = SlowSQLPanel(self.connector, log_fn=self.log)
        self.slow_sql_panel.sql_selected.connect(self._on_sql_selected_from_monitor)
        self.monitor_tabs.addTab(self.slow_sql_panel, "慢SQL抓取")

        self.session_panel = SessionPanel(self.connector, log_fn=self.log)
        self.session_panel.sql_selected.connect(self._on_sql_selected_from_monitor)
        self.monitor_tabs.addTab(self.session_panel, "会话监控")

        self.system_panel = SystemStatusPanel(self.connector, log_fn=self.log)
        self.monitor_tabs.addTab(self.system_panel, "系统状态")

        self.lock_panel = LockWaitPanel(self.connector, log_fn=self.log)
        self.monitor_tabs.addTab(self.lock_panel, "锁和事务")

        self.node_panel = NodeTimingPanel(self.connector, log_fn=self.log)
        self.monitor_tabs.addTab(self.node_panel, "节点耗时分析")

        self.main_tabs.addTab(self.monitor_tabs, "📊 动态监控")

    def _init_troubleshoot_tab(self):
        """配置与排查Tab"""
        self.troubleshoot_tabs = QTabWidget()
        self.troubleshoot_tabs.currentChanged.connect(self._on_tab_changed)

        self.param_panel = ParamPanel(self.connector, log_fn=self.log)
        self.troubleshoot_tabs.addTab(self.param_panel, "配置参数")

        self.hint_panel = HintPanel(log_fn=self.log)
        self.troubleshoot_tabs.addTab(self.hint_panel, "HINT建议")

        self.trouble_panel = TroubleshootPanel(log_fn=self.log)
        self.troubleshoot_tabs.addTab(self.trouble_panel, "问题排查指引")

        self.practice_panel = SQLBestPracticePanel(log_fn=self.log)
        self.troubleshoot_tabs.addTab(self.practice_panel, "SQL最佳实践")

        self.main_tabs.addTab(self.troubleshoot_tabs, "🛠 配置与排查")

    def _init_knowledge_tab(self):
        """文档知识库Tab"""
        self.knowledge_panel = KnowledgePanel()
        self.main_tabs.addTab(self.knowledge_panel, "📚 文档知识库")

    def _init_doc_dock(self):
        """初始化右侧文档参考 Dock 窗口"""
        self.doc_dock = QDockWidget("文档参考", self)
        self.doc_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self.doc_widget = DocInfoWidget()
        self.doc_widget.sql_example_clicked.connect(self.sql_editor.set_sql)

        self.doc_dock.setWidget(self.doc_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.doc_dock)

        # 默认载入当前 Tab 对应文档
        self._update_context_doc()

    def _init_log_dock(self):
        """初始化底部运行日志 Dock 窗口"""
        self.log_dock = QDockWidget("运行日志", self)
        self.log_dock.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        
        self.log_panel = LogPanel(self)
        self.log_dock.setWidget(self.log_panel)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.log_dock)

    def _init_menu(self):
        menubar = self.menuBar()

        # 1. 文件菜单
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

        # 2. 数据库菜单
        db_menu = menubar.addMenu("数据库")
        manage_action = db_menu.addAction("连接设置...")
        manage_action.setShortcut("Ctrl+Shift+C")
        manage_action.triggered.connect(self._on_manage_connections)

        self.disconnect_action = db_menu.addAction("断开当前连接")
        self.disconnect_action.triggered.connect(self._disconnect_db)
        self.disconnect_action.setEnabled(False)

        # 3. 操作与导航菜单
        op_menu = menubar.addMenu("操作")
        analyze_action = op_menu.addAction("执行SQL分析")
        analyze_action.setShortcut("F5")
        analyze_action.triggered.connect(lambda: self._on_analyze(self.sql_editor.get_sql()))

        op_menu.addSeparator()

        monitor_menu = op_menu.addMenu("动态监控导航")
        m_slow = monitor_menu.addAction("慢SQL抓取")
        m_slow.triggered.connect(lambda: self._switch_tab(1, 0))
        m_sess = monitor_menu.addAction("会话监控")
        m_sess.triggered.connect(lambda: self._switch_tab(1, 1))
        m_sys = monitor_menu.addAction("系统状态")
        m_sys.triggered.connect(lambda: self._switch_tab(1, 2))
        m_lock = monitor_menu.addAction("锁和事务")
        m_lock.triggered.connect(lambda: self._switch_tab(1, 3))
        m_node = monitor_menu.addAction("节点耗时分析")
        m_node.triggered.connect(lambda: self._switch_tab(1, 4))

        trouble_menu = op_menu.addMenu("配置与排查导航")
        t_param = trouble_menu.addAction("配置参数")
        t_param.triggered.connect(lambda: self._switch_tab(2, 0))
        t_hint = trouble_menu.addAction("HINT建议")
        t_hint.triggered.connect(lambda: self._switch_tab(2, 1))
        t_guide = trouble_menu.addAction("问题排查指引")
        t_guide.triggered.connect(lambda: self._switch_tab(2, 2))
        t_best = trouble_menu.addAction("SQL最佳实践")
        t_best.triggered.connect(lambda: self._switch_tab(2, 3))

        # 4. 视图菜单
        view_menu = menubar.addMenu("视图")

        # 隐藏/显示连接栏
        self.show_conn_action = view_menu.addAction("显示数据库连接栏")
        self.show_conn_action.setCheckable(True)
        self.show_conn_action.setChecked(True)
        self.show_conn_action.triggered.connect(lambda checked: self.conn_bar.setVisible(checked))

        # 隐藏/显示右侧文档栏
        self.show_doc_action = view_menu.addAction("显示文档参考面板")
        self.show_doc_action.setCheckable(True)
        self.show_doc_action.setChecked(True)
        self.show_doc_action.triggered.connect(lambda checked: self.doc_dock.setVisible(checked))
        self.doc_dock.visibilityChanged.connect(self.show_doc_action.setChecked)

        # 隐藏/显示底部运行日志栏
        self.show_log_action = view_menu.addAction("显示运行日志面板")
        self.show_log_action.setCheckable(True)
        self.show_log_action.setChecked(True)
        self.show_log_action.triggered.connect(lambda checked: self.log_dock.setVisible(checked))
        self.log_dock.visibilityChanged.connect(self.show_log_action.setChecked)

        view_menu.addSeparator()

        zoom_in_action = view_menu.addAction("放大文档字体")
        zoom_in_action.setShortcut("Ctrl+=")
        zoom_in_action.triggered.connect(lambda: self.doc_widget.zoom_in())

        zoom_out_action = view_menu.addAction("缩小文档字体")
        zoom_out_action.setShortcut("Ctrl+-")
        zoom_out_action.triggered.connect(lambda: self.doc_widget.zoom_out())

        zoom_reset_action = view_menu.addAction("恢复默认字体")
        zoom_reset_action.setShortcut("Ctrl+0")
        zoom_reset_action.triggered.connect(lambda: self.doc_widget.reset_zoom())

        # 5. 帮助菜单
        help_menu = menubar.addMenu("帮助")
        about_action = help_menu.addAction("关于")
        about_action.triggered.connect(self._on_about)

    def _init_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("就绪 - 请连接DM数据库后使用")

    # ------------------------------------------------------------------
    # 数据库连接逻辑
    # ------------------------------------------------------------------

    def _update_conn_combo(self):
        """刷新下拉连接框"""
        self.conn_combo.clear()
        for conn in self.app_config.connections:
            self.conn_combo.addItem(conn.name)

        # 预选上次使用的连接
        for i, conn in enumerate(self.app_config.connections):
            if conn.name == self.app_config.connection.name:
                self.conn_combo.setCurrentIndex(i)
                break

    def _on_manage_connections(self):
        """打开连接管理器弹窗"""
        dialog = ConnectionManagerDialog(self.app_config, self)
        if dialog.exec() == QDialog.Accepted:
            self._update_conn_combo()
            # 弹窗点击“保存并连接”时，自动发起连接
            self._connect_db(self.app_config.connection)

    def _on_connect_clicked(self):
        """点击连接/断开按钮"""
        if self.connector and self.connector.is_connected:
            self._disconnect_db()
        else:
            idx = self.conn_combo.currentIndex()
            if 0 <= idx < len(self.app_config.connections):
                selected_conn = self.app_config.connections[idx]
                self._connect_db(selected_conn)

    def _connect_db(self, config: DMConnectionConfig):
        """连接数据库的具体实现"""
        self.status.showMessage("正在连接数据库...")
        self.log(f"开始尝试连接数据库: {config.name} ({config.host}:{config.port})...")
        
        self.btn_connect.setEnabled(False)
        self.btn_connect.setText("连接中...")
        self.repaint()

        self.app_config.connection = config
        self.connector = DMConnector(config)
        try:
            self.connector.connect()
            self._update_connectors()

            # 连接成功后: 自动隐藏顶部窄条连接栏
            self.conn_bar.setVisible(False)
            self.show_conn_action.setChecked(False)

            self.setWindowTitle(
                f"DM数据库SQL优化分析工具 v2.0 - 已连接: {config.user}@{config.host}:{config.port}"
            )
            self.status.showMessage(
                f"已连接到 {config.host}:{config.port} (用户: {config.user})"
            )

            # 更新菜单与按钮状态
            self.disconnect_action.setEnabled(True)
            self.btn_connect.setText("断开")
            self.conn_status_label.setText(f"● 已连接: {config.name}")
            self.conn_status_label.setStyleSheet("color: #16a34a; font-weight: bold;")
            
            self.log(f"成功连接至达梦数据库: {config.name} ({config.user}@{config.host}:{config.port})", "SUCCESS")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))
            self.status.showMessage("连接失败")
            self.log(f"连接数据库失败: {e}", "ERROR")
            self._disconnect_db()
        finally:
            self.btn_connect.setEnabled(True)

    def _disconnect_db(self):
        """断开连接的具体实现"""
        if self.connector:
            try:
                self.connector.disconnect()
            except Exception:
                pass
            self.connector = None

        self._update_connectors()

        # 断开后: 重新显示顶部连接栏
        self.conn_bar.setVisible(True)
        self.show_conn_action.setChecked(True)

        self.setWindowTitle("DM数据库SQL优化分析工具 v2.0")
        self.status.showMessage("已断开连接")
        self.log("已主动断开当前数据库连接。")

        # 重置按钮与状态栏文本
        self.disconnect_action.setEnabled(False)
        self.btn_connect.setText("连接")
        self.conn_status_label.setText("● 未连接")
        self.conn_status_label.setStyleSheet("color: #64748b; font-weight: bold;")

    def _update_connectors(self):
        """更新所有监控与排查面板的数据库连接器实例引用"""
        self.slow_sql_panel.connector = self.connector
        self.session_panel.connector = self.connector
        self.system_panel.connector = self.connector
        self.lock_panel.connector = self.connector
        self.node_panel.connector = self.connector
        self.param_panel.connector = self.connector

    # ------------------------------------------------------------------
    # SQL 分析与菜单路由
    # ------------------------------------------------------------------

    def _on_analyze(self, sql: str):
        self.result_panel.clear()
        self.status.showMessage("分析中...")
        
        self.log("=" * 60)
        self.log("收到新的 SQL 优化分析请求。")

        if not self.connector or not self.connector.is_connected:
            reply = QMessageBox.question(
                self, "未连接数据库",
                "当前未连接数据库，将仅执行SQL写法规范检查和HINT建议。\n"
                "执行计划分析和统计信息检查需要数据库连接。\n\n是否继续?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply == QMessageBox.No:
                self.log("分析已被取消。", "WARNING")
                return

        # 等待上一次分析线程结束
        if self.worker:
            try:
                if self.worker.isRunning():
                    self.log("正在等待上一分析线程释放...", "WARNING")
                    self.worker.wait(5000)
            except RuntimeError:
                self.worker = None

        self.worker = AnalyzeWorker(self.connector, sql)
        self.worker.log_message.connect(self.log)  # 关联日志槽
        self.worker.finished.connect(self._on_analyze_done)
        self.worker.error.connect(self._on_analyze_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_analyze_done(self, results: dict):
        self.worker = None
        self.result_panel.show_results(
            plan_result=results.get("plan"),
            index_result=results.get("index"),
            stats_result=results.get("stats"),
            lint_result=results.get("lint"),
            plan_text=results.get("plan_text", ""),
            error=results.get("plan_error") if not results.get("plan") else None,
            ddls=results.get("ddls"),
        )

        # 同步 SQL 到 HINT 面板
        if "hints" in results:
            self.hint_panel.set_sql(self.sql_editor.get_sql())

        if results.get("plan_error") and results.get("lint"):
            self.status.showMessage(f"部分分析完成: {results['plan_error']}")
        else:
            self.status.showMessage("分析完成")

    def _on_analyze_error(self, error: str):
        self.worker = None
        self.result_panel.show_results(error=error)
        self.status.showMessage("分析失败")
        self.log(f"分析异常终止，原因: {error}", "ERROR")

    def _on_sql_selected_from_monitor(self, sql: str):
        """从监控面板选择 SQL 时触发的快捷流程：加载、切Tab、自动分析"""
        if not sql or not sql.strip():
            return
        self.sql_editor.set_sql(sql)
        self._switch_tab(0)  # 切换到 SQL 优化分析 Tab
        self._on_analyze(sql)  # 自动开始 SQL 分析流程

    def _on_open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "打开SQL文件", "", "SQL文件 (*.sql);;所有文件 (*.*)"
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.sql_editor.set_sql(f.read())
                self.status.showMessage(f"已加载: {path}")
                self.log(f"成功打开并载入外部SQL文件: {path}")
            except Exception as e:
                QMessageBox.warning(self, "读取失败", str(e))
                self.log(f"加载SQL文件失败: {e}", "ERROR")

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
                self.log(f"成功将分析报告保存至: {path}", "SUCCESS")
            except Exception as e:
                QMessageBox.warning(self, "保存失败", str(e))
                self.log(f"保存分析报告失败: {e}", "ERROR")

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

    # ------------------------------------------------------------------
    # Tab 导航与右侧文档更新
    # ------------------------------------------------------------------

    def _on_tab_changed(self, index=0):
        """当主 Tab 或子 Tab 改变时触发"""
        self._update_context_doc()

    def _update_context_doc(self):
        """根据当前激活的 Tab 自动更新右侧的 Dock 文档"""
        if not hasattr(self, 'main_tabs') or not hasattr(self, 'doc_widget'):
            return

        main_idx = self.main_tabs.currentIndex()
        sub_idx = None

        if main_idx == 1:
            sub_idx = self.monitor_tabs.currentIndex()
        elif main_idx == 2:
            sub_idx = self.troubleshoot_tabs.currentIndex()

        # 定义 Tab 到 文档Snippet Key 的映射
        TAB_DOC_MAPPING = {
            (0, None): "plan_explain",       # SQL优化分析
            (1, 0): "slow_sql",              # 慢SQL抓取
            (1, 1): "session_monitor",       # 会话监控
            (1, 2): "system_status",         # 系统状态
            (1, 3): "lock_wait",             # 锁和事务监控
            (1, 4): "node_timing",           # 执行节点耗时分析
            (2, 0): "param_check",           # 配置参数检查
            (2, 1): "hint_advisor",          # HINT建议
            (2, 2): "troubleshoot",          # 问题排查流程
            (2, 3): "sql_best_practice",     # 达梦最佳SQL开发实践
        }

        doc_key = TAB_DOC_MAPPING.get((main_idx, sub_idx)) or TAB_DOC_MAPPING.get((main_idx, None))
        if doc_key:
            snippet = self.kb.get(doc_key)
            self.doc_widget.set_snippet(snippet)

    def _switch_tab(self, main_idx, sub_idx=None):
        """供菜单项调用的导航跳转函数"""
        self.main_tabs.setCurrentIndex(main_idx)
        if sub_idx is not None:
            if main_idx == 1:
                self.monitor_tabs.setCurrentIndex(sub_idx)
            elif main_idx == 2:
                self.troubleshoot_tabs.setCurrentIndex(sub_idx)

    def closeEvent(self, event):
        if self.connector and self.connector.is_connected:
            try:
                self.connector.disconnect()
            except Exception:
                pass
        event.accept()
