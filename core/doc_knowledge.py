"""
达梦官方文档知识库模块

将4份达梦技术文档的核心知识提炼为结构化数据，
供GUI界面在每个功能上方显示对应的文档内容和操作提示。

文档来源:
1. 动态管理和性能视图 - https://eco.dameng.com/document/dm/zh-cn/pm/dynamic-management.html
2. 问题跟踪和解决 - https://eco.dameng.com/document/dm/zh-cn/pm/tracking-resolution.html
3. 查询优化 - https://eco.dameng.com/document/dm/zh-cn/pm/query-optimization.html
4. SQL调优 - https://eco.dameng.com/document/dm/zh-cn/pm/sql-tuning.html
"""
from dataclasses import dataclass, field


@dataclass
class DocSnippet:
    """文档知识片段"""
    feature_id: str               # 功能ID
    feature_name: str             # 功能名称
    doc_source: str               # 文档来源
    doc_url: str                  # 文档URL
    doc_content: str              # 文档核心内容(精炼)
    tips: str                     # 操作提示
    sql_examples: list = field(default_factory=list)  # 相关SQL示例


class DocKnowledgeBase:
    """达梦文档知识库"""

    # 文档URL
    URL_DYNAMIC = "https://eco.dameng.com/document/dm/zh-cn/pm/dynamic-management.html"
    URL_TRACKING = "https://eco.dameng.com/document/dm/zh-cn/pm/tracking-resolution.html"
    URL_OPTIMIZATION = "https://eco.dameng.com/document/dm/zh-cn/pm/query-optimization.html"
    URL_TUNING = "https://eco.dameng.com/document/dm/zh-cn/pm/sql-tuning.html"
    URL_APPENDIX4 = "https://eco.dameng.com/document/dm/zh-cn/pm/dm8-admin-manual-appendix4.html"

    def __init__(self):
        self._snippets: dict[str, DocSnippet] = {}
        self._init_snippets()

    def _init_snippets(self):
        """初始化所有文档知识片段"""

        # ====================================================================
        # 1. 动态管理和性能视图
        # ====================================================================

        self._add(DocSnippet(
            feature_id="slow_sql",
            feature_name="慢SQL抓取",
            doc_source="动态管理和性能视图 / SQL调优",
            doc_url=self.URL_DYNAMIC,
            doc_content=(
                "达梦数据库提供动态性能视图自动收集数据库活动信息。"
                "V$LONG_EXEC_SQLS 显示最近1000条执行时间较长的SQL语句，"
                "V$SYSTEM_LONG_EXEC_SQLS 显示服务器启动以来执行时间最长的20条SQL语句。"
                "使用前需确保 INI 参数 ENABLE_MONITOR=1 已开启监控。\n\n"
                "V$SQL_HISTORY 记录SQL执行历史，包含 SESS_ID、TOP_SQL_TEXT、TIME_USED 字段，"
                "可查看每条SQL的执行耗时。"
            ),
            tips=(
                "1. 确保已以DBA身份连接数据库\n"
                "2. 如果查询无结果，检查 ENABLE_MONITOR 参数是否开启:\n"
                "   SELECT SF_GET_PARA_VALUE(1, 'ENABLE_MONITOR');\n"
                "3. 可设置 MONITOR_SQL_EXEC=1 开启SQL执行监控\n"
                "4. V$LONG_EXEC_SQLS 最多保留最近1000条记录"
            ),
            sql_examples=[
                "SELECT * FROM V$LONG_EXEC_SQLS;",
                "SELECT * FROM V$SYSTEM_LONG_EXEC_SQLS;",
                "SELECT SESS_ID, TOP_SQL_TEXT, TIME_USED FROM V$SQL_HISTORY ORDER BY TIME_USED DESC;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="session_monitor",
            feature_name="会话监控",
            doc_source="动态管理和性能视图",
            doc_url=self.URL_DYNAMIC,
            doc_content=(
                "V$SESSIONS 动态视图提供当前所有会话信息，包括会话ID、SQL文本、"
                "状态(ACTIVE/IDLE)、创建时间、客户端主机等。"
                "V$CONNECT 提供连接信息，V$STMTS 提供语句信息。\n\n"
                "通过查询 V$SESSIONS 可以了解:\n"
                "- 当前有多少活跃连接\n"
                "- 各会话正在执行的SQL\n"
                "- 长时间运行的会话\n"
                "- 客户端来源信息"
            ),
            tips=(
                "1. 重点关注 STATE='ACTIVE' 的会话\n"
                "2. 可通过 CREATE_TIME 排查长时间未释放的会话\n"
                "3. 如需终止异常会话: SP_CLOSE_SESSION(SESS_ID);\n"
                "4. 结合 V$TRX 查看会话关联的事务和锁信息"
            ),
            sql_examples=[
                "SELECT SESS_ID, SQL_TEXT, STATE, CREATE_TIME, CLNT_HOST FROM V$SESSIONS;",
                "SELECT * FROM V$SESSIONS WHERE STATE = 'ACTIVE';",
            ],
        ))

        self._add(DocSnippet(
            feature_id="node_timing",
            feature_name="执行节点耗时分析",
            doc_source="动态管理和性能视图",
            doc_url=self.URL_DYNAMIC,
            doc_content=(
                "V$SQL_NODE_NAME 记录执行节点名称，V$SQL_NODE_HISTORY 记录每个执行节点的时间。"
                "通过两个视图的 TYPE$ 字段做等值连接，可以获取SQL执行计划中各节点的耗时。\n\n"
                "执行一条SQL后，查询其执行节点所花费时间(假设执行ID EXEC_ID 为4):\n"
                "SELECT N.NAME, TIME_USED, N_ENTER FROM V$SQL_NODE_NAME N, V$SQL_NODE_HISTORY H "
                "WHERE N.TYPE$ = H.TYPE$ AND EXEC_ID = 4;\n\n"
                "常见节点: CSCN2(聚集索引扫描), SSEK2(索引等值查找), "
                "HJOIN(哈希连接), NLI2(嵌套循环), SLCT2(选择过滤), "
                "HAGR2(哈希聚合), PRJT2(投影), SORT(排序)"
            ),
            tips=(
                "1. 先执行目标SQL，获取当前 EXEC_ID\n"
                "2. 然后立即查询 V$SQL_NODE_HISTORY (数据会被后续SQL覆盖)\n"
                "3. TIME_USED 单位为微秒，N_ENTER 为节点执行次数\n"
                "4. 重点关注 TIME_USED 最高的节点，即为性能瓶颈"
            ),
            sql_examples=[
                "SELECT N.NAME, TIME_USED, N_ENTER FROM V$SQL_NODE_NAME N, V$SQL_NODE_HISTORY H WHERE N.TYPE$ = H.TYPE$ AND EXEC_ID = <执行ID>;",
                "SELECT * FROM V$SQL_NODE_NAME;",  # 查看所有节点类型
            ],
        ))

        self._add(DocSnippet(
            feature_id="system_status",
            feature_name="系统状态检查",
            doc_source="动态管理和性能视图",
            doc_url=self.URL_DYNAMIC,
            doc_content=(
                "系统信息视图:\n"
                "- V$INSTANCE: 数据库实例信息(版本/启动时间/状态)\n"
                "- V$TABLESPACE: 表空间信息\n"
                "- V$DATAFILE: 数据文件信息\n"
                "- V$BUFFERPOOL: 缓冲池信息(页数/读取页数/命中率)\n"
                "- V$MEM_POOL: 内存池使用情况\n\n"
                "命中率查询:\n"
                "SELECT NAME, N_PAGES, N_LOGIC_READS, RAT_HIT FROM V$BUFFERPOOL;\n"
                "RAT_HIT 为缓冲命中率，应接近1.0(即100%)，过低说明需要增大缓冲池。"
            ),
            tips=(
                "1. V$INSTANCE 的 STATUS$ 应为 OPEN 表示正常运行\n"
                "2. 缓冲命中率低于90%时考虑增大 BUFFER 参数\n"
                "3. V$TABLESPACE 检查表空间使用率，防止空间不足\n"
                "4. V$MEM_POOL 检查内存池是否异常增长"
            ),
            sql_examples=[
                "SELECT NAME, INSTANCE_NAME, SVR_VERSION, START_TIME, STATUS$ FROM V$INSTANCE;",
                "SELECT NAME, N_PAGES, N_LOGIC_READS, RAT_HIT FROM V$BUFFERPOOL;",
                "SELECT * FROM V$TABLESPACE;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="lock_wait",
            feature_name="锁和事务等待",
            doc_source="动态管理和性能视图",
            doc_url=self.URL_DYNAMIC,
            doc_content=(
                "事务和锁信息视图:\n"
                "- V$TRX: 所有事务信息\n"
                "- V$TRXWAIT: 事务等待信息(谁在等谁)\n"
                "- V$LOCK: 事务锁信息(TID锁/对象锁)\n\n"
                "查询系统中上锁的事务:\n"
                "SELECT TRX_ID, LTYPE, LMODE, TABLE_ID FROM V$LOCK;\n\n"
                "LMODE 说明: X=排他锁, S=共享锁, IX=意向排他锁, IS=意向共享锁\n"
                "LTYPE 说明: OBJECT=对象锁, TID=TID锁"
            ),
            tips=(
                "1. V$TRXWAIT 可发现阻塞链: 谁阻塞了谁\n"
                "2. 长时间持有X锁的事务可能是性能问题根源\n"
                "3. 可结合 V$SESSIONS 找到对应会话\n"
                "4. 必要时可 SP_CLOSE_SESSION(SESS_ID) 终止阻塞会话"
            ),
            sql_examples=[
                "SELECT TRX_ID, LTYPE, LMODE, TABLE_ID FROM V$LOCK;",
                "SELECT * FROM V$TRXWAIT;",  # 查看事务等待
                "SELECT * FROM V$TRX WHERE STATE = 'ACTIVE';",
            ],
        ))

        # ====================================================================
        # 2. 问题跟踪和解决
        # ====================================================================

        self._add(DocSnippet(
            feature_id="param_check",
            feature_name="配置参数查看",
            doc_source="问题跟踪和解决",
            doc_url=self.URL_TRACKING,
            doc_content=(
                "DM数据库提供系统函数查看和修改配置参数:\n\n"
                "查看参数:\n"
                "- SF_GET_PARA_VALUE(scope, paraname): 获取整型参数值\n"
                "- SF_GET_PARA_DOUBLE_VALUE(scope, paraname): 获取浮点型参数值\n"
                "- SF_GET_PARA_STRING_VALUE(scope, paraname): 获取字符串参数值\n\n"
                "scope: 1=INI文件中的值, 2=内存中的值\n\n"
                "修改参数:\n"
                "- SP_SET_PARA_VALUE(scope, paraname, value)\n"
                "- SP_SET_PARA_DOUBLE_VALUE(scope, paraname, value)\n"
                "scope: 0=仅内存(动态参数), 1=内存+INI(动态参数), 2=仅INI(静态+动态)\n\n"
                "关键调优参数:\n"
                "- ENABLE_MONITOR: 监控开关(建议1)\n"
                "- MONITOR_SQL_EXEC: SQL执行监控(建议1)\n"
                "- OPTIMIZER_MODE: 优化器模式(0=原始,1=新优化器)\n"
                "- FIRST_ROWS: 优先返回行数(影响响应时间)\n"
                "- MAX_PARALLEL_DEGREE: 并行度\n"
                "- BUFFER: 缓冲池大小\n"
                "- HJ_BUF_SIZE: 哈希连接缓冲大小\n"
                "- SORT_BUF_SIZE: 排序缓冲大小"
            ),
            tips=(
                "1. 修改参数前先查看当前值: SF_GET_PARA_VALUE(2, '参数名')\n"
                "2. 静态参数只能用 scope=2 修改，需重启生效\n"
                "3. 动态参数用 scope=1 可立即生效并写入INI\n"
                "4. 生产环境调参前建议先在测试环境验证\n"
                "5. 只有DBA角色用户才能修改参数"
            ),
            sql_examples=[
                "SELECT SF_GET_PARA_VALUE(2, 'ENABLE_MONITOR');",
                "SELECT SF_GET_PARA_VALUE(2, 'OPTIMIZER_MODE');",
                "SELECT SF_GET_PARA_VALUE(2, 'BUFFER');",
                "CALL SP_SET_PARA_VALUE(1, 'ENABLE_MONITOR', 1);",
            ],
        ))

        self._add(DocSnippet(
            feature_id="troubleshoot",
            feature_name="问题排查指引",
            doc_source="问题跟踪和解决",
            doc_url=self.URL_TRACKING,
            doc_content=(
                "系统问题排查应依次检查以下方面:\n\n"
                "1. 网络是否正常\n"
                "   - 远程操作有问题但本地正常 → 可能网络故障或带宽耗尽\n"
                "   - 本地也有问题 → 需进一步分析\n\n"
                "2. 内存使用量\n"
                "   - 检查数据库是否占用过多内存\n"
                "   - 是否大量使用页面文件(Win)/交换分区(Linux)\n"
                "   - 检查内存参数是否设置错误\n"
                "   - 检查是否有连接/游标未释放\n\n"
                "3. CPU使用率\n"
                "   - CPU持续90%+ → 分析原因\n"
                "   - 可能: 存储过程死循环 / SQL执行计划差 / 负载过大\n"
                "   - 解决: 修正逻辑 / 建合适索引 / 升级硬件\n\n"
                "4. I/O是否正常\n"
                "   - I/O瓶颈是性能低下的常见原因\n"
                "   - 可能: 存储规划不足 / 缺少索引导致全表扫描\n"
                "   - 查看SQL执行计划分析I/O消耗\n\n"
                "5. 系统日志和SQL日志\n"
                "   - 系统日志: dm_<实例名>_YYYYMM.log\n"
                "   - SQL日志: 需设置 SVR_LOG 开启, dmsql_<实例名>_日期_时间.log"
            ),
            tips=(
                "1. 排查时按 网络→内存→CPU→I/O→日志 顺序逐一排除\n"
                "2. 系统日志记录启动/关闭时间和关键错误\n"
                "3. 开启SQL日志: CALL SP_SET_PARA_VALUE(1, 'SVR_LOG', 1);\n"
                "4. dmdbchk工具可检查数据物理一致性(需停库):\n"
                "   dmdbchk path=/opt/dmdbms/bin/dm.ini"
            ),
            sql_examples=[
                "-- 查看当前监控状态",
                "SELECT SF_GET_PARA_VALUE(2, 'ENABLE_MONITOR') AS ENABLE_MONITOR,",
                "       SF_GET_PARA_VALUE(2, 'MONITOR_SQL_EXEC') AS MONITOR_SQL_EXEC,",
                "       SF_GET_PARA_VALUE(2, 'SVR_LOG') AS SVR_LOG;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="db_layout",
            feature_name="数据库布局优化建议",
            doc_source="问题跟踪和解决",
            doc_url=self.URL_TRACKING,
            doc_content=(
                "数据库布局直接影响I/O性能，建议遵循以下原则:\n\n"
                "1. 日志文件放在独立的物理磁盘上，与数据文件分开存储\n"
                "2. 预先估算并分配好磁盘空间，避免运行中频繁扩充数据文件\n"
                "3. 不同表空间尽量分布在不同磁盘上，充分利用并行I/O\n"
                "4. 分区表的分区尽量放到不同表空间\n"
                "5. 分析型应用: 页大小和簇大小取最大值；列存储时每列存独立表\n\n"
                "DM数据库动态INI参数分为系统级和会话级:\n"
                "- 系统级: 全局生效\n"
                "- 会话级: SF_SET_SESSION_PARA_VALUE 设置，仅当前会话生效\n"
                "  SP_RESET_SESSION_PARA_VALUE 重置为系统值"
            ),
            tips=(
                "1. 查看表空间和数据文件分布:\n"
                "   SELECT * FROM V$TABLESPACE; SELECT * FROM V$DATAFILE;\n"
                "2. 检查表空间使用率，提前扩容\n"
                "3. 日志文件和数据文件混放是常见I/O瓶颈\n"
                "4. OLTP: 小页大小(8K/16K); OLAP: 大页大小(32K)"
            ),
            sql_examples=[
                "SELECT T.NAME AS TABLESPACE_NAME, T.STATUS$, D.PATH, D.TOTAL_SIZE FROM V$TABLESPACE T, V$DATAFILE D WHERE T.ID = D.GROUP_ID;",
            ],
        ))

        # ====================================================================
        # 3. 查询优化
        # ====================================================================

        self._add(DocSnippet(
            feature_id="plan_explain",
            feature_name="执行计划解读",
            doc_source="查询优化",
            doc_url=self.URL_OPTIMIZATION,
            doc_content=(
                "DM执行计划是查询优化器为SQL设计的执行方式，展示为一棵树:\n"
                "- 控制流从上向下传递，数据流从下向上传递\n"
                "- [代价, 行数, 字节数] 表示估算的操作符代价、处理记录行数、每行字节数\n\n"
                "获取方式:\n"
                "1. EXPLAIN <SQL> → 文本格式执行计划\n"
                "2. EXPLAIN FOR <SQL> → 表格格式(含COST/CPU_COST/IO_COST/ROW_NUMS等)\n\n"
                "EXPLAIN FOR 输出列:\n"
                "- OPERATION: 操作符名称\n"
                "- TAB_NAME/IDX_NAME: 表名/索引名\n"
                "- SCAN_TYPE: 扫描类型(ASC/DESC)\n"
                "- SCAN_RANGE: 扫描范围\n"
                "- ROW_NUMS: 预测行数\n"
                "- COST: 代价, CPU_COST: CPU代价, IO_COST: IO代价\n"
                "- FILTER: 过滤条件, JOIN_COND: 连接条件\n"
                "- ADVICE_INFO: 优化建议\n\n"
                "常见操作符:\n"
                "CSCN2(聚集索引扫描), SSCN(索引全扫描), SSEK2(索引等值查找),\n"
                "CSEK2(聚集索引范围查找), BLKUP2(回表查找),\n"
                "HASH2 INNER JOIN(哈希内连接), NEST LOOP JOIN2(嵌套循环),\n"
                "MERGE INNER JOIN(归并连接), SLCT2(选择), PRJT2(投影),\n"
                "HAGR2(哈希聚合), SORT3(排序), AAGR2(简单聚合)"
            ),
            tips=(
                "1. 关注 COST 和 ROW_NUMS 高的节点\n"
                "2. CSCN2 表示全表扫描(聚集索引扫描)，大表上需优化\n"
                "3. BLKUP2 表示回表操作，可通过覆盖索引避免\n"
                "4. Predicate Information 显示各节点的过滤和连接条件\n"
                "5. ADVICE_INFO 列可能直接给出优化建议"
            ),
            sql_examples=[
                "EXPLAIN SELECT * FROM 表名 WHERE 条件;",
                "EXPLAIN FOR SELECT * FROM 表名 WHERE 条件;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="access_path",
            feature_name="数据访问路径分析",
            doc_source="查询优化",
            doc_url=self.URL_OPTIMIZATION,
            doc_content=(
                "访问路径决定了从基表获取数据的代价:\n\n"
                "1. 全表扫描(CSCN2)\n"
                "   - 扫描表中所有数据\n"
                "   - 适合检索大部分数据(>10-20%)\n"
                "   - OLTP中应避免，OLAP中常用\n\n"
                "2. 聚集索引扫描\n"
                "   - 包含表中所有列值，只需扫描一个索引\n"
                "   - DM中每张表有且仅有一个聚集索引\n\n"
                "3. 二级索引扫描(SSEK2/SSCN)\n"
                "   - 只包含索引列和ROWID\n"
                "   - 查询列不在索引中时需BLKUP2回表\n"
                "   - 覆盖索引(包含所有查询列)可避免回表\n\n"
                "优化器选择访问路径基于:\n"
                "- WHERE条件可用的访问路径\n"
                "- 每条路径的代价估算\n"
                "- 统计信息(选择率/基数)\n"
                "- HINT提示"
            ),
            tips=(
                "1. 高选择率(过滤掉大部分数据) → 用索引扫描\n"
                "2. 低选择率(返回大部分数据) → 用全表扫描更高效\n"
                "3. 覆盖索引: 将SELECT的列都加入索引，避免BLKUP2回表\n"
                "4. 组合索引: 等值条件列作为前导列"
            ),
            sql_examples=[
                "-- 查看表的索引信息",
                "SELECT I.INDEX_NAME, I.UNIQUENESS, LISTAGG(C.COLUMN_NAME,', ') WITHIN GROUP(ORDER BY C.COLUMN_POSITION) AS COLS FROM ALL_INDEXES I, ALL_IND_COLUMNS C WHERE I.TABLE_NAME='表名' AND I.INDEX_NAME=C.INDEX_NAME GROUP BY I.INDEX_NAME, I.UNIQUENESS;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="join_method",
            feature_name="连接方式分析",
            doc_source="查询优化",
            doc_url=self.URL_OPTIMIZATION,
            doc_content=(
                "多表连接时需考虑: 访问路径、连接方式、连接顺序\n\n"
                "连接方式:\n"
                "1. 哈希连接(HASH2 INNER JOIN)\n"
                "   - 等值连接首选，大数据量效率高\n"
                "   - 以一张表连接列为哈希键构造哈希表\n"
                "   - 代价: 建哈希表 + 哈希探测\n"
                "   - 内存消耗较大(HJ_BUF_SIZE)\n\n"
                "2. 嵌套循环连接(NEST LOOP JOIN)\n"
                "   - 非等值连接或驱动表数据量小时使用\n"
                "   - 驱动表每条记录遍历内表\n"
                "   - 内表连接列有索引时效率好\n\n"
                "3. 归并连接(MERGE INNER JOIN)\n"
                "   - 连接列均为索引列时使用\n"
                "   - 按索引顺序归并，一趟完成\n"
                "   - 非等值连接(</<=/>/>=)也适用\n\n"
                "4. 外连接\n"
                "   - 左外: 外表数据全返回，无匹配填NULL\n"
                "   - 右外: 同左外，外表不同\n"
                "   - 全外: 左外+右外的UNION\n\n"
                "5. 半连接(子查询转换)\n"
                "   - 哈希半连接/索引半连接/归并半连接/嵌套半连接\n"
                "   - 等值条件选哈希/索引/归并，非等值选嵌套\n\n"
                "连接顺序原则: 能产生较小结果集的表优先连接"
            ),
            tips=(
                "1. 大表等值连接 → 期望HASH JOIN\n"
                "2. 驱动表小 + 内表有索引 → NEST LOOP也可高效\n"
                "3. 可用HINT强制连接方式:\n"
                "   /*+ USE_HASH(T1,T2) */ 或 /*+ USE_NL(T1,T2) */\n"
                "4. 连接顺序: /*+ ORDER(T1,T2,T3) */\n"
                "5. 对小表建HASH表性能更好"
            ),
            sql_examples=[
                "-- 强制使用哈希连接",
                "SELECT /*+ USE_HASH(T1, T2) */ * FROM T1, T2 WHERE T1.ID = T2.ID;",
                "-- 强制使用嵌套循环",
                "SELECT /*+ USE_NL(T1, T2) */ * FROM T1, T2 WHERE T1.ID = T2.ID;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="stats_info",
            feature_name="统计信息管理",
            doc_source="查询优化",
            doc_url=self.URL_OPTIMIZATION,
            doc_content=(
                "统计信息是优化器代价计算的依据，直接影响执行计划质量。\n\n"
                "统计信息种类:\n"
                "- 表统计: 行数、页数\n"
                "- 列统计: 数据分布(直方图)\n"
                "- 索引统计: 索引列分布\n\n"
                "直方图类型:\n"
                "- 频率直方图: 不同值<1万个时使用，每桶高度不同\n"
                "- 等高直方图: 不同值≥1万个时使用，每桶高度相同\n\n"
                "收集方式:\n"
                "1. 静态收集(推荐):\n"
                "   - DBMS_STATS.GATHER_TABLE_STATS('模式','表名')\n"
                "   - DBMS_STATS.GATHER_INDEX_STATS('模式','表名','索引名')\n"
                "   - DBMS_STATS.GATHER_SCHEMA_STATS('模式')\n"
                "   - STAT 30 ON 模式.表名(列名)  -- 采样率30%\n"
                "   - CALL SP_TAB_INDEX_STAT_INIT('模式','表名')\n\n"
                "2. 动态收集:\n"
                "   - OPTIMIZER_DYNAMIC_SAMPLING 参数(0-12)\n"
                "   - 0=不启用, 1-10=启用(采样10%-100%), 11=自动采样, 12=同11但保存\n\n"
                "3. 自动收集:\n"
                "   - AUTO_STAT_OBJ=1或2时开启\n"
                "   - SP_CREATE_AUTO_STAT_TRIGGER 设置触发器\n"
                "   - STALE_PERCENT 控制过期阈值(默认10%)\n\n"
                "查看统计信息:\n"
                "- 系统表 SYSSTATS, SYSSTATTABLEIDU\n"
                "- DBMS_STATS.COLUMN_STATS_SHOW / TABLE_STATS_SHOW / INDEX_STATS_SHOW"
            ),
            tips=(
                "1. 推荐静态收集，不影响查询性能\n"
                "2. 数据变化超过10%时应重新收集\n"
                "3. 收集前先创建系统包:\n"
                "   CALL SP_CREATE_SYSTEM_PACKAGES(1, 'DBMS_STATS');\n"
                "4. 自动收集需设置 AUTO_STAT_OBJ=1\n"
                "5. 查看上次收集时间: ALL_TABLES.LAST_ANALYZED"
            ),
            sql_examples=[
                "-- 手动收集表统计信息",
                "CALL SP_CREATE_SYSTEM_PACKAGES(1, 'DBMS_STATS');",
                "BEGIN DBMS_STATS.GATHER_TABLE_STATS('模式名','表名'); END;",
                "-- 使用STAT语法收集列统计",
                "STAT 30 ON 模式名.表名(列名);",
                "-- 收集索引统计",
                "CALL SP_TAB_INDEX_STAT_INIT('模式名','表名');",
            ],
        ))

        # ====================================================================
        # 4. SQL调优
        # ====================================================================

        self._add(DocSnippet(
            feature_id="hint_advisor",
            feature_name="HINT优化建议",
            doc_source="SQL调优",
            doc_url=self.URL_TUNING,
            doc_content=(
                "当优化器因统计信息缺失或陈旧而选择了差的执行计划时，"
                "DBA可通过HINT人工干预优化器的计划选择。\n\n"
                "HINT语法:\n"
                "  SELECT /*+ HINT1 [HINT2]*/ 列名 FROM 表名 WHERE ...;\n\n"
                "常用HINT:\n\n"
                "1. 索引提示:\n"
                "   /*+ INDEX(表名, 索引名) */  -- 指定使用某索引\n"
                "   /*+ NO_INDEX(表名, 索引名) */  -- 禁止使用某索引\n"
                "   一个语句最多指定8个索引\n\n"
                "2. 连接方法提示:\n"
                "   /*+ USE_HASH(T1, T2) */  -- 强制哈希连接\n"
                "   /*+ NO_USE_HASH(T1, T2) */  -- 禁止哈希连接\n"
                "   /*+ USE_NL(T1, T2) */  -- 强制嵌套循环\n"
                "   /*+ NO_USE_NL(T1, T2) */  -- 禁止嵌套循环\n"
                "   /*+ USE_MERGE(T1, T2) */  -- 强制归并连接(需索引列)\n"
                "   /*+ USE_NL_WITH_INDEX(T1, 索引名) */  -- 索引连接\n\n"
                "3. 连接顺序提示:\n"
                "   /*+ ORDER(T1, T2, T3) */  -- 指定连接顺序\n\n"
                "4. 统计信息提示:\n"
                "   /*+ STAT(表名, 行数) */  -- 手动设置表行数估算\n"
                "   行数可用 K(千)/M(百万)/G(十亿) 后缀\n\n"
                "5. INI参数提示(语句级):\n"
                "   /*+ ENABLE_HASH_JOIN(1) */  -- 启用哈希连接\n"
                "   /*+ OPTIMIZER_MODE(1) */  -- 使用新优化器\n\n"
                "6. 其他:\n"
                "   /*+ PLAN_NO_CACHE */  -- 禁用计划缓存\n"
                "   /*+ PARALLEL(4) */  -- 指定并行度\n\n"
                "注意: HINT语法错误不会报错，会被静默忽略。"
            ),
            tips=(
                "1. HINT是调优的最后一招，优先确保统计信息准确\n"
                "2. 使用HINT后务必用EXPLAIN验证执行计划是否改变\n"
                "3. 索引提示中表有别名时必须用别名\n"
                "4. USE_MERGE要求连接列都是索引列\n"
                "5. PARALLEL需配合 PARALLEL_POLICY>0 使用\n"
                "6. 可通过 V$HINT_INI_INFO 查询支持HINT的INI参数"
            ),
            sql_examples=[
                "-- 指定索引",
                "SELECT /*+ INDEX(t1, idx_t1_id) */ * FROM t1 WHERE id > 100;",
                "-- 强制哈希连接",
                "SELECT /*+ USE_HASH(a,b) */ * FROM t1 a, t2 b WHERE a.id=b.id;",
                "-- 指定连接顺序+方法",
                "SELECT /*+ ORDER(T1,T2) USE_HASH(T1,T2) */ * FROM T1, T2 WHERE T1.ID=T2.ID;",
                "-- 手动设置表行数估算",
                "SELECT /*+ STAT(T_S, 1M) */ * FROM T_S WHERE C1 <= 10;",
            ],
        ))

        self._add(DocSnippet(
            feature_id="sql_best_practice",
            feature_name="SQL开发最佳实践",
            doc_source="SQL调优",
            doc_url=self.URL_TUNING,
            doc_content=(
                "达梦官方SQL开发优化原则:\n\n"
                "1. 避免SELECT *\n"
                "   - 每列数据都需向上传递，增加IO和内存消耗\n"
                "   - 列存储表的IO优势会损耗殆尽\n"
                "   - 应明确列出需要的列名\n\n"
                "2. 避免OR子句\n"
                "   - OR会被转换为类似UNION的查询\n"
                "   - 某一侧不能用索引则全表扫描\n"
                "   - 同列OR改用IN: city='A' OR city='B' → city IN('A','B')\n\n"
                "3. 避免困难的正则表达式\n"
                "   - '%keyword%' 开头结尾都是通配符 → 无法用索引\n"
                "   - 'keyword%' 只开头有通配符 → 可建REVERSE函数索引\n"
                "   - 'key%' 开头无通配符 → 可优化为范围查询 a>='key' AND a<'kez'\n\n"
                "4. 使用COUNT(*)而非COUNT(列名)\n"
                "   - COUNT(*)可利用索引行数信息，无需读实际数据\n"
                "   - COUNT(列名)需读数据且不计算NULL值\n\n"
                "5. UNION ALL优于UNION\n"
                "   - UNION需建哈希表去重，可能刷盘\n"
                "   - 不需要去重时用UNION ALL\n\n"
                "6. 优化GROUP BY\n"
                "   - GROUP BY列上有索引 → 使用SAGR(排序分组)避免缓存\n"
                "   - 无索引时用HAGR(哈希分组)需缓存中间结果\n"
                "   - HAVING中非聚合条件可移到WHERE中\n\n"
                "7. 避免功能相似的重复索引\n"
                "   - 索引越多，优化器试探时间越长\n"
                "   - 增删改频繁时索引维护开销大\n"
                "   - 函数索引计算开销更大\n\n"
                "8. 灵活使用伪表(SYSDUAL)\n"
                "   - 判断是否存在记录用EXISTS而非COUNT(*)\n"
                "   - SELECT 'A' FROM SYSDUAL WHERE EXISTS(SELECT 1 FROM t WHERE ...)"
            ),
            tips=(
                "1. 始终明确列名，不用SELECT *\n"
                "2. 同列OR改IN，不同列OR考虑UNION ALL\n"
                "3. LIKE 'keyword%' 可以用索引，'%keyword' 不行\n"
                "4. 不需要去重时总是用UNION ALL\n"
                "5. GROUP BY列建索引可提升性能\n"
                "6. 定期清理无用索引"
            ),
            sql_examples=[
                "-- 避免: SELECT * FROM orders WHERE status='A' OR status='B'",
                "-- 推荐: SELECT order_id, customer_id FROM orders WHERE status IN ('A','B')",
                "",
                "-- 避免: SELECT COUNT(*) FROM t1 WHERE EXISTS条件判断",
                "-- 推荐: SELECT 'A' FROM SYSDUAL WHERE EXISTS(SELECT 1 FROM t1 WHERE condition)",
            ],
        ))

        # ====================================================================
        # 5. 附录4 - 执行计划操作符
        # ====================================================================

        self._add(DocSnippet(
            feature_id="plan_operators",
            feature_name="执行计划操作符参考",
            doc_source="附录4 执行计划操作符",
            doc_url=self.URL_APPENDIX4,
            doc_content=(
                "达梦执行计划由各种操作符组成，以下是常用操作符说明:\n\n"
                "【扫描类操作符】\n"
                "CSCN2: 聚集索引扫描(全表扫描)，扫描整张表\n"
                "  - btr_scan=1: B树扫描; btr_scan=0: 簇游标扫描\n"
                "  - need_slct(1): 过滤条件已下推到此节点\n\n"
                "SSCN: 索引全扫描，扫描整个索引\n"
                "SSEK2: 索引等值查找，通过索引定位特定值\n"
                "  - scan_type: ASC(升序)/DESC(降序)\n"
                "  - scan_range: 扫描范围\n\n"
                "CSEK2: 聚集索引数据定位(范围查找)\n"
                "BLKUP2: 定位查找(回表)，通过二级索引ROWID回聚集索引取数据\n"
                "  - use_clu_addr: 是否优化聚集索引定位\n\n"
                "BMSEK: 位图索引的范围查找\n"
                "DSCN: 动态视图表扫描\n"
                "ESCN: 外部表扫描\n\n"
                "【连接类操作符】\n"
                "HASH2 INNER JOIN: 哈希内连接(等值连接首选)\n"
                "  - KEY: 等值连接条件\n"
                "  - KEY_NULL_EQU: NULL值比较策略\n"
                "  - UNIQUE_FLAG: 数据唯一性策略(LKEY_UNIQUE/RKEY_UNIQUE等)\n\n"
                "NEST LOOP INDEX JOIN2 / NEST LOOP INNER JOIN2: 嵌套循环连接\n"
                "MERGE INNER JOIN3: 归并连接(连接列需为索引列)\n"
                "HASH LEFT JOIN2: 哈希左外连接\n"
                "HASH RIGHT JOIN2: 哈希右外连接\n"
                "HASH FULL JOIN2: 哈希全外连接\n"
                "HASH LEFT SEMI JOIN2: 哈希左半连接(子查询IN)\n"
                "  - (ANTI): 是否为反连接(NOT IN)\n"
                "HASH RIGHT SEMI JOIN2: 哈希右半连接\n"
                "INDEX JOIN SEMI JOIN2: 索引半连接\n"
                "INDEX JOIN LEFT JOIN2: 索引左连接\n\n"
                "【过滤/投影/排序类操作符】\n"
                "SLCT2: 选择过滤，按条件过滤数据\n"
                "  - slct_pushdown(1): 过滤条件已下推\n\n"
                "PRJT2: 投影，选择输出列\n"
                "  - exp_num: 输出表达式数\n"
                "  - is_atom: 是否原子表达式\n\n"
                "SORT3: 排序\n"
                "  - key_num: 排序键数\n"
                "  - is_distinct: 是否去重排序\n"
                "  - top_flag: 是否有TOP子句\n\n"
                "DISTINCT: 去重\n\n"
                "【聚合类操作符】\n"
                "HAGR2: HASH分组，计算集函数(需缓存中间结果)\n"
                "  - grp_num: 分组项个数\n"
                "  - sfun_num: 集函数个数\n"
                "  - distinct_flag: 是否去重\n\n"
                "AAGR2: 简单聚集(无分组时直接计算集函数)\n"
                "FAGR2: 快速聚集(COUNT(*)或索引MAX/MIN)\n"
                "SAGR2: 排序分组(利用索引，无需缓存)\n\n"
                "【其他常用操作符】\n"
                "NSET2: 结果集输出(顶层节点)\n"
                "ACTRL: 自适应计划控制(控制备用计划转换)\n"
                "AFUN: 分析函数计算(窗口函数)\n"
                "  - partition_num: 分区项个数\n"
                "  - order_num: 排序项个数\n\n"
                "CONST VALUE LIST: 常量列表(IN列表展开)\n"
                "INSERT/DELETE/UPDATE: 数据修改操作\n"
                "EXCEPT/INTERSECT/UNION: 集合运算\n"
                "HIERARCHICAL QUERY: 层次查询(CONNECT BY)\n\n"
                "【执行计划格式说明】\n"
                "每个节点格式: #操作符名: [代价, 行数, 字节数]\n"
                "  - 代价: 操作符估算代价(越小越好)\n"
                "  - 行数: 估算处理的记录行数\n"
                "  - 字节数: 每行记录的字节数\n\n"
                "Predicate Information: 谓词信息\n"
                "  - access: 连接条件使用的谓词\n"
                "  - filter: 过滤条件使用的谓词"
            ),
            tips=(
                "1. 关注COST和ROW_NUMS高的节点 - 它们是性能瓶颈\n"
                "2. CSCN2(聚集索引扫描) = 全表扫描，大表需优化\n"
                "3. BLKUP2(回表)可通过覆盖索引避免\n"
                "4. NEST LOOP大驱动表时性能差，考虑改HASH JOIN\n"
                "5. HAGR(哈希分组)可通过GROUP BY列建索引改为SAGR(排序分组)\n"
                "6. SORT节点可通过索引消除\n"
                "7. ACTRL表示自适应计划，有备用计划可切换"
            ),
            sql_examples=[
                "-- 查看执行计划",
                "EXPLAIN SELECT * FROM 表名 WHERE 条件;",
                "-- 表格格式(含COST/CPU_COST/IO_COST)",
                "EXPLAIN FOR SELECT * FROM 表名 WHERE 条件;",
                "-- 查看所有操作符名称",
                "SELECT NAME FROM V$SQL_NODE_NAME;",
            ],
        ))

    def _add(self, snippet: DocSnippet):
        self._snippets[snippet.feature_id] = snippet

    def get(self, feature_id: str) -> DocSnippet:
        """获取某个功能的文档知识"""
        return self._snippets.get(feature_id)

    def get_all(self) -> list[DocSnippet]:
        """获取所有文档知识"""
        return list(self._snippets.values())

    def get_all_ids(self) -> list[str]:
        """获取所有功能ID"""
        return list(self._snippets.keys())
