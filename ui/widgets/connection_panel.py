"""
数据库连接配置面板
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSpinBox, QPushButton, QLabel, QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Signal
from config import DMConnectionConfig


class ConnectionPanel(QGroupBox):
    """连接配置面板"""

    connect_requested = Signal(DMConnectionConfig)

    def __init__(self, config: DMConnectionConfig, parent=None):
        super().__init__("数据库连接", parent)
        self._config = config
        self._init_ui()
        self._load_config()

    def _init_ui(self):
        layout = QFormLayout(self)

        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("127.0.0.1")
        layout.addRow("主机:", self.host_input)

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(5236)
        layout.addRow("端口:", self.port_input)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("SYSDBA")
        layout.addRow("用户名:", self.user_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("密码")
        layout.addRow("密码:", self.password_input)

        self.schema_input = QLineEdit()
        self.schema_input.setPlaceholderText("默认Schema(可选)")
        layout.addRow("Schema:", self.schema_input)

        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self._on_connect)
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.status_label)
        btn_layout.addStretch()
        layout.addRow(btn_layout)

    def _load_config(self):
        self.host_input.setText(self._config.host)
        self.port_input.setValue(self._config.port)
        self.user_input.setText(self._config.user)
        self.password_input.setText(self._config.password)
        self.schema_input.setText(self._config.schema)

    def _on_connect(self):
        config = DMConnectionConfig(
            host=self.host_input.text().strip(),
            port=self.port_input.value(),
            user=self.user_input.text().strip(),
            password=self.password_input.text(),
            schema=self.schema_input.text().strip(),
        )
        self.connect_requested.emit(config)

    def set_connected(self, connected: bool):
        """设置连接状态"""
        if connected:
            self.status_label.setText("● 已连接")
            self.status_label.setStyleSheet("color: green; font-weight: bold;")
            self.connect_btn.setText("断开")
        else:
            self.status_label.setText("● 未连接")
            self.status_label.setStyleSheet("color: gray; font-weight: bold;")
            self.connect_btn.setText("连接")

    def get_config(self) -> DMConnectionConfig:
        return DMConnectionConfig(
            host=self.host_input.text().strip(),
            port=self.port_input.value(),
            user=self.user_input.text().strip(),
            password=self.password_input.text(),
            schema=self.schema_input.text().strip(),
        )
