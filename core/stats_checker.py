"""
统计信息检查模块

检查表和索引的统计信息是否过期或缺失：
- 表是否收集过统计信息(LAST_ANALYZED)
- 统计信息是否过期(数据变化大但未重新收集)
- 列的NDV(distinct值数量)是否合理
- 索引统计信息是否完整
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class StatsIssue:
    """统计信息问题"""
    level: str           # INFO / WARNING / CRITICAL
    table_name: str
    issue_type: str      # 问题类型
    description: str
    suggestion: str


@dataclass
class StatsCheckResult:
    """统计信息检查结果"""
    issues: list[StatsIssue] = field(default_factory=list)
    summary: str = ""
    tables_checked: int = 0
    tables_ok: int = 0
    tables_stale: int = 0
    tables_missing: int = 0


class StatsChecker:
    """统计信息检查器"""

    # 统计信息过期阈值(天数)
    STALE_DAYS_THRESHOLD = 7
    # 数据量变化比例阈值(20%)
    DATA_CHANGE_THRESHOLD = 0.20
    # 小表行数阈值(不需要统计信息)
    SMALL_TABLE_THRESHOLD = 100

    def check(
        self,
        table_stats: dict,
        table_name: str = "",
    ) -> StatsCheckResult:
        """
        检查表统计信息

        Args:
            table_stats: 通过DMConnector.get_table_stats()获取的统计信息
            table_name: 表名(可选，默认从stats中获取)

        Returns:
            StatsCheckResult 检查结果
        """
        result = StatsCheckResult()
        result.tables_checked = 1

        info = table_stats.get("table_info", {})
        columns = table_stats.get("columns", [])
        indexes = table_stats.get("indexes", [])

        if not info.get("exists", False):
            result.issues.append(StatsIssue(
                level="WARNING",
                table_name=table_name or info.get("table_name", ""),
                issue_type="表不存在",
                description=f"表 {table_name} 不存在或无法访问",
                suggestion="检查表名是否正确，以及当前用户是否有访问权限",
            ))
            result.summary = "表不存在"
            return result

        table_name = info.get("table_name", table_name)
        num_rows = info.get("num_rows", 0) or 0
        last_analyzed = info.get("last_analyzed")

        # 小表跳过
        if num_rows > 0 and num_rows < self.SMALL_TABLE_THRESHOLD:
            result.tables_ok += 1
            result.summary = f"表 {table_name} 行数较少({num_rows}行)，统计信息不影响性能"
            return result

        # 1. 检查是否收集过统计信息
        if not last_analyzed:
            result.tables_missing += 1
            result.issues.append(StatsIssue(
                level="CRITICAL",
                table_name=table_name,
                issue_type="缺少统计信息",
                description=f"表 {table_name} 从未收集统计信息(LAST_ANALYZED为空)，"
                            f"优化器无法做出准确的执行计划决策",
                suggestion=f"执行: DBMS_STATS.GATHER_TABLE_STATS("
                           f"'{table_name}'); 或使用 ANALYZE TABLE {table_name} COMPUTE STATISTICS;",
            ))
        else:
            # 2. 检查统计信息是否过期
            stale = self._check_stale(last_analyzed)
            if stale:
                result.tables_stale += 1
                result.issues.append(StatsIssue(
                    level="WARNING",
                    table_name=table_name,
                    issue_type="统计信息过期",
                    description=f"表 {table_name} 的统计信息最后收集时间为 {last_analyzed}，"
                                f"已超过 {self.STALE_DAYS_THRESHOLD} 天，可能已过期",
                    suggestion=f"建议重新收集: DBMS_STATS.GATHER_TABLE_STATS('{table_name}');",
                ))
            else:
                result.tables_ok += 1

        # 3. 检查行数为0但有数据
        if num_rows == 0:
            result.issues.append(StatsIssue(
                level="WARNING",
                table_name=table_name,
                issue_type="行数为0",
                description=f"表 {table_name} 统计信息中NUM_ROWS=0，"
                            f"但表可能实际有数据(统计信息未更新)",
                suggestion="建议重新收集统计信息，或检查表是否确实为空",
            ))

        # 4. 检查列的统计信息
        self._check_column_stats(table_name, columns, result)

        # 5. 检查索引统计信息
        self._check_index_stats(table_name, indexes, result)

        # 生成总结
        result.summary = self._generate_summary(result, table_name)
        return result

    def _check_stale(self, last_analyzed_str: str) -> bool:
        """检查统计信息是否过期"""
        try:
            # 尝试多种日期格式
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(last_analyzed_str.strip(), fmt)
                    threshold = datetime.now() - timedelta(days=self.STALE_DAYS_THRESHOLD)
                    return dt < threshold
                except ValueError:
                    continue
        except Exception:
            pass
        return False

    def _check_column_stats(self, table_name: str, columns: list, result: StatsCheckResult):
        """检查列级别统计信息"""
        for col in columns:
            ndv = col.get("num_distinct")
            if ndv is None:
                result.issues.append(StatsIssue(
                    level="INFO",
                    table_name=table_name,
                    issue_type="列缺少NDV统计",
                    description=f"列 {table_name}.{col['name']} 缺少DISTINCT值统计(NDV)",
                    suggestion="收集表统计信息时会自动收集列级统计",
                ))
            elif ndv == 0 and col.get("type", "").upper() not in ("BLOB", "CLOB", "TEXT"):
                result.issues.append(StatsIssue(
                    level="INFO",
                    table_name=table_name,
                    issue_type="列NDV为0",
                    description=f"列 {table_name}.{col['name']} 的NDV=0，统计信息可能不完整",
                    suggestion="建议重新收集统计信息",
                ))

    def _check_index_stats(self, table_name: str, indexes: list, result: StatsCheckResult):
        """检查索引级别统计信息"""
        for idx in indexes:
            if not idx.get("last_analyzed"):
                result.issues.append(StatsIssue(
                    level="WARNING",
                    table_name=table_name,
                    issue_type="索引缺少统计信息",
                    description=f"索引 {table_name}.{idx['name']} 缺少统计信息(LAST_ANALYZED为空)",
                    suggestion=f"收集索引统计: DBMS_STATS.GATHER_INDEX_STATS("
                               f"'{table_name}', '{idx['name']}');",
                ))
            if idx.get("num_rows") is None:
                result.issues.append(StatsIssue(
                    level="INFO",
                    table_name=table_name,
                    issue_type="索引行数缺失",
                    description=f"索引 {table_name}.{idx['name']} 缺少NUM_ROWS统计",
                    suggestion="收集表统计信息时会自动收集索引统计",
                ))

    def _generate_summary(self, result: StatsCheckResult, table_name: str) -> str:
        """生成总结"""
        critical = sum(1 for i in result.issues if i.level == "CRITICAL")
        warning = sum(1 for i in result.issues if i.level == "WARNING")
        info = sum(1 for i in result.issues if i.level == "INFO")

        status = "正常" if not critical and not warning else "需关注"
        return (
            f"表 {table_name} 统计信息状态: {status}\n"
            f"严重问题: {critical} | 警告: {warning} | 提示: {info}"
        )
