"""
索引建议模块

分析SQL语句，识别潜在的索引优化机会：
- WHERE条件中的等值/范围查询列
- JOIN连接列
- ORDER BY / GROUP BY列
- 检查是否已有覆盖索引
- 给出复合索引建议
"""
import re
from dataclasses import dataclass, field
from typing import Optional

try:
    import sqlparse
    from sqlparse.sql import IdentifierList, Identifier, Where, Comparison
    from sqlparse.tokens import Keyword, DML, Whitespace, Newline
except ImportError:
    sqlparse = None


@dataclass
class IndexSuggestion:
    """索引建议项"""
    table_name: str
    columns: list[str]                  # 建议索引的列
    suggestion_type: str                # 建议类型: WHERE/JOIN/ORDER_BY/COVERING
    reason: str                         # 建议原因
    ddl: str                            # 建议的DDL语句
    existing_index_conflict: str = ""   # 与已有索引的冲突说明
    priority: int = 0                   # 优先级(1-5, 5最高)


@dataclass
class IndexAnalysisResult:
    """索引分析结果"""
    suggestions: list[IndexSuggestion] = field(default_factory=list)
    existing_indexes: list[dict] = field(default_factory=list)
    summary: str = ""


class IndexAdvisor:
    """索引建议器"""

    # WHERE条件中的操作符
    EQUALITY_OPS = {"=", "IN", "IS", "LIKE"}
    RANGE_OPS = {">", "<", ">=", "<=", "BETWEEN"}

    def analyze(
        self,
        sql: str,
        table_stats: Optional[dict] = None,
    ) -> IndexAnalysisResult:
        """
        分析SQL，给出索引建议

        Args:
            sql: SQL语句
            table_stats: 表统计信息(含已有索引)，格式为 {table_name: stats_dict}

        Returns:
            IndexAnalysisResult 索引分析结果
        """
        if sqlparse is None:
            return IndexAnalysisResult(summary="需要安装sqlparse: pip install sqlparse")

        result = IndexAnalysisResult()
        if table_stats:
            for table_name, stats in table_stats.items():
                result.existing_indexes.extend(stats.get("indexes", []))

        # 解析SQL
        parsed = sqlparse.parse(sql)[0]

        # 提取表名
        tables = self._extract_tables(parsed)

        # 提取WHERE条件列
        where_columns = self._extract_where_columns(parsed)

        # 提取JOIN连接列
        join_columns = self._extract_join_columns(parsed)

        # 提取ORDER BY列
        order_by_columns = self._extract_order_by_columns(sql)

        # 提取GROUP BY列
        group_by_columns = self._extract_group_by_columns(sql)

        # 生成索引建议
        for table_name, alias in tables:
            table_cols_where = [c for c in where_columns if c[0] in (table_name, alias, "")]
            table_cols_join = [c for c in join_columns if c[0] in (table_name, alias, "")]
            table_cols_order = [c for c in order_by_columns if c[0] in (table_name, alias, "")]
            table_cols_group = [c for c in group_by_columns if c[0] in (table_name, alias, "")]

            stats = table_stats.get(table_name) if table_stats else None

            # WHERE条件索引建议
            if table_cols_where:
                suggestion = self._make_where_suggestion(
                    table_name, table_cols_where, stats
                )
                if suggestion:
                    result.suggestions.append(suggestion)

            # JOIN列索引建议
            if table_cols_join:
                suggestion = self._make_join_suggestion(
                    table_name, table_cols_join, stats
                )
                if suggestion:
                    result.suggestions.append(suggestion)

            # ORDER BY索引建议
            if table_cols_order:
                suggestion = self._make_order_suggestion(
                    table_name, table_cols_order, stats
                )
                if suggestion:
                    result.suggestions.append(suggestion)

            # GROUP BY索引建议
            if table_cols_group:
                suggestion = self._make_group_suggestion(
                    table_name, table_cols_group, stats
                )
                if suggestion:
                    result.suggestions.append(suggestion)

        # 去重和排序
        result.suggestions = self._deduplicate(result.suggestions)
        result.suggestions.sort(key=lambda x: x.priority, reverse=True)
        result.summary = self._generate_summary(result, tables)
        return result

    # ------------------------------------------------------------------
    # SQL解析
    # ------------------------------------------------------------------

    def _extract_tables(self, parsed) -> list[tuple[str, str]]:
        """提取SQL中的表名和别名，返回[(table_name, alias)]"""
        tables = []
        from_seen = False

        for token in parsed.tokens:
            if token.is_keyword and token.value.upper() in ("FROM", "JOIN", "INTO", "UPDATE"):
                from_seen = True
                continue
            if token.is_keyword and token.value.upper() in ("WHERE", "GROUP", "ORDER", "SET", "HAVING", "LIMIT"):
                from_seen = False
                continue
            if from_seen:
                if isinstance(token, IdentifierList):
                    for identifier in token.get_identifiers():
                        name, alias = self._parse_identifier(identifier)
                        if name:
                            tables.append((name, alias or name))
                elif isinstance(token, Identifier):
                    name, alias = self._parse_identifier(token)
                    if name:
                        tables.append((name, alias or name))
                elif token.ttype is Whitespace or token.ttype is Newline:
                    continue
        return tables

    def _parse_identifier(self, identifier) -> tuple[str, str]:
        """解析标识符，返回(表名, 别名)"""
        name = identifier.get_real_name()
        alias = identifier.get_alias()
        return name, alias

    def _extract_where_columns(self, parsed) -> list[tuple[str, str, str]]:
        """提取WHERE条件中的列，返回[(table_or_alias, column_name, operator)]"""
        columns = []
        for token in parsed.tokens:
            if isinstance(token, Where):
                where_text = str(token)
                columns.extend(self._parse_conditions(where_text))
        return columns

    def _extract_join_columns(self, parsed) -> list[tuple[str, str, str]]:
        """提取JOIN ON条件中的列"""
        columns = []
        sql_text = str(parsed)
        # 匹配 ON table1.col1 = table2.col2
        join_pattern = re.compile(
            r'ON\s+(\w+)\.(\w+)\s*=\s*(\w+)\.(\w+)',
            re.IGNORECASE,
        )
        for m in join_pattern.finditer(sql_text):
            columns.append((m.group(1), m.group(2), "JOIN"))
            columns.append((m.group(3), m.group(4), "JOIN"))
        return columns

    def _extract_order_by_columns(self, sql: str) -> list[tuple[str, str, str]]:
        """提取ORDER BY中的列"""
        columns = []
        match = re.search(r'ORDER\s+BY\s+(.+?)(?:LIMIT|TOP|$)', sql, re.IGNORECASE)
        if match:
            order_text = match.group(1).strip()
            for col_part in order_text.split(","):
                col_part = col_part.strip()
                # 去掉 ASC/DESC
                col_part = re.sub(r'\s+(ASC|DESC)\s*$', '', col_part, flags=re.IGNORECASE)
                # 匹配 table.column 或 column
                col_match = re.match(r'(\w+)\.(\w+)', col_part)
                if col_match:
                    columns.append((col_match.group(1), col_match.group(2), "ORDER BY"))
                else:
                    col_match = re.match(r'(\w+)', col_part)
                    if col_match:
                        columns.append(("", col_match.group(1), "ORDER BY"))
        return columns

    def _extract_group_by_columns(self, sql: str) -> list[tuple[str, str, str]]:
        """提取GROUP BY中的列"""
        columns = []
        match = re.search(r'GROUP\s+BY\s+(.+?)(?:HAVING|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if match:
            group_text = match.group(1).strip()
            for col_part in group_text.split(","):
                col_part = col_part.strip()
                col_match = re.match(r'(\w+)\.(\w+)', col_part)
                if col_match:
                    columns.append((col_match.group(1), col_match.group(2), "GROUP BY"))
                else:
                    col_match = re.match(r'(\w+)', col_part)
                    if col_match:
                        columns.append(("", col_match.group(1), "GROUP BY"))
        return columns

    def _parse_conditions(self, where_text: str) -> list[tuple[str, str, str]]:
        """解析WHERE条件文本，提取列和操作符"""
        columns = []
        # 匹配 table.column OP value 或 column OP value
        # 等值条件
        eq_pattern = re.compile(
            r'(?:(\w+)\.)?(\w+)\s*(=|IN|IS|LIKE)\s',
            re.IGNORECASE,
        )
        for m in eq_pattern.finditer(where_text):
            table_alias = m.group(1) or ""
            col_name = m.group(2)
            op = m.group(3).upper()
            # 过滤掉关键字
            if col_name.upper() not in ("AND", "OR", "NOT", "NULL", "SELECT"):
                columns.append((table_alias, col_name, op))

        # 范围条件
        range_pattern = re.compile(
            r'(?:(\w+)\.)?(\w+)\s*(>=|<=|>|<|BETWEEN)',
            re.IGNORECASE,
        )
        for m in range_pattern.finditer(where_text):
            table_alias = m.group(1) or ""
            col_name = m.group(2)
            op = m.group(3).upper()
            if col_name.upper() not in ("AND", "OR", "NOT", "SELECT"):
                columns.append((table_alias, col_name, op))

        return columns

    # ------------------------------------------------------------------
    # 建议生成
    # ------------------------------------------------------------------

    def _make_where_suggestion(
        self, table_name: str, columns: list, stats: Optional[dict]
    ) -> Optional[IndexSuggestion]:
        """为WHERE条件生成索引建议"""
        col_names = [c[1] for c in columns]
        # 去重保持顺序
        seen = set()
        unique_cols = []
        for c in col_names:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)

        if not unique_cols:
            return None

        # 检查是否已有索引覆盖
        conflict = self._check_existing_index(unique_cols, stats)

        # 优先级：等值条件 > 范围条件
        has_equality = any(c[2] in self.EQUALITY_OPS for c in columns)
        priority = 4 if has_equality else 3

        col_list = ", ".join(unique_cols)
        return IndexSuggestion(
            table_name=table_name,
            columns=unique_cols,
            suggestion_type="WHERE条件",
            reason=f"WHERE条件中使用了列: {col_list}，"
                   f"当前缺少匹配索引可能导致全表扫描",
            ddl=f'CREATE INDEX IDX_{table_name}_{_join_col_names(unique_cols)} '
                f'ON {table_name} ({col_list});',
            existing_index_conflict=conflict,
            priority=priority,
        )

    def _make_join_suggestion(
        self, table_name: str, columns: list, stats: Optional[dict]
    ) -> Optional[IndexSuggestion]:
        """为JOIN连接列生成索引建议"""
        col_names = [c[1] for c in columns]
        seen = set()
        unique_cols = []
        for c in col_names:
            if c not in seen:
                seen.add(c)
                unique_cols.append(c)

        if not unique_cols:
            return None

        conflict = self._check_existing_index(unique_cols, stats)
        col_list = ", ".join(unique_cols)
        return IndexSuggestion(
            table_name=table_name,
            columns=unique_cols,
            suggestion_type="JOIN连接",
            reason=f"表 {table_name} 在JOIN连接条件中使用了列: {col_list}，"
                   f"缺少索引会导致连接效率低下",
            ddl=f'CREATE INDEX IDX_{table_name}_{_join_col_names(unique_cols)} '
                f'ON {table_name} ({col_list});',
            existing_index_conflict=conflict,
            priority=5,
        )

    def _make_order_suggestion(
        self, table_name: str, columns: list, stats: Optional[dict]
    ) -> Optional[IndexSuggestion]:
        """为ORDER BY列生成索引建议"""
        col_names = [c[1] for c in columns]
        if not col_names:
            return None
        conflict = self._check_existing_index(col_names, stats)
        col_list = ", ".join(col_names)
        return IndexSuggestion(
            table_name=table_name,
            columns=col_names,
            suggestion_type="ORDER BY排序",
            reason=f"ORDER BY使用了列: {col_list}，"
                   f"创建索引可以避免排序操作",
            ddl=f'CREATE INDEX IDX_{table_name}_{_join_col_names(col_names)} '
                f'ON {table_name} ({col_list});',
            existing_index_conflict=conflict,
            priority=2,
        )

    def _make_group_suggestion(
        self, table_name: str, columns: list, stats: Optional[dict]
    ) -> Optional[IndexSuggestion]:
        """为GROUP BY列生成索引建议"""
        col_names = [c[1] for c in columns]
        if not col_names:
            return None
        conflict = self._check_existing_index(col_names, stats)
        col_list = ", ".join(col_names)
        return IndexSuggestion(
            table_name=table_name,
            columns=col_names,
            suggestion_type="GROUP BY分组",
            reason=f"GROUP BY使用了列: {col_list}，"
                   f"创建索引可以提升分组聚合效率",
            ddl=f'CREATE INDEX IDX_{table_name}_{_join_col_names(col_names)} '
                f'ON {table_name} ({col_list});',
            existing_index_conflict=conflict,
            priority=2,
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _check_existing_index(self, columns: list[str], stats: Optional[dict]) -> str:
        """检查列是否已被已有索引覆盖"""
        if not stats:
            return ""
        existing = stats.get("indexes", [])
        for idx in existing:
            idx_cols = idx.get("columns", [])
            if idx_cols and idx_cols[0] == columns[0]:
                if idx_cols == columns:
                    return f"已有索引 {idx['name']} 完全覆盖这些列，无需重复创建"
                else:
                    return (f"已有索引 {idx['name']}({', '.join(idx_cols)}) "
                            f"前缀匹配，建议评估是否需要调整索引列顺序")
        return ""

    def _deduplicate(self, suggestions: list) -> list:
        """去重"""
        seen = set()
        result = []
        for s in suggestions:
            key = (s.table_name, tuple(s.columns), s.suggestion_type)
            if key not in seen:
                seen.add(key)
                result.append(s)
        return result

    def _generate_summary(self, result: IndexAnalysisResult, tables: list) -> str:
        """生成总结"""
        total = len(result.suggestions)
        high_priority = sum(1 for s in result.suggestions if s.priority >= 4)
        conflict = sum(1 for s in result.suggestions if s.existing_index_conflict)
        return (
            f"共分析 {len(tables)} 张表，发现 {total} 个索引建议，"
            f"其中高优先级 {high_priority} 个，已有索引冲突 {conflict} 个"
        )


def _join_col_names(cols: list[str]) -> str:
    """将列名列表拼接为索引名后缀"""
    return "_".join(c.lower() for c in cols)[:30]
