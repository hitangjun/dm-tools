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
    slow_threshold_ms: int = 1000
    max_rows_explain: int = 10000
    enable_auto_stats: bool = True
    highlight_risk_level: str = "all"

    def __post_init__(self):
        if self.connection is None:
            self.connection = DMConnectionConfig()


def load_config() -> AppConfig:
    """
    加载配置

    优先级:
    1. 外部INI配置文件(db_config.ini)
    2. 用户配置目录(~/.dm_sql_optimizer/config.json)
    3. 默认配置
    """
    ini_path = _find_ini_config()
    if ini_path:
        try:
            parser = configparser.ConfigParser()
            parser.read(ini_path, encoding="utf-8")
            if parser.has_section("database"):
                db = parser["database"]
                conn = DMConnectionConfig(
                    host=db.get("host", "127.0.0.1"),
                    port=db.getint("port", 5236),
                    user=db.get("user", "SYSDBA"),
                    password=db.get("password", "SYSDBA"),
                    schema=db.get("schema", ""),
                    timeout=db.getint("timeout", 30),
                )
                app_cfg = AppConfig(connection=conn)
                if parser.has_section("app"):
                    app = parser["app"]
                    app_cfg.slow_threshold_ms = app.getint("slow_threshold_ms", 1000)
                    app_cfg.max_rows_explain = app.getint("max_rows_explain", 10000)
                    app_cfg.enable_auto_stats = app.getboolean("enable_auto_stats", True)
                    app_cfg.highlight_risk_level = app.get("highlight_risk_level", "all")
                return app_cfg
        except Exception:
            pass

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            conn_data = data.pop("connection", {})
            conn = DMConnectionConfig(**conn_data)
            return AppConfig(connection=conn, **data)
        except Exception:
            pass

    return AppConfig()


def save_config(config: AppConfig):
    """保存配置文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = asdict(config)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
