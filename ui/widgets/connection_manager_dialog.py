"""
数据库连接管理弹窗
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLineEdit, QSpinBox, QPushButton, QListWidget, QListWidgetItem,
    QMessageBox, QLabel, QWidget,
)
from PySide6.QtCore import Qt
from config import DMConnectionConfig, AppConfig, save_config
from core.dm_connector import DMConnector


class ConnectionManagerDialog(QDialog):
    """数据库连接管理器"""

    def __init__(self, app_config: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("数据库连接管理")
        self.setMinimumSize(650, 450)
        self.app_config = app_config
        # 复制一份连接列表，防止未保存即修改
        self.connections = [
            DMConnectionConfig(
                name=c.name, host=c.host, port=c.port,
                user=c.user, password=c.password, schema=c.schema,
                timeout=c.timeout
            ) for c in app_config.connections
        ]
        self.selected_index = -1
        self.selected_conn = None

        self._init_ui()
        self._load_list()

        # 默认选中当前正在使用的连接
        for i, c in enumerate(self.connections):
            if c.host == app_config.connection.host and c.port == app_config.connection.port and c.user == app_config.connection.user:
                self.list_widget.setCurrentRow(i)
                break
        else:
            if self.connections:
                self.list_widget.setCurrentRow(0)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # 中间分裂区域
        content_layout = QHBoxLayout()

        # 左侧: 连接列表
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("已保存连接:"))
        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self.list_widget)

        btn_list_layout = QHBoxLayout()
        self.btn_new = QPushButton("新建")
        self.btn_new.clicked.connect(self._on_new_connection)
        self.btn_delete = QPushButton("删除")
        self.btn_delete.clicked.connect(self._on_delete_connection)
        btn_list_layout.addWidget(self.btn_new)
        btn_list_layout.addWidget(self.btn_delete)
        left_layout.addLayout(btn_list_layout)
        content_layout.addLayout(left_layout, 1)

        # 右侧: 连接详情表单
        right_group = QGroupBox("连接属性")
        form_layout = QFormLayout(right_group)

        self.name_input = QLineEdit()
        form_layout.addRow("连接名称:", self.name_input)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("127.0.0.1")
        form_layout.addRow("主机 (Host):", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(5236)
        form_layout.addRow("端口 (Port):", self.port_input)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("SYSDBA")
        form_layout.addRow("用户名 (User):", self.user_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("SYSDBA")
        form_layout.addRow("密码 (Password):", self.password_input)

        self.schema_input = QLineEdit()
        self.schema_input.setPlaceholderText("默认Schema(可选)")
        form_layout.addRow("模式 (Schema):", self.schema_input)

        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(1, 3600)
        self.timeout_input.setValue(30)
        form_layout.addRow("超时时间 (秒):", self.timeout_input)

        # 连接详情的保存和测试按钮
        btn_form_layout = QHBoxLayout()
        self.btn_test = QPushButton("测试连接")
        self.btn_test.clicked.connect(self._on_test_connection)
        self.btn_save = QPushButton("保存修改")
        self.btn_save.clicked.connect(self._on_save_profile)
        btn_form_layout.addWidget(self.btn_test)
        btn_form_layout.addWidget(self.btn_save)
        form_layout.addRow(btn_form_layout)

        content_layout.addWidget(right_group, 2)
        main_layout.addLayout(content_layout)

        # 底部: 关闭与确定连接按钮
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_connect = QPushButton("保存并连接")
        self.btn_connect.setStyleSheet(
            "QPushButton { background-color: #2563eb; color: white; font-weight: bold; padding: 6px 20px; }"
        )
        self.btn_connect.clicked.connect(self._on_connect_clicked)
        self.btn_cancel = QPushButton("取消")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_connect)
        bottom_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom_layout)

    def _load_list(self):
        self.list_widget.clear()
        for conn in self.connections:
            item = QListWidgetItem(conn.name)
            self.list_widget.addItem(item)

    def _on_selection_changed(self, current, previous):
        if not current:
            self.selected_index = -1
            self.selected_conn = None
            self.name_input.clear()
            self.host_input.clear()
            self.port_input.setValue(5236)
            self.user_input.clear()
            self.password_input.clear()
            self.schema_input.clear()
            self.timeout_input.setValue(30)
            return

        self.selected_index = self.list_widget.row(current)
        self.selected_conn = self.connections[self.selected_index]

        self.name_input.setText(self.selected_conn.name)
        self.host_input.setText(self.selected_conn.host)
        self.port_input.setValue(self.selected_conn.port)
        self.user_input.setText(self.selected_conn.user)
        self.password_input.setText(self.selected_conn.password)
        self.schema_input.setText(self.selected_conn.schema)
        self.timeout_input.setValue(self.selected_conn.timeout)

    def _on_new_connection(self):
        new_conn = DMConnectionConfig(
            name=f"新连接 {len(self.connections) + 1}",
            host="127.0.0.1",
            port=5236,
            user="SYSDBA",
            password="SYSDBA",
            schema="",
            timeout=30
        )
        self.connections.append(new_conn)
        item = QListWidgetItem(new_conn.name)
        self.list_widget.addItem(item)
        self.list_widget.setCurrentItem(item)

    def _on_delete_connection(self):
        if self.selected_index < 0:
            return

        if len(self.connections) <= 1:
            QMessageBox.warning(self, "提示", "必须保留至少一个连接配置")
            return

        reply = QMessageBox.question(
            self, "确认删除", f"确定删除连接 '{self.selected_conn.name}' 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.connections.pop(self.selected_index)
            self._load_list()
            # 自动选中下一个
            new_row = min(self.selected_index, len(self.connections) - 1)
            self.list_widget.setCurrentRow(new_row)

    def _on_save_profile(self):
        if self.selected_index < 0:
            return

        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "连接名称不能为空")
            return

        self.selected_conn.name = name
        self.selected_conn.host = self.host_input.text().strip()
        self.selected_conn.port = self.port_input.value()
        self.selected_conn.user = self.user_input.text().strip()
        self.selected_conn.password = self.password_input.text()
        self.selected_conn.schema = self.schema_input.text().strip()
        self.selected_conn.timeout = self.timeout_input.value()

        # 更新列表中的显示名称
        self.list_widget.currentItem().setText(name)
        QMessageBox.information(self, "成功", "修改已保存到临时配置")

    def _on_test_connection(self):
        temp_config = DMConnectionConfig(
            host=self.host_input.text().strip(),
            port=self.port_input.value(),
            user=self.user_input.text().strip(),
            password=self.password_input.text(),
            schema=self.schema_input.text().strip(),
            timeout=5  # 测试连接使用短超时
        )
        connector = DMConnector(temp_config)
        self.btn_test.setEnabled(False)
        self.btn_test.setText("正在测试...")
        # 强制界面刷新
        self.repaint()

        try:
            connector.connect()
            connector.disconnect()
            QMessageBox.information(self, "连接测试", "连接成功！")
        except Exception as e:
            QMessageBox.critical(self, "连接测试", f"连接失败:\n{e}")
        finally:
            self.btn_test.setEnabled(True)
            self.btn_test.setText("测试连接")

    def _on_connect_clicked(self):
        # 确保当前表单的修改被保存
        if self.selected_index >= 0:
            self.selected_conn.name = self.name_input.text().strip()
            self.selected_conn.host = self.host_input.text().strip()
            self.selected_conn.port = self.port_input.value()
            self.selected_conn.user = self.user_input.text().strip()
            self.selected_conn.password = self.password_input.text()
            self.selected_conn.schema = self.schema_input.text().strip()
            self.selected_conn.timeout = self.timeout_input.value()

        # 将临时修改写回全局配置
        self.app_config.connections = self.connections
        if self.selected_index >= 0:
            self.app_config.connection = self.connections[self.selected_index]
        
        # 写入物理磁盘
        try:
            save_config(self.app_config)
        except Exception:
            pass

        self.accept()
