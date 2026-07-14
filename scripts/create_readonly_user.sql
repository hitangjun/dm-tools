-- ============================================================
-- DM数据库SQL优化分析工具 - 只读授权账号创建脚本
-- ============================================================
--
-- 安全说明:
--   本工具仅执行查询操作(执行计划、动态视图、元数据查询等)，
--   不需要任何写权限。建议创建一个专用的只读账号，
--   防止工具执行危险的DDL/DML操作。
--
--   此账号可以:
--   ✅ 查询所有动态性能视图 (V$*)
--   ✅ 查询数据字典 (ALL_TABLES, ALL_INDEXES等)
--   ✅ 执行 EXPLAIN 获取执行计划
--   ✅ 查询表统计信息
--
--   此账号不能:
--   ❌ CREATE / ALTER / DROP (任何DDL)
--   ❌ INSERT / UPDATE / DELETE (任何DML)
--   ❌ 修改配置参数 (SP_SET_PARA_VALUE)
--   ❌ 创建/修改用户
--   ❌ 授予权限
--
-- 使用方法:
--   1. 以SYSDBA身份登录DM数据库
--   2. 执行此脚本创建只读账号
--   3. 在工具连接配置中使用此账号
--
-- ============================================================

-- 步骤1: 创建用户(请修改密码)
-- 注意: 请将 DM_READONLY 替换为你想要的用户名，密码请务必修改
CREATE USER "DM_READONLY" IDENTIFIED BY "Dm_ReadOnly_2024" DEFAULT TABLESPACE MAIN;

-- 步骤2: 授予基本连接权限
GRANT RESOURCE TO "DM_READONLY";

-- 步骤3: 授予查询动态性能视图的权限
-- V$视图查询需要SELECT ANY DICTIONARY权限
GRANT SELECT ANY DICTIONARY TO "DM_READONLY";

-- 步骤4: 授予查询所有用户表的权限(只读)
-- 如果只需要查询特定schema的表，可以用:
-- GRANT SELECT ON schema_name.table_name TO "DM_READONLY";
GRANT SELECT ANY TABLE TO "DM_READONLY";

-- 步骤5: 授予执行EXPLAIN的权限
-- EXPLAIN需要查询权限即可，上面的SELECT权限已覆盖

-- 步骤6: 授予查询数据字典的权限
-- ALL_TABLES, ALL_INDEXES, ALL_TAB_COLUMNS等
-- SELECT ANY DICTIONARY已覆盖

-- ============================================================
-- 验证账号权限(以新账号登录后执行)
-- ============================================================

-- 验证: 可以查询动态视图
-- SELECT * FROM V$INSTANCE;

-- 验证: 可以获取执行计划
-- EXPLAIN SELECT * FROM ALL_TABLES WHERE ROWNUM = 1;

-- 验证: 可以查询慢SQL
-- SELECT * FROM V$LONG_EXEC_SQLS;

-- 验证: 不能执行DDL (应该报错)
-- CREATE TABLE test(id INT);  -- 应该失败

-- 验证: 不能执行DML (应该报错)
-- INSERT INTO ALL_TABLES VALUES(1);  -- 应该失败

-- ============================================================
-- 如需收回权限
-- ============================================================
-- REVOKE SELECT ANY TABLE FROM "DM_READONLY";
-- REVOKE SELECT ANY DICTIONARY FROM "DM_READONLY";
-- REVOKE RESOURCE FROM "DM_READONLY";
-- DROP USER "DM_READONLY";

-- ============================================================
-- 注意事项:
-- 1. 如果ENABLE_MONITOR未开启，部分V$视图可能无数据
--    SYSDBA执行: CALL SP_SET_PARA_VALUE(1, 'ENABLE_MONITOR', 1);
-- 2. 如需查看SQL执行节点耗时，需要开启MONITOR_SQL_EXEC
--    SYSDBA执行: CALL SP_SET_PARA_VALUE(1, 'MONITOR_SQL_EXEC', 1);
-- 3. 密码请使用强密码，不要使用示例中的默认密码
-- 4. 生产环境建议限制该账号的IP访问来源
-- ============================================================
