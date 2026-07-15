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
from config import DMConnectionConfig

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
        
        # 检查是否是达梦结构化执行计划表格 (通常包含 LEVEL_ID 和 OPERATION)
        col_names = [c.upper() for c in result.columns]
        if "LEVEL_ID" in col_names and "OPERATION" in col_names:
            level_idx = col_names.index("LEVEL_ID")
            op_idx = col_names.index("OPERATION")
            
            # 其他需要展示的辅助性能/对象列
            tab_idx = col_names.index("TAB_NAME") if "TAB_NAME" in col_names else -1
            idx_idx = col_names.index("IDX_NAME") if "IDX_NAME" in col_names else -1
            rows_idx = col_names.index("ROW_NUMS") if "ROW_NUMS" in col_names else -1
            cost_idx = col_names.index("COST") if "COST" in col_names else -1
            filter_idx = col_names.index("FILTER") if "FILTER" in col_names else -1
            join_idx = col_names.index("JOIN_COND") if "JOIN_COND" in col_names else -1
            scan_idx = col_names.index("SCAN_TYPE") if "SCAN_TYPE" in col_names else -1
            advice_idx = col_names.index("ADVICE_INFO") if "ADVICE_INFO" in col_names else -1
            scan_range_idx = col_names.index("SCAN_RANGE") if "SCAN_RANGE" in col_names else -1

            lines = []
            lines.append("达梦数据库执行计划树 (层级缩进):")
            lines.append("=" * 90)
            
            node_no = 0
            for row in result.rows:
                node_no += 1
                level = 0
                try:
                    level = int(row[level_idx]) if row[level_idx] is not None else 0
                except ValueError:
                    pass
                
                op = str(row[op_idx]) if row[op_idx] is not None else "NULL"
                
                # 提取并组装当前节点的关键指标
                info = []
                if tab_idx != -1 and row[tab_idx] and str(row[tab_idx]).upper() != "NULL":
                    info.append(f"表: {row[tab_idx]}")
                if idx_idx != -1 and row[idx_idx] and str(row[idx_idx]).upper() != "NULL":
                    info.append(f"索引: {row[idx_idx]}")
                if rows_idx != -1 and row[rows_idx] and str(row[rows_idx]).upper() != "NULL":
                    info.append(f"估算行数: {row[rows_idx]}")
                if cost_idx != -1 and row[cost_idx] and str(row[cost_idx]).upper() != "NULL":
                    info.append(f"估算代价: {row[cost_idx]}")
                if scan_idx != -1 and row[scan_idx] and str(row[scan_idx]).upper() != "NULL":
                    info.append(f"扫描方式: {row[scan_idx]}")
                if scan_range_idx != -1 and row[scan_range_idx] and str(row[scan_range_idx]).upper() != "NULL":
                    info.append(f"扫描范围: {row[scan_range_idx]}")
                if filter_idx != -1 and row[filter_idx] and str(row[filter_idx]).upper() != "NULL":
                    info.append(f"过滤条件(WHERE): {row[filter_idx]}")
                if join_idx != -1 and row[join_idx] and str(row[join_idx]).upper() != "NULL":
                    info.append(f"连接条件(ON): {row[join_idx]}")
                if advice_idx != -1 and row[advice_idx] and str(row[advice_idx]).upper() != "NULL":
                    info.append(f"优化器建议: {row[advice_idx]}")
                
                info_str = f" [{', '.join(info)}]" if info else ""
                
                # 使用缩进空格表示树层级，带行号前缀
                indent = "  " * level
                line_num = f"{node_no:>3}"
                lines.append(f"{line_num} | {indent}└─ {op}{info_str}")
                
            lines.append("=" * 90)
            return "\n".join(lines)
            
        return self._format_raw_table(result)

    def _format_raw_table(self, result: QueryResult) -> str:
        """将查询结果格式化为原始表格文本"""
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

    def get_table_ddl(self, table_name: str) -> str:
        """获取表的 DDL 定义语句"""
        schema = self.config.schema or self.config.user
        result = self.execute(f"""
            SELECT DBMS_METADATA.GET_DDL('TABLE', UPPER('{table_name}'), UPPER('{schema}')) FROM DUAL
        """)
        if result.error or not result.rows or not result.rows[0][0]:
            if result.error:
                # 尝试用较通用的回退方案：只查询列信息自己组装一个简易的 DDL
                cols = self.get_table_columns(table_name)
                if cols:
                    ddl_lines = [f"CREATE TABLE {table_name.upper()} ("]
                    col_defs = []
                    for c in cols:
                        nullable_str = "NULL" if c["nullable"] else "NOT NULL"
                        default_str = f" DEFAULT {c['default']}" if c["default"] else ""
                        col_defs.append(f"    {c['name']} {c['type']}({c['length']}){default_str} {nullable_str}")
                    ddl_lines.append(",\n".join(col_defs))
                    ddl_lines.append(");")
                    return "\n".join(ddl_lines) + f"\n\n-- 提示: DBMS_METADATA 获取失败，以上为根据列元数据自动拼装的简易 DDL。\n-- 错误: {result.error}"
                return f"-- 获取 DDL 失败: {result.error}"
            return f"-- 未找到表 {table_name} 的 DDL 定义"
        return str(result.rows[0][0])
