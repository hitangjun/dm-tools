"""
执行计划分析模块

解析DM数据库执行计划，识别性能问题：
- 全表扫描 (TABLE SCAN)
- 高代价排序操作
- 嵌套循环连接效率
- 笛卡尔积
- 不合适的连接方式
- 估算行数偏差
"""
import re
from dataclasses import dataclass, field
from enum import Enum


class RiskLevel(Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class PlanIssue:
    """执行计划问题项"""
    level: RiskLevel
    category: str           # 问题类别
    operation: str          # 相关操作节点
    description: str        # 问题描述
    suggestion: str         # 优化建议
    location: str = ""      # 在执行计划中的位置
    sql_fragment: str = ""  # 导致问题的SQL片段(过滤条件/连接条件等)


@dataclass
class PlanAnalysisResult:
    """执行计划分析结果"""
    plan_text: str                          # 原始执行计划
    issues: list[PlanIssue] = field(default_factory=list)
    summary: str = ""                       # 总体评估
    cost_score: int = 0                     # 代价评分(0-100, 越高越好)
    table_scans: int = 0                    # 全表扫描次数
    join_count: int = 0                     # 连接操作次数
    sort_count: int = 0                     # 排序操作次数


class PlanAnalyzer:
    """执行计划分析器"""

    # DM执行计划中的操作关键字
    FULL_SCAN_PATTERNS = [
        r"TABLE\s+SCAN\s+FULL",    # 全表扫描
        r"FULL\s+TABLE\s+SCAN",
        r"SSCN",                   # DM执行计划中的全表扫描标识
        r"CSCN",                   # DM执行计划中的聚簇索引扫描(等同全表扫描)
        r"TABLE\s+ACCESS\s+FULL",
    ]

    INDEX_SCAN_PATTERNS = [
        r"INDEX\s+SCAN",
        r"INDEX\s+RANGE\s+SCAN",
        r"INDEX\s+UNIQUE\s+SCAN",
        r"BLKFUP",                 # DM索引扫描
        r"SSEK",
    ]

    JOIN_PATTERNS = [
        (r"HASH\s+JOIN|HJIN", "HASH JOIN"),
        (r"NESTED\s+LOOP|NLJN", "NESTED LOOP JOIN"),
        (r"MERGE\s+JOIN|MJIN", "MERGE JOIN"),
        (r"HJOIN", "HASH JOIN"),
        (r"NLJOIN", "NESTED LOOP JOIN"),
        (r"MJOIN", "MERGE JOIN"),
    ]

    SORT_PATTERNS = [
        r"SORT",
        r"ORDER\s+BY",
        r"GROUP\s+BY",
        r"DISTINCT",
    ]

    CARTESIAN_PATTERN = r"CARTESIAN|CROSS\s+JOIN"

    # 高代价操作
    HIGH_COST_OPS = [
        ("HASH JOIN|HJIN", "哈希连接，大表场景下内存消耗大"),
        ("SORT", "排序操作，内存不足时会写临时表空间"),
        ("HASH GROUP|HGRP", "哈希聚合，内存消耗较大"),
        ("WINDOW SORT", "窗口函数排序"),
    ]

    def analyze(self, plan_text: str, sql: str = "") -> PlanAnalysisResult:
        """
        分析执行计划，识别性能问题

        Args:
            plan_text: DM执行计划文本
            sql: 原始 SQL 语句文本

        Returns:
            PlanAnalysisResult 分析结果
        """
        result = PlanAnalysisResult(plan_text=plan_text)
        lines = plan_text.split("\n")

        for i, line in enumerate(lines):
            line_upper = line.upper().strip()
            # 提取该行中可能的 SQL 片段 (过滤条件/连接条件/排序字段等)
            sql_frag = self._extract_sql_fragment(line, sql)
            self._check_full_scan(line_upper, line, i, result, sql_frag)
            self._check_join(line_upper, line, i, result, sql_frag)
            self._check_sort(line_upper, line, i, result, sql_frag)
            self._check_cartesian(line_upper, line, i, result, sql_frag)
            self._check_high_cost(line_upper, line, i, result, sql_frag)

        # 计算代价评分
        result.cost_score = self._calculate_score(result)
        result.summary = self._generate_summary(result)
        return result

    @staticmethod
    def _extract_sql_fragment(line: str, sql: str = "") -> str:
        """
        从执行计划树节点行中提取与原始SQL对应的片段
        (过滤条件、连接条件、扫描范围等)
        """
        fragments = []
        # 过滤条件(WHERE)
        m = re.search(r'过滤条件\(WHERE\):\s*(.+?)(?:,\s*连接|,\s*优化|,\s*扫描|\]|$)', line)
        if m:
            fragments.append(f"WHERE条件: {m.group(1).strip().rstrip(']')}")
        else:
            m = re.search(r'过滤条件:\s*(.+?)(?:,\s*连接|,\s*优化|,\s*扫描|\]|$)', line)
            if m:
                fragments.append(f"WHERE条件: {m.group(1).strip().rstrip(']')}")
        # 连接条件(ON)
        m = re.search(r'连接条件\(ON\):\s*(.+?)(?:,\s*过滤|,\s*优化|,\s*扫描|\]|$)', line)
        if m:
            fragments.append(f"JOIN ON: {m.group(1).strip().rstrip(']')}")
        else:
            m = re.search(r'连接条件:\s*(.+?)(?:,\s*过滤|,\s*优化|,\s*扫描|\]|$)', line)
            if m:
                fragments.append(f"JOIN ON: {m.group(1).strip().rstrip(']')}")
        # 扫描范围
        m = re.search(r'扫描范围:\s*(.+?)(?:,|\]|$)', line)
        if m:
            fragments.append(f"扫描范围: {m.group(1).strip().rstrip(']')}")

        # 如果是排序或分组聚合操作，且有传入SQL，尝试从原始SQL中提取对应的片段
        if sql and any(kw in line.upper() for kw in ("SORT", "HGRP", "AAGR", "FAGR")):
            sql_clean = " ".join(sql.split())
            # 提取 ORDER BY 子句
            order_match = re.search(r'\bORDER\s+BY\s+(.+?)(?:\bGROUP\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|\bJOIN\b|$)', sql_clean, re.IGNORECASE)
            if order_match:
                fragments.append(f"排序子句: ORDER BY {order_match.group(1).strip().rstrip(';')}")
            
            # 提取 GROUP BY 子句
            group_match = re.search(r'\bGROUP\s+BY\s+(.+?)(?:\bORDER\b|\bHAVING\b|\bLIMIT\b|\bUNION\b|\bJOIN\b|$)', sql_clean, re.IGNORECASE)
            if group_match:
                fragments.append(f"分组子句: GROUP BY {group_match.group(1).strip().rstrip(';')}")
            
            # 提取 DISTINCT
            if "DISTINCT" in sql_clean.upper() and not order_match and not group_match:
                fragments.append("去重子句: DISTINCT")

        return "; ".join(fragments) if fragments else ""

    # ------------------------------------------------------------------
    # 检查方法
    # ------------------------------------------------------------------

    def _check_full_scan(self, line_upper, line, line_no, result, sql_frag=""):
        """检查全表扫描"""
        for pattern in self.FULL_SCAN_PATTERNS:
            if re.search(pattern, line_upper):
                result.table_scans += 1
                # 提取表名 (支持 ON/OF/TABLE 以及格式化后的 表:)
                table_match = re.search(r'(?:ON|OF|TABLE|表:)\s*(\w+)', line_upper)
                table_name = table_match.group(1) if table_match else "未知表"
                desc = f"检测到对表 {table_name} 的全表扫描，大数据量表上会导致严重性能问题"
                if sql_frag:
                    desc += f"。对应SQL子句: {sql_frag}"
                result.issues.append(PlanIssue(
                     level=RiskLevel.CRITICAL,
                     category="全表扫描",
                     operation=line.strip(),
                     description=desc,
                     suggestion=f"建议在 {table_name} 的过滤条件列上创建合适的索引，"
                                f"或检查WHERE条件是否可以使用已有索引",
                     location=f"第{line_no + 1}行",
                     sql_fragment=sql_frag,
                ))
                break

    def _check_join(self, line_upper, line, line_no, result, sql_frag=""):
        """检查连接操作"""
        for pattern, join_type in self.JOIN_PATTERNS:
            if re.search(pattern, line_upper):
                result.join_count += 1
                # 嵌套循环在大表场景下可能有问题
                if "NESTED LOOP" in join_type or "NLJOIN" in pattern:
                    desc = ("检测到嵌套循环连接(NESTED LOOP)，"
                            "如果驱动表结果集较大，会导致内表被多次扫描")
                    if sql_frag:
                        desc += f"。对应SQL子句: {sql_frag}"
                    result.issues.append(PlanIssue(
                        level=RiskLevel.WARNING,
                        category="嵌套循环连接",
                        operation=line.strip(),
                        description=desc,
                        suggestion="确认驱动表返回少量数据；"
                                   "大表连接建议使用HASH JOIN；"
                                   "确保被驱动表的连接列上有索引",
                        location=f"第{line_no + 1}行",
                        sql_fragment=sql_frag,
                    ))
                break

    def _check_sort(self, line_upper, line, line_no, result, sql_frag=""):
        """检查排序操作"""
        for pattern in self.SORT_PATTERNS:
            if re.search(pattern, line_upper):
                result.sort_count += 1
                if "SORT" in pattern or "ORDER BY" in pattern:
                    desc = ("检测到排序操作，大数据量排序会消耗大量内存，"
                            "内存不足时会写临时表空间导致性能下降")
                    if sql_frag:
                        desc += f"。对应SQL子句: {sql_frag}"
                    result.issues.append(PlanIssue(
                        level=RiskLevel.INFO,
                        category="排序操作",
                        operation=line.strip(),
                        description=desc,
                        suggestion="检查是否可以通过索引消除排序；"
                                   "确认排序字段是否必要；"
                                   "考虑使用LIMIT/TOP减少排序数据量",
                        location=f"第{line_no + 1}行",
                        sql_fragment=sql_frag,
                    ))
                break

    def _check_cartesian(self, line_upper, line, line_no, result, sql_frag=""):
        """检查笛卡尔积"""
        if re.search(self.CARTESIAN_PATTERN, line_upper):
            desc = "检测到笛卡尔积操作，会产生大量中间结果集，严重影响性能"
            if sql_frag:
                desc += f"。对应SQL子句: {sql_frag}"
            result.issues.append(PlanIssue(
                level=RiskLevel.CRITICAL,
                category="笛卡尔积",
                operation=line.strip(),
                description=desc,
                suggestion="检查SQL是否遗漏了表连接条件(JOIN ON)；"
                           "确认所有参与连接的表都有正确的关联条件",
                location=f"第{line_no + 1}行",
                sql_fragment=sql_frag,
            ))

    def _check_high_cost(self, line_upper, line, line_no, result, sql_frag=""):
        """检查高代价操作"""
        for op_name, desc in self.HIGH_COST_OPS:
            if op_name.upper() in line_upper:
                full_desc = f"检测到高代价操作: {desc}"
                if sql_frag:
                    full_desc += f"。对应SQL子句: {sql_frag}"
                result.issues.append(PlanIssue(
                    level=RiskLevel.INFO,
                    category="高代价操作",
                    operation=line.strip(),
                    description=full_desc,
                    suggestion="评估该操作是否必要，是否有更高效的替代方案",
                    location=f"第{line_no + 1}行",
                    sql_fragment=sql_frag,
                ))
                break

    # ------------------------------------------------------------------
    # 评分和总结
    # ------------------------------------------------------------------

    def _calculate_score(self, result: PlanAnalysisResult) -> int:
        """
        计算执行计划的代价评分(0-100, 越高越好)

        扣分规则:
        - 每个CRITICAL问题扣15分
        - 每个WARNING问题扣8分
        - 每个INFO问题扣3分
        - 全表扫描额外扣5分/次
        """
        score = 100
        for issue in result.issues:
            if issue.level == RiskLevel.CRITICAL:
                score -= 15
            elif issue.level == RiskLevel.WARNING:
                score -= 8
            elif issue.level == RiskLevel.INFO:
                score -= 3
        # 全表扫描额外惩罚
        score -= result.table_scans * 5
        return max(0, min(100, score))

    def _generate_summary(self, result: PlanAnalysisResult) -> str:
        """生成总体评估"""
        if result.cost_score >= 80:
            rating = "良好"
        elif result.cost_score >= 60:
            rating = "一般"
        elif result.cost_score >= 40:
            rating = "较差"
        else:
            rating = "很差"

        critical = sum(1 for i in result.issues if i.level == RiskLevel.CRITICAL)
        warning = sum(1 for i in result.issues if i.level == RiskLevel.WARNING)
        info = sum(1 for i in result.issues if i.level == RiskLevel.INFO)

        return (
            f"执行计划评估: {rating} (评分: {result.cost_score}/100)\n"
            f"全表扫描: {result.table_scans}次 | "
            f"连接操作: {result.join_count}次 | "
            f"排序操作: {result.sort_count}次\n"
            f"问题统计: 严重{critical}个 | 警告{warning}个 | 提示{info}个"
        )
