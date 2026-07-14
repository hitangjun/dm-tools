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
- 完全离线使用，无需网络连接

## 快速开始

### 开发环境运行

```bash
pip install -r requirements.txt
python main.py
```

### 打包为EXE发布(用户无需安装Python)

打包后用户拿到exe直接双击运行，不需要安装Python或任何依赖。打包步骤如下：

#### 前提条件

在打包机器上需要安装：
- Python 3.10+（仅打包机器需要，目标用户不需要）
- 项目依赖：`pip install PySide6 sqlparse`
- 打包工具：`pip install pyinstaller`

#### 方式一：目录模式（推荐）

打包后生成一个文件夹，内含exe和依赖文件。启动速度快，适合分发给用户。

```bash
# 1. 安装打包工具和依赖
pip install pyinstaller PySide6 sqlparse

# 2. 执行打包
pyinstaller --noconsole --name DM_SQL_Optimizer --add-data "db_config.ini.template;." main.py

# 3. 复制配置文件到输出目录
# Windows PowerShell:
Copy-Item db_config.ini.template dist\DM_SQL_Optimizer\db_config.ini
# Linux/Mac:
cp db_config.ini.template dist/DM_SQL_Optimizer/db_config.ini
```

打包完成后 `dist\DM_SQL_Optimizer\` 目录包含：
- `DM_SQL_Optimizer.exe` - 主程序，双击即可运行
- `db_config.ini` - 数据库连接配置文件，用户编辑此文件填写连接信息
- 其他依赖文件（PySide6运行时等，自动生成）

将整个文件夹打包为zip发给用户即可。

#### 方式二：单文件模式

打包后只有一个exe文件，方便分发。但每次启动会稍慢（需要解压临时文件）。

```bash
pyinstaller --noconsole --onefile --name DM_SQL_Optimizer main.py
```

#### 方式三：使用打包脚本

项目已提供打包脚本，一键完成：

```bash
# Windows
build.bat

# Linux/Mac
bash build.sh
```

或使用PyInstaller配置文件：
```bash
pyinstaller dm_sql_optimizer.spec --noconfirm
```

#### 分发给用户的说明

用户拿到打包好的程序后：
1. 解压到任意目录（目录模式）或直接双击exe（单文件模式）
2. 编辑 `db_config.ini` 填写DM数据库连接信息，或启动后在界面中输入
3. 双击 `DM_SQL_Optimizer.exe` 运行
4. 目标机器无需安装Python
5. 目标机器需要安装DM客户端（提供dmdpi.dll驱动库），用于连接DM数据库
6. 如果仅使用SQL规范检查和HINT建议功能（不连接数据库），连DM客户端都不需要

#### Win7兼容性打包

Windows 7 需要特殊版本组合：
- Python 3.10（最后支持Win7的Python版本）
- PySide6 6.4.x（6.5+不支持Win7）

```bash
pip install PySide6==6.4.3
pip install pyinstaller
pyinstaller --noconsole --name DM_SQL_Optimizer --add-data "db_config.ini.template;." main.py
```

目标Win7机器需要安装VC++运行库（vcredist_x64.exe，通常已自带）。

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

| 系统 | 开发环境要求 | EXE运行要求 |
|------|------------|------------|
| Windows 7 | Python 3.10 + PySide6 6.4.x | VC++运行库 + DM客户端 |
| Windows 10/11 | Python 3.10+ + PySide6 6.5+ | DM客户端 |
| Linux | Python 3.10+ + PySide6 | DM客户端(libdmdpi.so) |

打包成EXE后，目标机器无需安装Python。

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
