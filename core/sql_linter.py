"""
SQL写法规范检查模块

检查SQL中的常见写法问题：
- SELECT * 使用
- 隐式类型转换
- OR条件可能导致无法使用索引
- LIKE前导通配符
- 未使用LIMIT/TOP限制结果集
- 函数作用于索引列(可能导致索引失效)
- OR改UNION ALL的潜在机会
- 子查询可优化为JOIN
- 大IN列表
"""
import re
from dataclasses import dataclass, field


@dataclass
class LintRule:
    """SQL规范规则"""
    rule_id: str                # 规则ID
    rule_name: str              # 规则名称
    level: str                  # INFO / WARNING / CRITICAL
    description: str            # 问题描述
    suggestion: str             # 修改建议
    sql_fragment: str = ""      # 问题SQL片段


@dataclass
class LintResult:
    """SQL规范检查结果"""
    rules: list[LintRule] = field(default_factory=list)
    summary: str = ""
    score: int = 100            # 规范评分(0-100, 越高越好)


class SQLLinter:
    """SQL写法规范检查器"""

    def lint(self, sql: str) -> LintResult:
        """
        检查SQL写法规范

        Args:
            sql: SQL语句

        Returns:
            LintResult 检查结果
        """
        result = LintResult()
        sql_stripped = sql.strip().rstrip(";")
        sql_upper = sql_stripped.upper()

        self._check_select_star(sql_stripped, sql_upper, result)
        self._check_implicit_conversion(sql_stripped, sql_upper, result)
        self._check_or_condition(sql_stripped, sql_upper, result)
        self._check_like_wildcard(sql_stripped, sql_upper, result)
        self._check_function_on_column(sql_stripped, sql_upper, result)
        self._check_missing_limit(sql_stripped, sql_upper, result)
        self._check_large_in_list(sql_stripped, sql_upper, result)
        self._check_subquery_in_where(sql_stripped, sql_upper, result)
        self._check_not_equal(sql_stripped, sql_upper, result)
        self._check_is_null(sql_stripped, sql_upper, result)

        result.score = self._calculate_score(result)
        result.summary = self._generate_summary(result)
        return result

    # ------------------------------------------------------------------
    # 规则检查
    # ------------------------------------------------------------------

    def _check_select_star(self, sql: str, sql_upper: str, result: LintResult):
        """R001: SELECT * 检查"""
        if re.search(r'SELECT\s+\*', sql_upper):
            result.rules.append(LintRule(
                rule_id="R001",
                rule_name="SELECT *",
                level="WARNING",
                description="使用了 SELECT *，会返回所有列，"
                            "增加网络传输和内存消耗，也无法利用覆盖索引",
                suggestion="明确列出需要的列名，只查询必要的字段",
                sql_fragment=re.search(r'SELECT\s+\*.*?FROM', sql, re.IGNORECASE).group(0) if re.search(r'SELECT\s+\*.*?FROM', sql, re.IGNORECASE) else "",
            ))

    def _check_implicit_conversion(self, sql: str, sql_upper: str, result: LintResult):
        """R002: 隐式类型转换检查"""
        # 字符串与数字比较
        patterns = [
            (r"WHERE\s+.*?=\s*'\d+'", "字符串与数字比较"),
            (r"WHERE\s+.*?=\s*\d+\s*--.*字符", "数字与字符列比较"),
        ]
        # 检查 WHERE col = '123' (如果col是数字类型)
        # 以及 WHERE col = 123 (如果col是字符类型) - 需要表结构信息才能确定
        # 这里做基础检查: 字符串引号内的纯数字与列比较
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            # 检查数字列被当作字符串比较: col = '123'
            matches = re.findall(r"(\w+)\s*=\s*'(\d+)'", where_clause)
            for col, val in matches:
                result.rules.append(LintRule(
                    rule_id="R002",
                    rule_name="隐式类型转换",
                    level="WARNING",
                    description=f"列 {col} 与字符串 '{val}' 比较时可能发生隐式类型转换，"
                                f"导致索引失效、全表扫描",
                    suggestion=f"确保比较值类型与列类型一致，如 {col} = {val} (不加引号)",
                    sql_fragment=f"{col} = '{val}'",
                ))

    def _check_or_condition(self, sql: str, sql_upper: str, result: LintResult):
        """R003: OR条件可能导致索引失效"""
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            # 统计OR出现次数(排除子查询中的OR)
            or_count = len(re.findall(r'\bOR\b', where_clause, re.IGNORECASE))
            if or_count > 0:
                result.rules.append(LintRule(
                    rule_id="R003",
                    rule_name="OR条件",
                    level="INFO",
                    description=f"WHERE条件中使用了 {or_count} 个OR，"
                                f"OR条件可能导致优化器无法使用索引(尤其两侧列不同时)",
                    suggestion="考虑将OR改写为UNION ALL(如果结果集不重叠)，"
                               "或确保OR两侧的列都有索引",
                    sql_fragment=where_clause.strip()[:100],
                ))

    def _check_like_wildcard(self, sql: str, sql_upper: str, result: LintResult):
        """R004: LIKE前导通配符"""
        matches = re.findall(r"(\w+)\s+LIKE\s+'%([^']+)'", sql, re.IGNORECASE)
        for col, pattern in matches:
            result.rules.append(LintRule(
                rule_id="R004",
                rule_name="LIKE前导通配符",
                level="WARNING",
                description=f"列 {col} 使用了 LIKE '%{pattern}' 前导通配符查询，"
                            f"无法使用索引，必定全表扫描",
                suggestion="避免使用前导通配符；如必须使用模糊查询，"
                           "考虑全文索引或反向存储字段",
                sql_fragment=f"{col} LIKE '%{pattern}'",
            ))

    def _check_function_on_column(self, sql: str, sql_upper: str, result: LintResult):
        """R005: 函数作用于索引列(索引失效)"""
        # 常见会导致索引失效的函数
        functions = [
            "UPPER", "LOWER", "SUBSTR", "TRIM", "TO_CHAR",
            "TO_NUMBER", "TO_DATE", "CAST", "EXTRACT",
            "NVL", "COALESCE", "DECODE", "CASE",
            "REPLACE", "LPAD", "RPAD", "MOD",
        ]
        func_pattern = re.compile(
            r'\b(' + '|'.join(functions) + r')\s*\(\s*(\w+)\s*[,)]',
            re.IGNORECASE,
        )
        # 只在WHERE子句中检查
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            found_cols = set()
            for m in func_pattern.finditer(where_clause):
                func_name = m.group(1).upper()
                col_name = m.group(2)
                if col_name.upper() not in ("AND", "OR", "NOT", "SELECT", "FROM"):
                    key = (func_name, col_name)
                    if key not in found_cols:
                        found_cols.add(key)
                        result.rules.append(LintRule(
                            rule_id="R005",
                            rule_name="函数作用于列",
                            level="WARNING",
                            description=f"WHERE条件中对列 {col_name} 使用了函数 {func_name}()，"
                                        f"会导致该列上的索引失效",
                            suggestion=f"改写为等价的不使用函数的形式，"
                                       f"或创建基于函数的索引: CREATE INDEX ... ON table({func_name}({col_name}))",
                            sql_fragment=m.group(0),
                        ))

    def _check_missing_limit(self, sql: str, sql_upper: str, result: LintResult):
        """R006: 查询未限制结果集大小"""
        if "SELECT" in sql_upper and "TOP" not in sql_upper and "LIMIT" not in sql_upper:
            # 排除子查询和聚合查询
            has_aggregate = any(
                agg in sql_upper
                for agg in ["COUNT(", "SUM(", "AVG(", "MAX(", "MIN(", "GROUP BY"]
            )
            has_where = "WHERE" in sql_upper
            if not has_aggregate and has_where:
                result.rules.append(LintRule(
                    rule_id="R006",
                    rule_name="未限制结果集",
                    level="INFO",
                    description="查询未使用TOP/LIMIT限制返回行数，"
                                "可能返回大量数据导致性能问题",
                    suggestion="添加 TOP N 或 LIMIT 子句限制返回行数",
                ))

    def _check_large_in_list(self, sql: str, sql_upper: str, result: LintResult):
        """R007: 大IN列表"""
        # 匹配 IN (v1, v2, v3, ...) 并计算元素数量
        in_pattern = re.compile(r'IN\s*\(([^()]+)\)', re.IGNORECASE)
        for m in in_pattern.finditer(sql):
            in_list = m.group(1)
            item_count = len([x for x in in_list.split(",") if x.strip()])
            if item_count > 10:
                result.rules.append(LintRule(
                    rule_id="R007",
                    rule_name="大IN列表",
                    level="WARNING",
                    description=f"IN列表包含 {item_count} 个元素，"
                                f"过大的IN列表会导致性能下降(解析开销大，可能走全表扫描)",
                    suggestion="考虑使用临时表/表变量JOIN替代大IN列表，"
                               "或将IN列表拆分为多个小IN并使用UNION ALL",
                    sql_fragment=f"IN ({in_list[:80]}...)" if len(in_list) > 80 else f"IN ({in_list})",
                ))

    def _check_subquery_in_where(self, sql: str, sql_upper: str, result: LintResult):
        """R008: WHERE中的子查询可优化为JOIN"""
        # 检查 WHERE ... IN (SELECT ...) 或 WHERE ... = (SELECT ...)
        patterns = [
            (r'WHERE\s+.*?IN\s*\(\s*SELECT', "IN子查询"),
            (r'WHERE\s+.*?=\s*\(\s*SELECT', "标量子查询"),
            (r'WHERE\s+.*?NOT\s+IN\s*\(\s*SELECT', "NOT IN子查询"),
        ]
        for pattern, subquery_type in patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                result.rules.append(LintRule(
                    rule_id="R008",
                    rule_name=f"WHERE中的{subquery_type}",
                    level="INFO" if "NOT IN" not in subquery_type else "WARNING",
                    description=f"WHERE条件中使用了{subquery_type}，"
                                f"子查询可能导致执行计划效率低下"
                                + ("，NOT IN对NULL值敏感可能产生错误结果" if "NOT IN" in subquery_type else ""),
                    suggestion="考虑将子查询改写为JOIN( INNER JOIN 或 LEFT JOIN)，"
                               "通常JOIN的执行计划更优",
                ))
                break

    def _check_not_equal(self, sql: str, sql_upper: str, result: LintResult):
        """R009: != / <> 操作符"""
        where_match = re.search(r'WHERE\s+(.+?)(?:GROUP|ORDER|LIMIT|TOP|$)', sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            matches = re.findall(r'(\w+)\s*(?:!=|<>)\s*', where_clause)
            for col in matches:
                if col.upper() not in ("AND", "OR", "NOT"):
                    result.rules.append(LintRule(
                        rule_id="R009",
                        rule_name="不等于操作符",
                        level="INFO",
                        description=f"列 {col} 使用了 != 或 <> 操作符，"
                                    f"不等于操作通常无法使用索引",
                        suggestion="如可能，改写为范围查询(> max_value OR < min_value) "
                                   "或使用其他条件替代",
                        sql_fragment=f"{col} != ...",
                    ))
                    break

    def _check_is_null(self, sql: str, sql_upper: str, result: LintResult):
        """R010: IS NOT NULL检查"""
        if re.search(r'IS\s+NOT\s+NULL', sql_upper):
            result.rules.append(LintRule(
                rule_id="R010",
                rule_name="IS NOT NULL",
                level="INFO",
                description="使用了 IS NOT NULL 条件，通常无法有效使用普通索引",
                suggestion="如果频繁查询非NULL记录，考虑创建过滤索引或位图索引",
            ))

    # ------------------------------------------------------------------
    # 评分和总结
    # ------------------------------------------------------------------

    def _calculate_score(self, result: LintResult) -> int:
        """计算规范评分"""
        score = 100
        for rule in result.rules:
            if rule.level == "CRITICAL":
                score -= 20
            elif rule.level == "WARNING":
                score -= 10
            elif rule.level == "INFO":
                score -= 4
        return max(0, min(100, score))

    def _generate_summary(self, result: LintResult) -> str:
        """生成总结"""
        critical = sum(1 for r in result.rules if r.level == "CRITICAL")
        warning = sum(1 for r in result.rules if r.level == "WARNING")
        info = sum(1 for r in result.rules if r.level == "INFO")

        if result.score >= 80:
            rating = "规范"
        elif result.score >= 60:
            rating = "基本规范"
        else:
            rating = "不规范"

        return (
            f"SQL规范评分: {rating} ({result.score}/100)\n"
            f"问题统计: 严重{critical} | 警告{warning} | 提示{info}"
        )
