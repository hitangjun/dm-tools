"""
DM SQL优化分析工具 - 配置管理

支持两种配置方式:
1. 外部INI配置文件 (db_config.ini) - 与exe同目录，运行时提供DBA账号
2. 用户配置目录 (~/.dm_sql_optimizer/config.json) - 程序自动保存
"""
import json
import os
import sys
import configparser
from dataclasses import dataclass, asdict
from pathlib import Path

CONFIG_DIR = Path.home() / ".dm_sql_optimizer"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _find_ini_config():
    """查找外部INI配置文件"""
    candidates = []
    if hasattr(sys, '_MEIPASS'):
        candidates.append(Path(sys._MEIPASS).parent / "db_config.ini")
    candidates.append(Path.cwd() / "db_config.ini")
    candidates.append(Path(__file__).parent / "db_config.ini")
    for path in candidates:
        if path.exists():
            return path
    return None


@dataclass
class DMConnectionConfig:
    """DM数据库连接配置"""
    name: str = "默认连接"
    host: str = "127.0.0.1"
    port: int = 5236
    user: str = "SYSDBA"
    password: str = "SYSDBA"
    schema: str = ""
    timeout: int = 30

    @property
    def connection_string(self) -> str:
        return f"dm://{self.user}:{self.password}@{self.host}:{self.port}"


@dataclass
class AppConfig:
    """应用全局配置"""
    connection: DMConnectionConfig = None
    connections: list[DMConnectionConfig] = None
    slow_threshold_ms: int = 1000
    max_rows_explain: int = 10000
    enable_auto_stats: bool = True
    highlight_risk_level: str = "all"

    def __post_init__(self):
        if self.connection is None:
            self.connection = DMConnectionConfig()
        if self.connections is None or len(self.connections) == 0:
            self.connections = [self.connection]


def load_config() -> AppConfig:
    """
    加载配置

    优先级与合并规则:
    1. 先读取用户配置目录(~/.dm_sql_optimizer/config.json)以保留所有保存的连接
    2. 若有外部INI配置文件(db_config.ini)，则将INI连接作为新配置导入并合并(避免重复)
    3. 若没有JSON配置但有INI配置，则使用INI并保存一次到JSON
    4. 兜底默认配置
    """
    app_cfg = None
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            conn_data = data.pop("connection", {})
            conn = DMConnectionConfig(**conn_data)
            
            conns_data = data.pop("connections", [])
            conns = []
            for c_data in conns_data:
                conns.append(DMConnectionConfig(**c_data))
                
            if not conns:
                conns = [conn]
            app_cfg = AppConfig(connection=conn, connections=conns, **data)
        except Exception:
            pass

    # 检查是否有外部INI配置
    ini_path = _find_ini_config()
    ini_cfg = None
    if ini_path:
        try:
            parser = configparser.ConfigParser()
            parser.read(ini_path, encoding="utf-8")
            if parser.has_section("database"):
                db = parser["database"]
                ini_conn = DMConnectionConfig(
                    name="外部INI连接",
                    host=db.get("host", "127.0.0.1"),
                    port=db.getint("port", 5236),
                    user=db.get("user", "SYSDBA"),
                    password=db.get("password", "SYSDBA"),
                    schema=db.get("schema", ""),
                    timeout=db.getint("timeout", 30),
                )
                ini_cfg = AppConfig(connection=ini_conn, connections=[ini_conn])
                if parser.has_section("app"):
                    app = parser["app"]
                    ini_cfg.slow_threshold_ms = app.getint("slow_threshold_ms", 1000)
                    ini_cfg.max_rows_explain = app.getint("max_rows_explain", 10000)
                    ini_cfg.enable_auto_stats = app.getboolean("enable_auto_stats", True)
                    ini_cfg.highlight_risk_level = app.get("highlight_risk_level", "all")
        except Exception:
            pass

    # 合并策略
    if app_cfg:
        if ini_cfg:
            ini_conn = ini_cfg.connection
            # 检查INI中的配置是否已存在于已保存列表中
            exists = False
            for c in app_cfg.connections:
                if c.host == ini_conn.host and c.port == ini_conn.port and c.user == ini_conn.user:
                    exists = True
                    break
            if not exists:
                app_cfg.connections.append(ini_conn)
        return app_cfg
    elif ini_cfg:
        try:
            save_config(ini_cfg)
        except Exception:
            pass
        return ini_cfg

    return AppConfig()


def save_config(config: AppConfig):
    """保存配置文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
