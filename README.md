# DM数据库SQL优化分析工具

基于达梦官方文档开发的DM数据库SQL优化分析桌面工具，帮助DBA和开发人员快速定位SQL性能问题。

## 功能概览

### 🔍 SQL优化分析
- 执行计划分析 - 解析DM执行计划，识别全表扫描、笛卡尔积、嵌套循环低效等问题
- 索引建议 - 分析WHERE/JOIN/ORDER BY/GROUP BY条件，推荐索引并生成DDL
- 统计信息检查 - 检查表和索引的统计信息是否过期或缺失
- SQL写法规范检查 - 检测SELECT *、隐式类型转换、LIKE前导通配符等10类问题
- HINT优化建议 - 根据SQL结构生成USE_HASH/USE_NL/INDEX等HINT建议

### 📊 动态监控
- 慢SQL抓取 - 查询V$LONG_EXEC_SQLS/V$SYSTEM_LONG_EXEC_SQLS
- 会话监控 - 查询V$SESSIONS，查看活跃会话和SQL
- 系统状态 - V$INSTANCE/V$TABLESPACE/V$BUFFERPOOL命中率
- 锁和事务 - V$LOCK/V$TRX/V$TRXWAIT
- 执行节点耗时 - V$SQL_NODE_HISTORY/V$SQL_NODE_NAME

### 🛠 配置与排查
- 配置参数检查 - 查看ENABLE_MONITOR/OPTIMIZER_MODE等14个关键参数
- 问题排查指引 - 网络/内存/CPU/IO/日志6步排查流程
- SQL最佳实践 - 达梦官方SQL开发优化原则

### 📚 文档知识库
- 内嵌5份达梦官方文档知识(动态管理/问题跟踪/查询优化/SQL调优/执行计划操作符)
- 每个功能上方显示对应文档内容和操作提示
- SQL示例可一键复制

## 快速开始

### 开发环境运行

```bash
pip install -r requirements.txt
python main.py
```

### 打包为EXE(无需安装Python)

```bash
# Windows
pip install pyinstaller
build.bat

# 或手动打包
pyinstaller dm_sql_optimizer.spec --noconfirm
```

打包后的 `dist/` 目录包含:
- `DM_SQL_Optimizer.exe` - 主程序
- `db_config.ini` - 数据库连接配置文件
- 其他依赖文件

### ⚠️ 安全提示：创建只读账号

**强烈建议不要使用SYSDBA账号连接工具！**

请先以SYSDBA身份执行 `scripts/create_readonly_user.sql` 创建一个只读账号，该账号:
- ✅ 可以查询所有动态视图(V$*)和数据字典
- ✅ 可以执行EXPLAIN获取执行计划
- ❌ 不能执行CREATE/ALTER/DROP(DDL)
- ❌ 不能执行INSERT/UPDATE/DELETE(DML)
- ❌ 不能修改配置参数

然后在 `db_config.ini` 或程序界面中使用此只读账号连接。

## 配置文件

复制 `db_config.ini.template` 为 `db_config.ini`，填写DM数据库连接信息:

```ini
[database]
host = 127.0.0.1
port = 5236
user = DM_READONLY
password = YourPassword
schema =
timeout = 30
```

程序启动时会自动读取此文件。也可以在界面中直接输入(会覆盖文件配置)。

## 系统兼容性

| 系统 | 要求 |
|------|------|
| Windows 7 | Python 3.10 + PySide6 6.4.x + VC++运行库 |
| Windows 10/11 | Python 3.10+ + PySide6 6.5+ |
| Linux | Python 3.10+ + PySide6 |

打包成EXE后，目标机器**无需安装Python**，但需要:
- Windows: 安装VC++运行库(通常已自带)
- 所有系统: 安装DM客户端(提供dmdpi.dll/libdmdpi.so驱动库)

## 项目结构

```
dm_sql_optimizer/
├── main.py                         # 应用入口
├── config.py                       # 配置管理(INI+JSON双模式)
├── requirements.txt                # Python依赖
├── build.bat / build.sh            # 打包脚本
├── dm_sql_optimizer.spec           # PyInstaller配置
├── db_config.ini.template          # 配置文件模板
│
├── core/                           # 核心分析模块(无UI依赖)
│   ├── dm_connector.py             # DM数据库连接器
│   ├── plan_analyzer.py            # 执行计划分析
│   ├── index_advisor.py            # 索引建议
│   ├── stats_checker.py            # 统计信息检查
│   ├── sql_linter.py               # SQL写法规范检查
│   ├── dynamic_views.py            # 动态管理视图查询
│   ├── troubleshoot.py             # 问题排查+HINT建议
│   └── doc_knowledge.py            # 达梦文档知识库
│
├── ui/                             # 界面层
│   ├── main_window.py              # 主窗口(多Tab布局)
│   └── widgets/
│       ├── connection_panel.py     # 连接配置面板
│       ├── sql_editor.py           # SQL编辑器(语法高亮)
│       ├── result_panel.py         # 分析结果面板
│       ├── doc_info_widget.py      # 文档信息展示组件
│       ├── dynamic_view_panels.py  # 动态监控面板
│       ├── troubleshoot_panels.py  # 配置排查面板
│       └── knowledge_panel.py      # 知识库浏览面板
│
├── scripts/
│   └── create_readonly_user.sql    # 只读账号创建脚本
│
└── docs/
    └── design.md                   # 设计文档
```

## 文档来源

- [动态管理和性能视图](https://eco.dameng.com/document/dm/zh-cn/pm/dynamic-management.html)
- [问题跟踪和解决](https://eco.dameng.com/document/dm/zh-cn/pm/tracking-resolution.html)
- [查询优化](https://eco.dameng.com/document/dm/zh-cn/pm/query-optimization.html)
- [SQL调优](https://eco.dameng.com/document/dm/zh-cn/pm/sql-tuning.html)
- [附录4 执行计划操作符](https://eco.dameng.com/document/dm/zh-cn/pm/dm8-admin-manual-appendix4.html)
