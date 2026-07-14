"""
问题排查和HINT建议模块

基于达梦《问题跟踪和解决》和《SQL调优》文档，实现：
- 配置参数查看 (SF_GET_PARA_VALUE)
- HINT优化建议生成器 (USE_HASH/USE_NL/INDEX/ORDER等)
- 数据物理一致性检查指引 (dmdbchk)
- 数据库布局优化建议
"""
import re
import copy
from dataclasses import dataclass, field
from core.dm_connector import DMConnector


def _insert_hint(sql: str, hint: str) -> str:
    """在SQL的SELECT关键字后插入HINT，兼容大小写"""
    return re.sub(r'(?i)^(\s*SELECT\s+)', lambda m: f'{m.group(1)}{hint} ', sql, count=1)


@dataclass
class ParamInfo:
    """配置参数信息"""
    name: str
    ini_value: str = ""        # INI文件中的值
    mem_value: str = ""        # 内存中的值
    description: str = ""      # 参数说明
    recommend: str = ""        # 推荐值
    is_dynamic: bool = True    # 是否动态参数


@dataclass
class HintSuggestion:
    """HINT建议"""
    hint_text: str             # HINT文本
    description: str           # 说明
    sql_with_hint: str         # 加了HINT的完整SQL
    reason: str                # 建议原因


@dataclass
class HintAnalysisResult:
    """HINT分析结果"""
    suggestions: list[HintSuggestion] = field(default_factory=list)
    summary: str = ""


class ParamChecker:
    """配置参数检查器"""

    # 关键调优参数
    KEY_PARAMS = [
        ParamInfo(name="ENABLE_MONITOR", description="监控开关", recommend="1", is_dynamic=True),
        ParamInfo(name="MONITOR_SQL_EXEC", description="SQL执行监控", recommend="1", is_dynamic=True),
        ParamInfo(name="OPTIMIZER_MODE", description="优化器模式(0=原始,1=新优化器)", recommend="1", is_dynamic=True),
        ParamInfo(name="FIRST_ROWS", description="优先返回行数(影响响应时间)", recommend="根据业务设置", is_dynamic=True),
        ParamInfo(name="MAX_PARALLEL_DEGREE", description="最大并行度", recommend="根据CPU核数设置", is_dynamic=True),
        ParamInfo(name="PARALLEL_POLICY", description="并行策略(0=关闭,1=自动,2=手动)", recommend="1", is_dynamic=True),
        ParamInfo(name="BUFFER", description="缓冲池大小", recommend="根据内存设置", is_dynamic=True),
        ParamInfo(name="HJ_BUF_SIZE", description="哈希连接缓冲大小", recommend="增大可提升大表JOIN", is_dynamic=True),
        ParamInfo(name="SORT_BUF_SIZE", description="排序缓冲大小", recommend="增大可减少排序刷盘", is_dynamic=True),
        ParamInfo(name="MAX_SESSIONS", description="最大会话数", recommend="根据并发设置", is_dynamic=True),
        ParamInfo(name="SVR_LOG", description="SQL日志开关", recommend="排查时开启,平时关闭", is_dynamic=True),
        ParamInfo(name="AUTO_STAT_OBJ", description="自动统计信息收集(0=关,1=全部表,2=指定表)", recommend="1", is_dynamic=True),
        ParamInfo(name="OPTIMIZER_DYNAMIC_SAMPLING", description="动态采样(0=关,1-12)", recommend="0(用静态收集)", is_dynamic=True),
        ParamInfo(name="ADAPTIVE_NPLN_FLAG", description="自适应计划开关", recommend="1", is_dynamic=True),
    ]

    def __init__(self, connector: DMConnector):
        self.connector = connector

    def get_param_value(self, param_name: str) -> tuple[str, str]:
        """
        获取参数值

        文档: SF_GET_PARA_VALUE(scope, paraname)
              scope=1: INI文件值, scope=2: 内存值
        返回: (ini_value, mem_value)
        """
        if not self.connector or not self.connector.is_connected:
            return ("", "")

        ini_result = self.connector.execute(
            f"SELECT SF_GET_PARA_VALUE(1, '{param_name}')"
        )
        mem_result = self.connector.execute(
            f"SELECT SF_GET_PARA_VALUE(2, '{param_name}')"
        )

        ini_val = str(ini_result.rows[0][0]) if not ini_result.error and ini_result.rows else "N/A"
        mem_val = str(mem_result.rows[0][0]) if not mem_result.error and mem_result.rows else "N/A"

        return (ini_val, mem_val)

    def check_all_key_params(self) -> list[ParamInfo]:
        """检查所有关键调优参数"""
        results = []
        for param in self.KEY_PARAMS:
            # 深拷贝避免共享可变状态
            p = copy.deepcopy(param)
            ini_val, mem_val = self.get_param_value(p.name)
            p.ini_value = ini_val
            p.mem_value = mem_val
            results.append(p)
        return results

    def set_param(self, param_name: str, value, scope: int = 1) -> bool:
        """
        修改参数值

        文档: SP_SET_PARA_VALUE(scope, paraname, value)
              scope: 0=仅内存(动态), 1=内存+INI(动态), 2=仅INI(静态+动态)
        """
        if not self.connector or not self.connector.is_connected:
            return False

        result = self.connector.execute(
            f"CALL SP_SET_PARA_VALUE({scope}, '{param_name}', {value})"
        )
        return not result.error


class HintAdvisor:
    """
    HINT优化建议生成器

    基于达梦《SQL调优》文档中的HINT使用指南，
    分析SQL并给出HINT优化建议。
    """

    def analyze(self, sql: str, tables: list = None) -> HintAnalysisResult:
        """
        分析SQL并生成HINT建议

        Args:
            sql: SQL语句
            tables: 表信息列表(可选，含索引信息)
        """
        result = HintAnalysisResult()
        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper()

        # 1. 检查是否已有HINT
        if "/*+" in sql_upper:
            result.summary = "SQL中已包含HINT提示，建议先用EXPLAIN验证当前HINT的效果"
            return result

        # 2. 多表连接场景 - 连接方法建议
        join_tables = self._extract_join_tables(sql_stripped)
        if len(join_tables) >= 2:
            self._suggest_join_hints(sql_stripped, join_tables, result)

        # 3. WHERE条件场景 - 索引提示建议
        where_cols = self._extract_where_columns(sql_stripped)
        if where_cols and tables:
            self._suggest_index_hints(sql_stripped, where_cols, tables, result)

        # 4. 统计信息提示
        self._suggest_stat_hint(sql_stripped, join_tables, result)

        # 5. 并行查询建议
        self._suggest_parallel(sql_stripped, result)

        # 6. 优化器模式建议
        self._suggest_optimizer_mode(sql_stripped, result)

        if not result.suggestions:
            result.summary = "未生成HINT建议。建议优先确保统计信息准确，再用EXPLAIN检查执行计划。"
        else:
            result.summary = (
                f"共生成 {len(result.suggestions)} 个HINT建议。"
                f"注意: 使用HINT后务必用EXPLAIN验证执行计划是否改变。"
                f"HINT语法错误不会报错，会被静默忽略。"
            )

        return result

    def _extract_join_tables(self, sql: str) -> list[str]:
        """提取JOIN涉及的表名"""
        tables = []
        # FROM table1, table2 或 JOIN table
        from_match = re.search(r'FROM\s+(.+?)(?:WHERE|GROUP|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if from_match:
            from_text = from_match.group(1)
            # 简单提取表名
            for part in re.split(r',|\s+JOIN\s+|\s+INNER\s+JOIN\s+|\s+LEFT\s+JOIN\s+|\s+RIGHT\s+JOIN\s+', from_text, flags=re.IGNORECASE):
                part = part.strip()
                # 去掉别名
                name_match = re.match(r'(\w+)', part)
                if name_match and name_match.group(1).upper() not in ("SELECT",):
                    tables.append(name_match.group(1))
        return tables

    def _extract_where_columns(self, sql: str) -> list[tuple[str, str]]:
        """提取WHERE条件中的(表, 列)"""
        columns = []
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if where_match:
            where_text = where_match.group(1)
            for m in re.finditer(r'(?:(\w+)\.)?(\w+)\s*[=<>]', where_text):
                table = m.group(1) or ""
                col = m.group(2)
                if col.upper() not in ("AND", "OR", "NOT", "SELECT"):
                    columns.append((table, col))
        return columns

    def _suggest_join_hints(self, sql, tables, result):
        """生成连接方法HINT建议"""
        table_list = ", ".join(tables[:4])  # 最多4个表名

        # 哈希连接建议(大表等值连接)
        if re.search(r'=\s*\w+\.\w+', sql, re.IGNORECASE):
            hint = f"/*+ USE_HASH({table_list}) */"
            result.suggestions.append(HintSuggestion(
                hint_text=hint,
                description="强制使用哈希连接(适合大表等值连接)",
                sql_with_hint=_insert_hint(sql, hint),
                reason="大表等值连接场景下，HASH JOIN通常比NESTED LOOP效率更高。"
                       "如果执行计划显示NESTED LOOP但驱动表数据量大，建议尝试此HINT。",
            ))

            # 嵌套循环建议(小表驱动)
            hint_nl = f"/*+ USE_NL({table_list}) */"
            result.suggestions.append(HintSuggestion(
                hint_text=hint_nl,
                description="强制使用嵌套循环连接(适合小表驱动+内表有索引)",
                sql_with_hint=_insert_hint(sql, hint_nl),
                reason="如果驱动表结果集很小且内表连接列有索引，"
                       "NESTED LOOP可能比HASH JOIN更快(无需建哈希表)。",
            ))

        # 连接顺序建议
        if len(tables) >= 3:
            order_hint = f"/*+ ORDER({', '.join(tables[:4])}) */"
            result.suggestions.append(HintSuggestion(
                hint_text=order_hint,
                description="指定表连接顺序(小结果集表优先)",
                sql_with_hint=_insert_hint(sql, order_hint),
                reason="多表连接时，连接顺序影响中间结果集大小。"
                       "原则: 能产生较小结果集的表优先连接。",
            ))

    def _suggest_index_hints(self, sql, where_cols, tables, result):
        """生成索引HINT建议"""
        if not isinstance(tables, dict):
            return
        for table_name, table_info in tables.items():
            indexes = table_info.get("indexes", []) if isinstance(table_info, dict) else []
            for idx in indexes:
                idx_cols = idx.get("columns", [])
                for col in where_cols:
                    if col[1] in idx_cols:
                        hint = f"/*+ INDEX({table_name}, {idx['name']}) */"
                        result.suggestions.append(HintSuggestion(
                            hint_text=hint,
                            description=f"指定使用索引 {idx['name']}",
                            sql_with_hint=_insert_hint(sql, hint),
                            reason=f"WHERE条件中的列 {col[1]} 在索引 {idx['name']} 上，"
                                   f"如果优化器未选择此索引，可尝试强制使用。",
                        ))
                        break

    def _suggest_stat_hint(self, sql, tables, result):
        """生成统计信息HINT建议"""
        if tables:
            stat_hint = f"/*+ STAT({tables[0]}, 1M) */"
            result.suggestions.append(HintSuggestion(
                hint_text=stat_hint,
                description=f"手动设置表 {tables[0]} 的行数估算为1M",
                sql_with_hint=_insert_hint(sql, stat_hint),
                reason="如果统计信息缺失或陈旧导致优化器误判表大小，"
                       "可用STAT提示临时指定行数。行数可用K/M/G后缀。"
                       "建议同时执行: DBMS_STATS.GATHER_TABLE_STATS()收集真实统计信息。",
            ))

    def _suggest_parallel(self, sql, result):
        """并行查询建议"""
        sql_upper = sql.upper()
        # 大表扫描/聚合/排序场景适合并行
        if any(kw in sql_upper for kw in ["GROUP BY", "ORDER BY", "COUNT(", "SUM(", "AVG("]):
            hint = "/*+ PARALLEL(4) */"
            result.suggestions.append(HintSuggestion(
                hint_text=hint,
                description="指定并行度为4",
                sql_with_hint=_insert_hint(sql, hint),
                reason="包含聚合/排序的大数据量查询适合并行执行。"
                       "需先设置: SP_SET_PARA_VALUE(1,'PARALLEL_POLICY',1) 开启自动并行。",
            ))

    def _suggest_optimizer_mode(self, sql, result):
        """优化器模式建议"""
        hint = "/*+ OPTIMIZER_MODE(1) */"
        result.suggestions.append(HintSuggestion(
            hint_text=hint,
            description="使用新优化器模式",
            sql_with_hint=_insert_hint(sql, hint),
            reason="新优化器(OPTIMIZER_MODE=1)支持更多优化特性，"
                   "如自适应计划、增强归并连接等。如果当前执行计划不理想可尝试。",
        ))


class TroubleshootGuide:
    """问题排查指引(基于《问题跟踪和解决》文档)"""

    @staticmethod
    def get_troubleshoot_steps() -> list[dict]:
        """获取问题排查步骤"""
        return [
            {
                "step": 1,
                "title": "网络检查",
                "description": "检查网络是否正常",
                "detail": "远程操作有问题但本地正常 → 可能网络故障或带宽耗尽。本地也有问题 → 需进一步分析。",
                "commands": [],
            },
            {
                "step": 2,
                "title": "内存检查",
                "description": "检查数据库内存使用量",
                "detail": "检查是否占用过多内存、是否大量使用页面文件/交换分区。检查内存参数是否正确，是否有连接/游标未释放。",
                "commands": [
                    "SELECT * FROM V$MEM_POOL;",  # 内存池使用情况
                ],
            },
            {
                "step": 3,
                "title": "CPU检查",
                "description": "检查CPU使用率",
                "detail": "CPU持续90%+需分析: 存储过程死循环 / SQL执行计划差 / 负载过大。",
                "commands": [
                    "SELECT * FROM V$SESSIONS WHERE STATE = 'ACTIVE';",  # 活跃会话
                ],
            },
            {
                "step": 4,
                "title": "I/O检查",
                "description": "检查I/O性能",
                "detail": "I/O瓶颈常见原因: 存储规划不足 / 缺少索引导致全表扫描。查看SQL执行计划分析I/O消耗。",
                "commands": [
                    "SELECT NAME, N_PAGES, N_LOGIC_READS, RAT_HIT FROM V$BUFFERPOOL;",  # 缓冲命中率
                ],
            },
            {
                "step": 5,
                "title": "日志检查",
                "description": "查看系统日志和SQL日志",
                "detail": "系统日志: dm_<实例名>_YYYYMM.log (记录启动关闭/关键错误)。SQL日志: 需开启SVR_LOG参数。",
                "commands": [
                    "CALL SP_SET_PARA_VALUE(1, 'SVR_LOG', 1);",  # 开启SQL日志
                ],
            },
            {
                "step": 6,
                "title": "数据一致性检查",
                "description": "使用dmdbchk检查数据物理一致性",
                "detail": "在数据库正常关闭的情况下使用dmdbchk校验数据文件完整性。完成后生成dbchk_err.txt报告。",
                "commands": [
                    "dmdbchk path=/opt/dmdbms/bin/dm.ini",  # 基本检查
                    "dmdbchk path=/opt/dmdbms/bin/dm.ini CHECK_REC=1",  # 检查记录
                ],
            },
        ]

    @staticmethod
    def get_layout_advice() -> list[str]:
        """获取数据库布局优化建议"""
        return [
            "日志文件放在独立的物理磁盘上，与数据文件分开存储",
            "预先估算并分配好磁盘空间，避免运行中频繁扩充数据文件",
            "不同表空间尽量分布在不同磁盘上，充分利用并行I/O",
            "分区表的分区尽量放到不同表空间",
            "分析型应用: 页大小和簇大小取最大值；列存储时每列存独立表",
            "OLTP: 小页大小(8K/16K); OLAP: 大页大小(32K)",
        ]
