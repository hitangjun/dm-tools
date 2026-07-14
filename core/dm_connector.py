"""
DM数据库连接管理模块

封装dmPython的连接操作，提供：
- 连接/断开
- 执行SQL查询
- 获取执行计划
- 获取表/索引/列的元数据
"""
import re
from typing import Optional
from dataclasses import dataclass

try:
    import dmPython
except ImportError:
    dmPython = None


@dataclass
class QueryResult:
    """查询结果"""
    columns: list          # 列名列表
    rows: list            # 数据行列表
    row_count: int        # 行数
    elapsed_ms: float     # 耗时(毫秒)
    error: Optional[str] = None  # 错误信息


class DMConnector:
    """DM数据库连接器"""

    def __init__(self, config: DMConnectionConfig):
        self.config = config
        self._conn = None

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    def connect(self) -> bool:
        """连接DM数据库"""
        if dmPython is None:
            raise RuntimeError(
                "未找到dmPython驱动模块，无法连接DM数据库。\n\n"
                "解决方法:\n"
                "  1. 确保本机已安装DM客户端(提供dmdpi.dll/libdmdpi.so驱动库)\n"
                "  2. 安装dmPython: pip install dmPython\n"
                "  3. 如果是打包后的EXE，需确保:\n"
                "     - 打包机器上已安装dmPython\n"
                "     - 打包时加了 --hidden-import dmPython 参数\n"
                "     - 目标机器上已安装DM客户端\n"
                "  4. 如果不需要连接数据库，可使用SQL规范检查和HINT建议功能(离线可用)"
            )
        try:
            self._conn = dmPython.connect(
                user=self.config.user,
                password=self.config.password,
                server=self.config.host,
                port=self.config.port,
                login_timeout=self.config.timeout,
            )
            if self.config.schema:
                self.execute(f'SET SCHEMA "{self.config.schema}"')
            return True
        except Exception as e:
            self._conn = None
            raise ConnectionError(f"连接DM数据库失败: {e}")

    def disconnect(self):
        """断开连接"""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            finally:
                self._conn = None

    # ------------------------------------------------------------------
    # SQL执行
    # ------------------------------------------------------------------

    def execute(self, sql: str, params=None) -> QueryResult:
        """执行查询SQL，返回结果"""
        if not self.is_connected:
            raise RuntimeError("数据库未连接")
        import time
        cursor = self._conn.cursor()
        start = time.time()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            columns = (
                [desc[0] for desc in cursor.description]
                if cursor.description
                else []
            )
            rows = cursor.fetchall()
            elapsed = (time.time() - start) * 1000
            return QueryResult(
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed_ms=round(elapsed, 2),
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return QueryResult(
                columns=[], rows=[], row_count=0,
                elapsed_ms=round(elapsed, 2), error=str(e),
            )
        finally:
            cursor.close()

    def execute_only(self, sql: str, params=None) -> int:
        """执行非查询SQL（DDL/DML），返回影响行数"""
        if not self.is_connected:
            raise RuntimeError("数据库未连接")
        cursor = self._conn.cursor()
        try:
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            self._conn.commit()
            return cursor.rowcount
        finally:
            cursor.close()

    # ------------------------------------------------------------------
    # 执行计划
    # ------------------------------------------------------------------

    def get_explain_plan(self, sql: str) -> str:
        """
        获取SQL的执行计划文本

        DM数据库通过 EXPLAIN 语句获取执行计划
        返回执行计划的文本格式
        """
        sql = sql.strip().rstrip(";")
        result = self.execute(f"EXPLAIN {sql}")
        if result.error:
            # 某些DM版本需要用 EXPLAIN FOR
            result = self.execute(f"EXPLAIN FOR {sql}")
            if result.error:
                raise RuntimeError(f"获取执行计划失败: {result.error}")
        return self._format_explain(result)

    def _format_explain(self, result: QueryResult) -> str:
        """将查询结果格式化为执行计划文本"""
        if not result.columns:
            return ""
        lines = []
        # 计算每列最大宽度
        col_widths = []
        for i, col in enumerate(result.columns):
            max_w = len(str(col))
            for row in result.rows:
                if i < len(row) and row[i] is not None:
                    max_w = max(max_w, len(str(row[i])))
            col_widths.append(max_w)

        # 表头
        header = " | ".join(
            str(col).ljust(col_widths[i])
            for i, col in enumerate(result.columns)
        )
        lines.append(header)
        lines.append("-+-".join("-" * w for w in col_widths))
        # 数据行
        for row in result.rows:
            lines.append(" | ".join(
                str(row[i]).ljust(col_widths[i]) if i < len(row) and row[i] is not None else "NULL".ljust(col_widths[i])
                for i in range(len(result.columns))
            ))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 元数据查询
    # ------------------------------------------------------------------

    def get_table_info(self, table_name: str) -> dict:
        """获取表的基本信息（行数、大小等）"""
        schema = self.config.schema or self.config.user
        result = self.execute(f"""
            SELECT TABLE_NAME, NUM_ROWS, BLOCKS, AVG_ROW_LEN, LAST_ANALYZED
            FROM ALL_TABLES
            WHERE TABLE_NAME = UPPER('{table_name}')
              AND OWNER = UPPER('{schema}')
        """)
        if result.error or not result.rows:
            return {"table_name": table_name, "exists": False}
        row = result.rows[0]
        return {
            "table_name": row[0],
            "num_rows": row[1] or 0,
            "blocks": row[2] or 0,
            "avg_row_len": row[3] or 0,
            "last_analyzed": str(row[4]) if row[4] else None,
            "exists": True,
        }

    def get_table_columns(self, table_name: str) -> list[dict]:
        """获取表的列信息"""
        schema = self.config.schema or self.config.user
        result = self.execute(f"""
            SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH,
                   NULLABLE, DATA_DEFAULT, NUM_DISTINCT
            FROM ALL_TAB_COLUMNS
            WHERE TABLE_NAME = UPPER('{table_name}')
              AND OWNER = UPPER('{schema}')
            ORDER BY COLUMN_ID
        """)
        columns = []
        if result.error:
            return columns
        for row in result.rows:
            columns.append({
                "name": row[0],
                "type": row[1],
                "length": row[2],
                "nullable": row[3] == "Y",
                "default": row[4],
                "num_distinct": row[5],
            })
        return columns

    def get_table_indexes(self, table_name: str) -> list[dict]:
        """获取表的索引信息"""
        schema = self.config.schema or self.config.user
        result = self.execute(f"""
            SELECT I.INDEX_NAME, I.INDEX_TYPE, I.UNIQUENESS,
                   I.LAST_ANALYZED, I.NUM_ROWS,
                   LISTAGG(C.COLUMN_NAME, ', ') WITHIN GROUP (ORDER BY C.COLUMN_POSITION) AS COLUMNS
            FROM ALL_INDEXES I
            JOIN ALL_IND_COLUMNS C
              ON I.INDEX_NAME = C.INDEX_NAME
             AND I.OWNER = C.INDEX_OWNER
             AND I.TABLE_NAME = C.TABLE_NAME
            WHERE I.TABLE_NAME = UPPER('{table_name}')
              AND I.OWNER = UPPER('{schema}')
            GROUP BY I.INDEX_NAME, I.INDEX_TYPE, I.UNIQUENESS,
                     I.LAST_ANALYZED, I.NUM_ROWS
        """)
        indexes = []
        if result.error:
            return indexes
        for row in result.rows:
            indexes.append({
                "name": row[0],
                "type": row[1],
                "uniqueness": row[2],
                "last_analyzed": str(row[3]) if row[3] else None,
                "num_rows": row[4],
                "columns": row[5].split(", ") if row[5] else [],
            })
        return indexes

    def get_table_stats(self, table_name: str) -> dict:
        """获取表统计信息详情"""
        info = self.get_table_info(table_name)
        columns = self.get_table_columns(table_name)
        indexes = self.get_table_indexes(table_name)
        return {
            "table_info": info,
            "columns": columns,
            "indexes": indexes,
        }
