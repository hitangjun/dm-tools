"""
动态管理视图功能面板

包含: 慢SQL抓取、会话监控、执行节点耗时、系统状态、锁等待
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLabel,
    QPushButton, QSpinBox, QHeaderView,
    QMessageBox, QSplitter,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor

from core.dm_connector import DMConnector
from core.dynamic_views import DynamicViewManager
from core.doc_knowledge import DocKnowledgeBase
from ui.widgets.doc_info_widget import DocInfoWidget


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
                data = self.manager.get_sessions(self.params.get("active_only", False))
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

    def __init__(self, connector: DMConnector, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.kb = DocKnowledgeBase()
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # 文档信息
        doc_widget = DocInfoWidget(self.kb.get("slow_sql"))
        layout.addWidget(doc_widget)

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

        # 结果展示
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["序号", "耗时(ms)", "执行时间", "SQL文本"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self.tree)

    def _query(self, task_name):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        # 等待前一个线程完成
        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        self.tree.clear()
        params = {"limit": self.limit_spin.value()} if task_name == "slow_sql" else {}
        self.worker = DynamicViewWorker(self.connector, task_name, params)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
        self.tree.clear()
        for i, item in enumerate(data):
            tree_item = QTreeWidgetItem([
                str(i + 1),
                str(item.elapsed_ms),
                item.exec_time,
                item.sql_text[:200],
            ])
            # 高亮耗时长的SQL
            if item.elapsed_ms > 5000:
                tree_item.setForeground(1, QColor("#dc2626"))
            elif item.elapsed_ms > 1000:
                tree_item.setForeground(1, QColor("#f59e0b"))
            self.tree.addTopLevelItem(tree_item)

    def _on_error(self, task_name, error):
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")


class SessionPanel(QWidget):
    """会话监控面板"""

    def __init__(self, connector: DMConnector, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.kb = DocKnowledgeBase()
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("session_monitor"))
        layout.addWidget(doc_widget)

        toolbar = QHBoxLayout()
        self.btn_all = QPushButton("查询所有会话")
        self.btn_all.clicked.connect(lambda: self._query(False))
        toolbar.addWidget(self.btn_all)

        self.btn_active = QPushButton("仅活跃会话")
        self.btn_active.setStyleSheet("QPushButton { background-color: #fef3c7; }")
        self.btn_active.clicked.connect(lambda: self._query(True))
        toolbar.addWidget(self.btn_active)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["会话ID", "状态", "创建时间", "客户端", "SQL文本"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        layout.addWidget(self.tree)

    def _query(self, active_only):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        self.tree.clear()
        self.worker = DynamicViewWorker(self.connector, "sessions", {"active_only": active_only})
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
        self.tree.clear()
        for item in data:
            tree_item = QTreeWidgetItem([
                item.sess_id, item.state, item.create_time, item.clnt_host,
                item.sql_text[:200],
            ])
            if item.state == "ACTIVE":
                tree_item.setForeground(1, QColor("#dc2626"))
            self.tree.addTopLevelItem(tree_item)

    def _on_error(self, task_name, error):
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")


class SystemStatusPanel(QWidget):
    """系统状态检查面板"""

    def __init__(self, connector: DMConnector, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.kb = DocKnowledgeBase()
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("system_status"))
        layout.addWidget(doc_widget)

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

        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        self.result_text.setPlainText("查询中...")
        self.worker = DynamicViewWorker(self.connector, "system_status")
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
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

    def _on_error(self, task_name, error):
        self.result_text.setPlainText(f"查询失败: {error}")


class LockWaitPanel(QWidget):
    """锁和事务等待面板"""

    def __init__(self, connector: DMConnector, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.kb = DocKnowledgeBase()
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("lock_wait"))
        layout.addWidget(doc_widget)

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

        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        self.tree.clear()
        self.wait_text.setPlainText("查询中...")
        self.worker = DynamicViewWorker(self.connector, "locks")
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_finished(self, task_name, data):
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

    def _on_error(self, task_name, error):
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")


class NodeTimingPanel(QWidget):
    """执行节点耗时分析面板"""

    def __init__(self, connector: DMConnector, parent=None):
        super().__init__(parent)
        self.connector = connector
        self.kb = DocKnowledgeBase()
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        doc_widget = DocInfoWidget(self.kb.get("node_timing"))
        layout.addWidget(doc_widget)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("EXEC_ID:"))
        self.exec_id_spin = QSpinBox()
        self.exec_id_spin.setRange(0, 999999999)
        self.exec_id_spin.setValue(0)
        self.exec_id_spin.setToolTip("0=自动获取最近一次执行的ID")
        toolbar.addWidget(self.exec_id_spin)

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

    def _query(self):
        if not self.connector or not self.connector.is_connected:
            QMessageBox.warning(self, "未连接", "请先连接DM数据库")
            return

        if self.worker and self.worker.isRunning():
            self.worker.wait(3000)

        self.tree.clear()
        params = {"exec_id": self.exec_id_spin.value()}
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
        self.tree.clear()
        for item in data:
            desc = self.NODE_DESCRIPTIONS.get(item.node_name, "")
            tree_item = QTreeWidgetItem([
                item.node_name,
                str(item.time_used),
                str(item.n_enter),
                desc,
            ])
            # 高亮耗时最高的节点
            if item.time_used > 10000:
                tree_item.setForeground(1, QColor("#dc2626"))
                tree_item.setForeground(0, QColor("#dc2626"))
            elif item.time_used > 1000:
                tree_item.setForeground(1, QColor("#f59e0b"))
            self.tree.addTopLevelItem(tree_item)

        if not data:
            self.tree.addTopLevelItem(QTreeWidgetItem([
                "", "", "", "无数据。请先执行一条SQL，然后立即查询。"
            ]))

    def _on_error(self, task_name, error):
        QMessageBox.warning(self, "查询失败", f"{task_name}: {error}")
