"""
动态管理视图模块

基于达梦《动态管理和性能视图》文档，实现：
- 慢SQL抓取 (V$LONG_EXEC_SQLS / V$SYSTEM_LONG_EXEC_SQLS)
- 会话监控 (V$SESSIONS)
- 执行节点耗时分析 (V$SQL_NODE_HISTORY / V$SQL_NODE_NAME)
- 系统状态检查 (V$INSTANCE / V$TABLESPACE / V$BUFFERPOOL)
- 锁和事务等待 (V$TRX / V$LOCK / V$TRXWAIT)
"""
from dataclasses import dataclass, field
from core.dm_connector import DMConnector


@dataclass
class SlowSQLItem:
    """慢SQL记录"""
    sql_text: str
    elapsed_ms: int           # 执行耗时(毫秒)
    exec_time: str = ""       # 执行时间
    seq_no: int = 0           # 序号
    exec_id: str = ""         # 执行ID (绑定变量查询用)


@dataclass
class SessionItem:
    """会话信息"""
    sess_id: str
    sql_text: str = ""
    state: str = ""           # ACTIVE / IDLE
    create_time: str = ""
    clnt_host: str = ""
    curr_sch: str = ""


@dataclass
class NodeTimingItem:
    """执行节点耗时"""
    node_name: str            # 节点名称
    time_used: int            # 耗时(微秒)
    n_enter: int              # 执行次数


@dataclass
class SystemStatus:
    """系统状态"""
    instance_name: str = ""
    version: str = ""
    start_time: str = ""
    status: str = ""           # OPEN / 其他
    tablespaces: list = field(default_factory=list)
    buffer_hit_rate: float = 0.0
    buffer_pool_info: list = field(default_factory=list)


@dataclass
class LockWaitItem:
    """锁等待信息"""
    trx_id: str
    ltype: str                 # OBJECT / TID
    lmode: str                 # X / S / IX / IS
    table_id: str = ""
    wait_trx_id: str = ""      # 等待的事务ID


class DynamicViewManager:
    """动态管理视图管理器"""

    def __init__(self, connector: DMConnector):
        self.connector = connector

    # ------------------------------------------------------------------
    # 慢SQL抓取
    # ------------------------------------------------------------------

    def get_slow_sqls(self, limit: int = 20) -> list[SlowSQLItem]:
        """
        获取最近执行时间较长的SQL

        文档: V$LONG_EXEC_SQLS 显示最近1000条执行时间较长的SQL
              V$SYSTEM_LONG_EXEC_SQLS 显示启动以来最慢的20条SQL
        """
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute(f"""
            SELECT TOP {limit} SQL_TEXT, TIME_USED, EXEC_TIME, SEQ_NO
            FROM V$LONG_EXEC_SQLS
            ORDER BY TIME_USED DESC
        """)
        if result.error:
            # 尝试备选列名
            result = self.connector.execute(f"""
                SELECT TOP {limit} *
                FROM V$LONG_EXEC_SQLS
            """)

        items = []
        if result.error:
            return items

        for row in result.rows:
            items.append(SlowSQLItem(
                sql_text=str(row[0]) if len(row) > 0 else "",
                elapsed_ms=int(row[1]) if len(row) > 1 and row[1] else 0,
                exec_time=str(row[2]) if len(row) > 2 and row[2] else "",
                seq_no=int(row[3]) if len(row) > 3 and row[3] else 0,
            ))
        return items

    def get_system_slow_sqls(self) -> list[SlowSQLItem]:
        """获取系统启动以来最慢的20条SQL"""
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute("""
            SELECT SQL_TEXT, TIME_USED, EXEC_TIME, SEQ_NO
            FROM V$SYSTEM_LONG_EXEC_SQLS
            ORDER BY TIME_USED DESC
        """)
        items = []
        if result.error:
            return items

        for row in result.rows:
            items.append(SlowSQLItem(
                sql_text=str(row[0]) if len(row) > 0 else "",
                elapsed_ms=int(row[1]) if len(row) > 1 and row[1] else 0,
                exec_time=str(row[2]) if len(row) > 2 and row[2] else "",
                seq_no=int(row[3]) if len(row) > 3 and row[3] else 0,
            ))
        return items

    def get_sql_history(self, limit: int = 50) -> list[SlowSQLItem]:
        """获取SQL执行历史"""
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute(f"""
            SELECT TOP {limit} START_TIME, TOP_SQL_TEXT, TIME_USED, EXEC_ID
            FROM V$SQL_HISTORY
            ORDER BY START_TIME DESC
        """)
        items = []
        if result.error:
            return items

        for row in result.rows:
            items.append(SlowSQLItem(
                sql_text=str(row[1]) if len(row) > 1 else "",
                elapsed_ms=int(row[2]) if len(row) > 2 and row[2] else 0,
                exec_time=str(row[0]) if len(row) > 0 else "",
                seq_no=0,
                exec_id=str(row[3]) if len(row) > 3 and row[3] is not None else "",
            ))
        return items

    # ------------------------------------------------------------------
    # 会话监控
    # ------------------------------------------------------------------

    def get_sessions(self, active_only: bool = False, schema_filter: str = "") -> list[SessionItem]:
        """
        获取当前会话信息

        文档: V$SESSIONS 提供会话ID、SQL文本、状态、创建时间、客户端主机等
        """
        if not self.connector or not self.connector.is_connected:
            return []

        conditions = []
        if active_only:
            conditions.append("STATE = 'ACTIVE'")
        if schema_filter and schema_filter.strip():
            safe_schema = schema_filter.strip().replace("'", "''")
            conditions.append(f"CURR_SCH = '{safe_schema}'")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        result = self.connector.execute(f"""
            SELECT SESS_ID, SQL_TEXT, STATE, CREATE_TIME, CLNT_HOST, CURR_SCH
            FROM V$SESSIONS
            {where_clause}
        """)
        items = []
        if result.error:
            return items

        for row in result.rows:
            items.append(SessionItem(
                sess_id=str(row[0]) if len(row) > 0 else "",
                sql_text=str(row[1]) if len(row) > 1 else "",
                state=str(row[2]) if len(row) > 2 else "",
                create_time=str(row[3]) if len(row) > 3 else "",
                clnt_host=str(row[4]) if len(row) > 4 else "",
                curr_sch=str(row[5]) if len(row) > 5 else "",
            ))
        return items

    # ------------------------------------------------------------------
    # 执行节点耗时分析
    # ------------------------------------------------------------------

    def get_node_names(self) -> list[str]:
        """获取所有执行节点类型名称"""
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute("SELECT NAME FROM V$SQL_NODE_NAME")
        if result.error:
            return []
        return [str(row[0]) for row in result.rows if row[0]]

    def get_node_timing(self, exec_id: int) -> list[NodeTimingItem]:
        """
        获取指定执行ID的各节点耗时

        文档: 关联V$SQL_NODE_NAME和V$SQL_NODE_HISTORY，
              通过TYPE$字段等值连接，获取每个执行节点的耗时
        """
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute(f"""
            SELECT N.NAME, H.TIME_USED, H.N_ENTER
            FROM V$SQL_NODE_NAME N, V$SQL_NODE_HISTORY H
            WHERE N.TYPE$ = H.TYPE$
              AND H.EXEC_ID = {exec_id}
            ORDER BY H.TIME_USED DESC
        """)
        items = []
        if result.error:
            return items

        for row in result.rows:
            items.append(NodeTimingItem(
                node_name=str(row[0]) if len(row) > 0 else "",
                time_used=int(row[1]) if len(row) > 1 and row[1] else 0,
                n_enter=int(row[2]) if len(row) > 2 and row[2] else 0,
            ))
        return items

    def get_latest_exec_id(self) -> int:
        """获取最近一次SQL执行的EXEC_ID"""
        if not self.connector or not self.connector.is_connected:
            return 0

        result = self.connector.execute("""
            SELECT MAX(EXEC_ID) FROM V$SQL_NODE_HISTORY
        """)
        if result.error or not result.rows:
            return 0
        return int(result.rows[0][0]) if result.rows[0][0] else 0

    # ------------------------------------------------------------------
    # 系统状态检查
    # ------------------------------------------------------------------

    def get_system_status(self) -> SystemStatus:
        """
        获取系统状态

        文档: V$INSTANCE 实例信息, V$TABLESPACE 表空间,
              V$BUFFERPOOL 缓冲池命中率
        """
        status = SystemStatus()

        if not self.connector or not self.connector.is_connected:
            return status

        # 实例信息
        result = self.connector.execute("""
            SELECT INSTANCE_NAME, SVR_VERSION, START_TIME, STATUS$
            FROM V$INSTANCE
        """)
        if not result.error and result.rows:
            row = result.rows[0]
            status.instance_name = str(row[0]) if len(row) > 0 else ""
            status.version = str(row[1]) if len(row) > 1 else ""
            status.start_time = str(row[2]) if len(row) > 2 else ""
            status.status = str(row[3]) if len(row) > 3 else ""

        # 表空间信息
        result = self.connector.execute("""
            SELECT ID, NAME, STATUS$, MAX_SIZE, TOTAL_SIZE, FILE_NUM
            FROM V$TABLESPACE
        """)
        if not result.error:
            for row in result.rows:
                status.tablespaces.append({
                    "id": row[0],
                    "name": str(row[1]) if len(row) > 1 else "",
                    "status": str(row[2]) if len(row) > 2 else "",
                    "max_size": row[3] if len(row) > 3 else 0,
                    "total_size": row[4] if len(row) > 4 else 0,
                    "file_num": row[5] if len(row) > 5 else 0,
                })

        # 缓冲池命中率
        result = self.connector.execute("""
            SELECT NAME, N_PAGES, N_LOGIC_READS, RAT_HIT
            FROM V$BUFFERPOOL
        """)
        if not result.error:
            total_hit = 0
            count = 0
            for row in result.rows:
                name = str(row[0]) if len(row) > 0 else ""
                n_pages = row[1] if len(row) > 1 else 0
                n_logic_reads = row[2] if len(row) > 2 else 0
                rat_hit = float(row[3]) if len(row) > 3 and row[3] else 0.0
                status.buffer_pool_info.append({
                    "name": name,
                    "n_pages": n_pages,
                    "n_logic_reads": n_logic_reads,
                    "rat_hit": rat_hit,
                })
                total_hit += rat_hit
                count += 1
            if count > 0:
                status.buffer_hit_rate = total_hit / count

        return status

    # ------------------------------------------------------------------
    # 锁和事务等待
    # ------------------------------------------------------------------

    def get_locks(self) -> list[LockWaitItem]:
        """
        获取事务锁信息

        文档: V$LOCK 记录事务锁信息(TID锁/对象锁)
              V$TRXWAIT 记录事务等待信息
        """
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute("""
            SELECT TRX_ID, LTYPE, LMODE, TABLE_ID
            FROM V$LOCK
        """)
        items = []
        if result.error:
            return items

        for row in result.rows:
            items.append(LockWaitItem(
                trx_id=str(row[0]) if len(row) > 0 else "",
                ltype=str(row[1]) if len(row) > 1 else "",
                lmode=str(row[2]) if len(row) > 2 else "",
                table_id=str(row[3]) if len(row) > 3 else "",
            ))
        return items

    def get_trx_waits(self) -> list[dict]:
        """获取事务等待信息"""
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute("""
            SELECT * FROM V$TRXWAIT
        """)
        if result.error:
            return []

        waits = []
        for row in result.rows:
            wait_item = {}
            for i, col in enumerate(result.columns):
                wait_item[col.lower()] = str(row[i]) if i < len(row) and row[i] else ""
            waits.append(wait_item)
        return waits

    def get_active_transactions(self) -> list[dict]:
        """获取活跃事务"""
        if not self.connector or not self.connector.is_connected:
            return []

        result = self.connector.execute("""
            SELECT TRX_ID, STATE, START_TIME FROM V$TRX WHERE STATE = 'ACTIVE'
        """)
        if result.error:
            return []

        trxs = []
        for row in result.rows:
            trxs.append({
                "trx_id": str(row[0]) if len(row) > 0 else "",
                "state": str(row[1]) if len(row) > 1 else "",
                "start_time": str(row[2]) if len(row) > 2 else "",
            })
        return trxs
