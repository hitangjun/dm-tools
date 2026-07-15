"""
动态管理视图功能面板

包含: 慢SQL抓取、会话监控、执行节点耗时、系统状态、锁等待
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QPlainTextEdit, QLabel,
    QPushButton, QSpinBox, QHeaderView,
    QMessageBox, QSplitter, QApplication, QLineEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

from core.dm_connector import DMConnector
from core.dynamic_views import DynamicViewManager



class DynamicViewWorker(QThread):
    """动态视图查询后台线程"""
    finished = Signal(str, object)  # (task_name, result_data)
    error = Signal(str, str)        # (task_name, error_msg)

    def __init__(self, connector: DMConnector, task: str, params: dict = None):
        super().__init__()
        self.connector = connector
        self.task = task
        self.params = params or {}
        self.manager = DynamicViewManager(connector)

    def run(self):
        try:
            if self.task == "slow_sql":
                data = self.manager.get_slow_sqls(self.params.get("limit", 20))
                self.finished.emit("slow_sql", data)
            elif self.task == "system_slow_sql":
                data = self.manager.get_system_slow_sqls()
                self.finished.emit("system_slow_sql", data)
            elif self.task == "sql_history":
                data = self.manager.get_sql_history(self.params.get("limit", 50))
                self.finished.emit("sql_history", data)
            elif self.task == "sessions":
                data = self.manager.get_sessions(
                    self.params.get("active_only", False),
                    schema_filter=self.params.get("schema_filter", ""),
                )
                self.finished.emit("sessions", data)
            elif self.task == "node_timing":
                exec_id = self.params.get("exec_id", 0)
                if exec_id == 0:
                    exec_id = self.manager.get_latest_exec_id()
                data = self.manager.get_node_timing(exec_id)
                self.finished.emit("node_timing", data)
            elif self.task == "system_status":
                data = self.manager.get_system_status()
                self.finished.emit("system_status", data)
            elif self.task == "locks":
                locks = self.manager.get_locks()
                waits = self.manager.get_trx_waits()
                trxs = self.manager.get_active_transactions()
                self.finished.emit("locks", {"locks": locks, "waits": waits, "trxs": trxs})
        except Exception as e:
            self.error.emit(self.task, str(e))


class SlowSQLPanel(QWidget):
    """慢SQL抓取面板"""
    sql_selected = Signal(str)  # 双击或点击载入时发射信号

    def __init__(self, connector: DMConnector, log_fn=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.log_fn = log_fn
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 操作栏
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("获取条数:"))
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(1, 1000)
        self.limit_spin.setValue(20)
        toolbar.addWidget(self.limit_spin)

        self.btn_long = QPushButton("查询最近慢SQL")
        self.btn_long.clicked.connect(lambda: self._query("slow_sql"))
        toolbar.addWidget(self.btn_long)

        self.btn_system = QPushButton("查询系统最慢SQL")
        self.btn_system.clicked.connect(lambda: self._query("system_slow_sql"))
        toolbar.addWidget(self.btn_system)

        self.btn_history = QPushButton("查询SQL历史")
        self.btn_history.clicked.connect(lambda: self._query("sql_history"))
        toolbar.addWidget(self.btn_history)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 上下分割器
        splitter = QSplitter(Qt.Vertical)

        # 上半部分: Tree列表
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["序号", "耗时(ms)", "执行时间", "SQL文本"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tree.currentItemChanged.connect(self._on_row_selected)
        self.tree.itemDoubleClicked.connect(lambda item, col: self._send_sql())
        # 右键上下文菜单
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        splitter.addWidget(self.tree)

        # 下半部分: 选中SQL详情和参数
        detail_widget = QWidget()
        detail_layout = QVBoxLayout(detail_widget)
        detail_layout.setContentsMargins(0, 5, 0, 0)

        detail_tb = QHBoxLayout()
        detail_tb.addWidget(QLabel("<b>选中SQL详情与绑定变量参数:</b>"))
        detail_tb.addStretch()

        self.btn_copy_sql = QPushButton("复制完整SQL")
        self.btn_copy_sql.clicked.connect(self._copy_sql)
        self.btn_copy_sql.setEnabled(False)
        detail_tb.addWidget(self.btn_copy_sql)

        self.btn_send_sql = QPushButton("载入主编辑器")
        self.btn_send_sql.clicked.connect(self._send_sql)
        self.btn_send_sql.setEnabled(False)
        detail_tb.addWidget(self.btn_send_sql)

        detail_layout.addLayout(detail_tb)

        # 左右分割: 左侧 SQL，右侧绑定参数
        detail_splitter = QSplitter(Qt.Horizontal)

        self.sql_detail = QPlainTextEdit()
        self.sql_detail.setReadOnly(True)
        self.sql_detail.setFont(QFont("Consolas", 11))
        self.sql_detail.setPlaceholderText("在上方列表中选择一行以查看完整 SQL 文本")
        detail_splitter.addWidget(self.sql_detail)

        self.param_detail = QPlainTextEdit()
        self.param_detail.setReadOnly(True)
        self.param_detail.setFont(QFont("Consolas", 11))
        self.param_detail.setPlaceholderText("选择上方执行历史行以提取绑定参数\n(注：数据库端需开启 ENABLE_MONITOR_BP = 1 监控)")
        detail_splitter.addWidget(self.param_detail)

        detail_splitter.setSizes([750, 450])
        detail_layout.addWidget(detail_splitter)

        splitter.addWidget(detail_widget)
        splitter.setSizes([450, 250])
        layout.addWidget(splitter, 1)

    def _query(self, task_name):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker:
            try:
                if self.worker.isRunning():
                    self.worker.wait(3000)
            except RuntimeError:
                self.worker = None

        if self.log_fn:
            self.log_fn(f"正在执行数据库监控查询: {task_name}...")

        self.tree.clear()
        params = {"limit": self.limit_spin.value()} if task_name == "slow_sql" else {}
        self.worker = DynamicViewWorker(self.connector, task_name, params)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
        self.worker = None
        self.tree.clear()
        self.sql_detail.clear()
        self.param_detail.clear()
        self.btn_copy_sql.setEnabled(False)
        self.btn_send_sql.setEnabled(False)

        for i, item in enumerate(data):
            tree_item = QTreeWidgetItem([
                str(i + 1),
                str(item.elapsed_ms),
                item.exec_time,
                item.sql_text[:200].replace("\n", " "),
            ])
            # 存储完整数据到 column 0 (最稳健)
            tree_item.setData(0, Qt.UserRole, item.sql_text)
            tree_item.setData(0, Qt.UserRole + 1, item.exec_id)
            
            # 高亮耗时长的SQL
            if item.elapsed_ms > 5000:
                tree_item.setForeground(1, QColor("#dc2626"))
            elif item.elapsed_ms > 1000:
                tree_item.setForeground(1, QColor("#f59e0b"))
            self.tree.addTopLevelItem(tree_item)
            
        if self.log_fn:
            self.log_fn(f"监控查询 {task_name} 执行完毕，获取到 {len(data)} 条数据。", "SUCCESS")

    def _on_error(self, task_name, error):
        self.worker = None
        if self.log_fn:
            self.log_fn(f"监控查询 {task_name} 失败: {error}", "ERROR")
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")

    def _on_row_selected(self, current, previous):
        if not current:
            self.sql_detail.clear()
            self.param_detail.clear()
            self.btn_copy_sql.setEnabled(False)
            self.btn_send_sql.setEnabled(False)
            return

        sql = current.data(0, Qt.UserRole)
        exec_id = current.data(0, Qt.UserRole + 1)

        self.sql_detail.setPlainText(sql)
        self.btn_copy_sql.setEnabled(True)
        self.btn_send_sql.setEnabled(True)

        self.param_detail.setPlainText("正在拉取/提取绑定变量参数...")
        self._query_bind_params(exec_id, sql)

    def _query_bind_params(self, exec_id, sql=None):
        if not self.connector or not self.connector.is_connected:
            self.param_detail.setPlainText("未连接数据库，无法获取参数。")
            return
        try:
            # 针对慢 SQL (无 exec_id) 进行 SQL 模糊特征历史搜索匹配
            if (not exec_id or exec_id == "0" or exec_id == "") and sql:
                cleaned_sql = sql.strip().replace("'", "''")
                # 取出前150个字符作为搜索特征值
                search_frag = " ".join(cleaned_sql.split())[:150]
                
                res_exec = self.connector.execute(f"""
                    SELECT TOP 1 EXEC_ID
                    FROM V$SQL_HISTORY
                    WHERE TOP_SQL_TEXT LIKE '%{search_frag}%'
                    ORDER BY START_TIME DESC
                """)
                if not res_exec.error and res_exec.rows and res_exec.rows[0][0]:
                    exec_id = res_exec.rows[0][0]

            if not exec_id or exec_id == "0" or exec_id == "":
                self.param_detail.setPlainText("当前记录无执行号 (EXEC_ID)，且在归档历史中未搜索到匹配项。\n\n提示：\n1. 达梦仅对使用了 ? 或 :name 占位符的参数化 SQL 记录绑定值；\n2. 需确保已开启达梦系统级变量监控 ENABLE_MONITOR_BP = 1")
                return

            res = self.connector.execute(f"""
                SELECT SF_EXTRACT_BIND_DATA_NUM(BINDDATA, 1)
                FROM V$SQL_BINDDATA_HISTORY
                WHERE EXEC_ID = {exec_id}
            """)
            if res.error or not res.rows or res.rows[0][0] is None:
                self.param_detail.setPlainText("未检索到当前执行的绑定变量参数。\n\n可能原因：\n1. 该查询未使用绑定变量占位符；\n2. 数据库参数 ENABLE_MONITOR_BP 未启用 (当前为0)；\n3. 该历史参数数据已被系统清理回收。")
                return

            num_binds = int(res.rows[0][0])
            params = []
            for i in range(1, num_binds + 1):
                char_res = self.connector.execute(f"""
                    SELECT SF_EXTRACT_BIND_DATA_CHAR(BINDDATA, {i})
                    FROM V$SQL_BINDDATA_HISTORY
                    WHERE EXEC_ID = {exec_id}
                """)
                if not char_res.error and char_res.rows:
                    val = char_res.rows[0][0]
                    params.append(f"参数 #{i}: {val}")
                else:
                    params.append(f"参数 #{i}: [提取失败或不支持的二进制数据]")

            self.param_detail.setPlainText("\n".join(params))
            if self.log_fn:
                self.log_fn(f"成功获取执行号 {exec_id} 的 {num_binds} 个绑定变量参数。", "SUCCESS")
        except Exception as e:
            self.param_detail.setPlainText(f"获取参数失败: {e}")
            if self.log_fn:
                self.log_fn(f"获取绑定变量异常: {e}", "ERROR")

    def _copy_sql(self):
        sql = self.sql_detail.toPlainText().strip()
        if sql:
            QApplication.clipboard().setText(sql)
            if self.log_fn:
                self.log_fn("选中 SQL 文本已成功复制到剪贴板。", "SUCCESS")

    def _send_sql(self):
        sql = self.sql_detail.toPlainText().strip()
        if sql:
            self.sql_selected.emit(sql)
            if self.log_fn:
                self.log_fn("已成功将选中 SQL 载入 SQL 优化分析编辑器。")

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self)
        sql = item.data(0, Qt.UserRole)
        
        act_analyze = QAction("🔬 分析此 SQL", self)
        act_analyze.setEnabled(bool(sql and sql.strip()))
        act_analyze.triggered.connect(lambda: self.sql_selected.emit(sql))
        menu.addAction(act_analyze)
        
        menu.addSeparator()
        
        act_copy = QAction("📄 复制完整 SQL", self)
        act_copy.setEnabled(bool(sql and sql.strip()))
        act_copy.triggered.connect(self._copy_sql)
        menu.addAction(act_copy)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))


class SessionPanel(QWidget):
    """会话监控面板"""
    sql_selected = Signal(str)       # 会话右键 -> 分析此SQL
    jump_to_node = Signal(str)       # 会话右键 -> 跳转节点耗时分析(传递 sess_id)

    def __init__(self, connector: DMConnector, log_fn=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.log_fn = log_fn
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_all = QPushButton("查询所有会话")
        self.btn_all.clicked.connect(lambda: self._query(False))
        toolbar.addWidget(self.btn_all)

        self.btn_active = QPushButton("仅活跃会话")
        self.btn_active.setStyleSheet("QPushButton { background-color: #fef3c7; }")
        self.btn_active.clicked.connect(lambda: self._query(True))
        toolbar.addWidget(self.btn_active)

        toolbar.addWidget(QLabel("  SCHEMA过滤:"))
        self.schema_input = QLineEdit()
        self.schema_input.setPlaceholderText("输入SCHEMA名称过滤(留空=全部)")
        self.schema_input.setMaximumWidth(200)
        self.schema_input.setClearButtonEnabled(True)
        toolbar.addWidget(self.schema_input)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["会话ID", "SCHEMA", "状态", "创建时间", "客户端", "SQL文本"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(5, QHeaderView.Stretch)
        # 右键上下文菜单
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

    def _query(self, active_only):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker:
            try:
                if self.worker.isRunning():
                    self.worker.wait(3000)
            except RuntimeError:
                self.worker = None

        schema = self.schema_input.text().strip()
        if self.log_fn:
            extra = f", SCHEMA={schema}" if schema else ""
            self.log_fn(f"正在查询会话信息 (仅活跃: {active_only}{extra})...")

        self.tree.clear()
        self.worker = DynamicViewWorker(
            self.connector, "sessions",
            {"active_only": active_only, "schema_filter": schema},
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
        self.worker = None
        self.tree.clear()
        for item in data:
            tree_item = QTreeWidgetItem([
                item.sess_id, item.curr_sch, item.state, item.create_time,
                item.clnt_host,
                item.sql_text[:200].replace("\n", " "),
            ])
            # 将完整 SQL 存入 column 0
            tree_item.setData(0, Qt.UserRole, item.sql_text)
            if item.state == "ACTIVE":
                tree_item.setForeground(2, QColor("#dc2626"))
            self.tree.addTopLevelItem(tree_item)
        if self.log_fn:
            self.log_fn(f"会话监控查询完成，共 {len(data)} 个活动会话。", "SUCCESS")

    def _on_error(self, task_name, error):
        self.worker = None
        if self.log_fn:
            self.log_fn(f"会话监控查询失败: {error}", "ERROR")
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        
        from PySide6.QtWidgets import QMenu
        from PySide6.QtGui import QAction
        
        menu = QMenu(self)
        sql = item.data(0, Qt.UserRole)
        sess_id = item.text(0)
        
        act_analyze = QAction("🔬 分析此会话 SQL", self)
        act_analyze.setEnabled(bool(sql and sql.strip()))
        act_analyze.triggered.connect(lambda: self.sql_selected.emit(sql))
        menu.addAction(act_analyze)

        act_node = QAction("📊 跳转节点耗时分析", self)
        act_node.setEnabled(bool(sess_id))
        act_node.triggered.connect(lambda: self.jump_to_node.emit(sess_id))
        menu.addAction(act_node)
        
        menu.addSeparator()
        
        act_copy_sql = QAction("📄 复制会话 SQL", self)
        act_copy_sql.setEnabled(bool(sql and sql.strip()))
        act_copy_sql.triggered.connect(lambda: self._copy_text(sql))
        menu.addAction(act_copy_sql)
        
        act_copy_id = QAction("🆔 复制会话 ID", self)
        act_copy_id.triggered.connect(lambda: self._copy_text(sess_id))
        menu.addAction(act_copy_id)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _copy_text(self, text):
        if text:
            QApplication.clipboard().setText(text)
            if self.log_fn:
                self.log_fn("文本已成功复制到剪贴板。", "SUCCESS")


class SystemStatusPanel(QWidget):
    """系统状态检查面板"""

    def __init__(self, connector: DMConnector, log_fn=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.log_fn = log_fn
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 刷新系统状态")
        self.btn_refresh.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; font-weight: bold; padding: 6px 15px; }"
        )
        self.btn_refresh.clicked.connect(self._query)
        toolbar.addWidget(self.btn_refresh)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 10))
        layout.addWidget(self.result_text)

    def _query(self):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker:
            try:
                if self.worker.isRunning():
                    self.worker.wait(3000)
            except RuntimeError:
                self.worker = None

        if self.log_fn:
            self.log_fn("正在获取系统状态参数和命中率指标...")

        self.result_text.setPlainText("查询中...")
        self.worker = DynamicViewWorker(self.connector, "system_status")
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
        self.worker = None
        text = "═══ 系统状态 ═══\n\n"
        text += f"实例名: {data.instance_name}\n"
        text += f"版本: {data.version}\n"
        text += f"启动时间: {data.start_time}\n"
        status_color = "正常 ✅" if data.status == "OPEN" else f"异常 ❌ ({data.status})"
        text += f"状态: {status_color}\n\n"

        text += "═══ 表空间 ═══\n"
        for ts in data.tablespaces:
            text += f"  {ts['name']}: 状态={ts['status']} 文件数={ts['file_num']} 总大小={ts['total_size']}\n"

        text += "\n═══ 缓冲池 ═══\n"
        hit_pct = data.buffer_hit_rate * 100
        hit_status = "✅ 良好" if hit_pct >= 90 else ("⚠️ 偏低" if hit_pct >= 70 else "❌ 过低")
        text += f"平均命中率: {hit_pct:.2f}% {hit_status}\n"
        for bp in data.buffer_pool_info:
            bp_hit = bp['rat_hit'] * 100
            text += f"  {bp['name']}: 页数={bp['n_pages']} 逻辑读={bp['n_logic_reads']} 命中率={bp_hit:.2f}%\n"

        if hit_pct < 90:
            text += "\n⚠️ 缓冲命中率偏低，建议增大BUFFER参数:\n"
            text += "  CALL SP_SET_PARA_VALUE(1, 'BUFFER', <更大的值>);\n"

        self.result_text.setPlainText(text)
        if self.log_fn:
            self.log_fn(f"系统状态抓取完成。实例运行状态: {data.status}，缓冲池命中率: {hit_pct:.2f}%", "SUCCESS")

    def _on_error(self, task_name, error):
        self.worker = None
        self.result_text.setPlainText(f"查询失败: {error}")
        if self.log_fn:
            self.log_fn(f"系统状态查询失败: {error}", "ERROR")


class LockWaitPanel(QWidget):
    """锁和事务等待面板"""

    def __init__(self, connector: DMConnector, log_fn=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.log_fn = log_fn
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        self.btn_query = QPushButton("🔍 查询锁和事务信息")
        self.btn_query.clicked.connect(self._query)
        toolbar.addWidget(self.btn_query)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["事务ID", "锁类型", "锁模式", "表ID"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(QLabel("锁信息:"))
        layout.addWidget(self.tree)

        self.wait_text = QTextEdit()
        self.wait_text.setReadOnly(True)
        self.wait_text.setMaximumHeight(150)
        self.wait_text.setFont(QFont("Consolas", 10))
        layout.addWidget(QLabel("事务等待 / 活跃事务:"))
        layout.addWidget(self.wait_text)

    def _query(self):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker:
            try:
                if self.worker.isRunning():
                    self.worker.wait(3000)
            except RuntimeError:
                self.worker = None

        if self.log_fn:
            self.log_fn("正在查询锁冲突及活动事务等待链...")

        self.tree.clear()
        self.wait_text.setPlainText("查询中...")
        self.worker = DynamicViewWorker(self.connector, "locks")
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
        self.worker = None
        self.tree.clear()
        locks = data.get("locks", [])
        waits = data.get("waits", [])
        trxs = data.get("trxs", [])

        for lock in locks:
            item = QTreeWidgetItem([lock.trx_id, lock.ltype, lock.lmode, lock.table_id])
            if lock.lmode == "X":
                item.setForeground(2, QColor("#dc2626"))
            self.tree.addTopLevelItem(item)

        text = ""
        if waits:
            text += "═══ 事务等待 ═══\n"
            for w in waits:
                text += f"  {w}\n"
        else:
            text += "═══ 事务等待 ═══\n  无等待\n"

        text += "\n═══ 活跃事务 ═══\n"
        if trxs:
            for t in trxs:
                text += f"  事务ID={t['trx_id']} 状态={t['state']} 开始={t['start_time']}\n"
        else:
            text += "  无活跃事务\n"

        self.wait_text.setPlainText(text)
        if self.log_fn:
            self.log_fn(f"锁和事务状态查询完成。当前锁数量: {len(locks)}，事务等待事件数: {len(waits)}", "SUCCESS")

    def _on_error(self, task_name, error):
        self.worker = None
        if self.log_fn:
            self.log_fn(f"锁和事务查询失败: {error}", "ERROR")
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")


class NodeTimingPanel(QWidget):
    """执行节点耗时分析面板"""

    def __init__(self, connector: DMConnector, log_fn=None, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.log_fn = log_fn
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("EXEC_ID:"))
        self.exec_id_input = QLineEdit()
        self.exec_id_input.setPlaceholderText("0")
        self.exec_id_input.setText("0")
        self.exec_id_input.setToolTip("输入执行ID，0表示自动获取最近一次执行的ID")
        self.exec_id_input.setFixedWidth(140)
        toolbar.addWidget(self.exec_id_input)

        self.btn_query = QPushButton("查询节点耗时")
        self.btn_query.clicked.connect(self._query)
        toolbar.addWidget(self.btn_query)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["节点名称", "耗时(μs)", "执行次数", "说明"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.tree)

        # 底部提示语
        tip_label = QLabel(
            "💡 使用提示:\n"
            "1. EXEC_ID 是达梦数据库中单次 SQL 执行的唯一标识号（每次执行自动递增，不是会话 ID）。\n"
            "   从会话监控右键跳转时，工具会自动定位并为您填充该会话最近一次的 EXEC_ID。\n"
            "2. 如果查询无结果，是因为达梦数据库默认关闭了执行节点监控参数。请使用 SYSDBA 运行以下命令启用（即时生效）：\n"
            "   CALL SP_SET_PARA_VALUE(1, 'ENABLE_MONITOR', 1);\n"
            "   CALL SP_SET_PARA_VALUE(1, 'MONITOR_SQL_EXEC', 1);"
        )
        tip_label.setWordWrap(True)
        tip_label.setStyleSheet("color: #4b5563; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 4px; padding: 8px; font-size: 9pt;")
        layout.addWidget(tip_label)

    def _query(self):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker:
            try:
                if self.worker.isRunning():
                    self.worker.wait(3000)
            except RuntimeError:
                self.worker = None

        try:
            exec_id_str = self.exec_id_input.text().strip()
            exec_id = int(exec_id_str) if exec_id_str else 0
        except ValueError:
            exec_id = 0
        if self.log_fn:
            self.log_fn(f"正在查询执行计划节点耗时 (EXEC_ID: {'最新' if exec_id==0 else exec_id})...")

        self.tree.clear()
        params = {"exec_id": exec_id}
        self.worker = DynamicViewWorker(self.connector, "node_timing", params)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    # 节点说明 (来源: 附录4 执行计划操作符)
    NODE_DESCRIPTIONS = {
        "CSCN2": "聚集索引扫描(全表扫描) - 扫描整张表",
        "SSCN": "索引全扫描 - 扫描整个索引",
        "SSEK2": "索引等值查找 - 通过索引定位特定值",
        "CSEK2": "聚集索引范围查找",
        "BLKUP2": "回表查找 - 通过ROWID回聚集索引取数据",
        "HASH2 INNER JOIN": "哈希内连接 - 等值连接首选",
        "NEST LOOP INDEX JOIN2": "嵌套循环索引连接",
        "NEST LOOP INNER JOIN2": "嵌套循环内连接",
        "NEST LOOP LEFT JOIN2": "嵌套循环左连接",
        "MERGE INNER JOIN3": "归并连接 - 连接列需为索引列",
        "HASH LEFT JOIN2": "哈希左外连接",
        "HASH RIGHT JOIN2": "哈希右外连接",
        "HASH FULL JOIN2": "哈希全外连接",
        "HASH LEFT SEMI JOIN2": "哈希左半连接(子查询IN)",
        "HASH RIGHT SEMI JOIN2": "哈希右半连接",
        "INDEX JOIN SEMI JOIN2": "索引半连接",
        "SLCT2": "选择过滤 - 按条件过滤数据",
        "PRJT2": "投影 - 选择输出列",
        "HAGR2": "HASH分组(需缓存中间结果)",
        "AAGR2": "简单聚集(无分组时直接计算)",
        "FAGR2": "快速聚集(COUNT(*)或索引MAX/MIN)",
        "SORT3": "排序",
        "SORT": "排序",
        "DISTINCT": "去重",
        "NSET2": "结果集输出(顶层节点)",
        "ACTRL": "自适应计划控制(备用计划转换)",
        "AFUN": "分析函数计算(窗口函数)",
        "CONST VALUE LIST": "常量列表(IN列表展开)",
        "DLCK": "数据锁控制",
        "INSERT": "插入记录",
        "DELETE": "删除数据",
        "UPDATE": "更新数据",
    }

    def _on_finished(self, task_name, data):
        self.worker = None
        self.tree.clear()
        for item in data:
            desc = self.NODE_DESCRIPTIONS.get(item.node_name, "")
            tree_item = QTreeWidgetItem([
                item.node_name,
                f"{item.time_used:,}",
                str(item.n_enter),
                desc,
            ])
            # 高亮耗时多的操作符
            if item.time_used > 100000:  # > 100ms
                tree_item.setForeground(1, QColor("#dc2626"))
            elif item.time_used > 10000:  # > 10ms
                tree_item.setForeground(1, QColor("#f59e0b"))
            self.tree.addTopLevelItem(tree_item)
            
        self.tree.expandAll()
        if self.log_fn:
            self.log_fn(f"节点耗时分析完成，共析出 {len(data)} 个执行节点。", "SUCCESS")

        if not data:
            self.tree.addTopLevelItem(QTreeWidgetItem([
                "", "", "", "无数据。请先执行一条SQL，然后立即查询。"
            ]))

    def _on_error(self, task_name, error):
        self.worker = None
        if self.log_fn:
            self.log_fn(f"节点耗时查询失败: {error}", "ERROR")
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")
