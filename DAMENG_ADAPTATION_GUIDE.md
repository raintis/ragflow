# RAGFlow 达梦数据库适配指南

## 概述

本文档详细说明了在 RAGFlow 中实现达梦数据库（DM, DaMeng）适配的完整方案。达梦是国产开源关系型数据库，需要在现有的 MySQL 基础设施上进行必要的扩展和兼容性处理。

---

## 一、数据库驱动与连接配置

### 1.1 依赖安装

在 `pyproject.toml` 中添加达梦数据库驱动：

```toml
[project]
dependencies = [
    # ... 其他依赖
    "pydmdb>=1.0.0",  # 达梦数据库 Python 驱动
    # 或使用官方驱动
    "dm-sql-driver>=1.0.0",
]
```

### 1.2 连接字符串格式

达梦数据库的连接字符串格式：

```
dm://[user[:password]@][host][:port]/[database]
```

示例：
```python
# 基础连接
"dm://root:password@localhost:5236/rag_flow"

# 带连接池
"dm+pymysql://root:password@localhost:5236/rag_flow"
```

### 1.3 配置文件示例

在 `conf/service_conf.yaml` 中增加达梦配置：

```yaml
dameng:
  name: 'rag_flow'          # 数据库名称
  user: 'SYSDBA'            # 用户名 (达梦默认管理员)
  password: 'DmPassword'    # 密码
  host: 'localhost'
  port: 5236                # 达梦默认端口
  max_connections: 900
  stale_timeout: 300
  max_allowed_packet: 1073741824
```

---

## 二、核心代码修改

### 2.1 common/config_utils.py

**修改内容**：添加达梦数据库配置解析

```python
def decrypt_database_config(name: str = "mysql") -> dict:
    """
    解密并获取数据库配置，支持 MySQL 和达梦
    """
    from common.config_utils import get_base_config
    
    if name.lower() in ["dameng", "dm"]:
        config = get_base_config("dameng", {})
        return {
            "dialect": "dameng",
            "user": config.get("user", "SYSDBA"),
            "password": config.get("password", ""),
            "host": config.get("host", "localhost"),
            "port": config.get("port", 5236),
            "database": config.get("name", "rag_flow"),
            "max_connections": config.get("max_connections", 900),
            "stale_timeout": config.get("stale_timeout", 300),
        }
    else:
        # 保持现有 MySQL 配置
        config = get_base_config("mysql", {})
        return {
            "dialect": "mysql",
            "user": config.get("user", "root"),
            "password": config.get("password", ""),
            "host": config.get("host", "localhost"),
            "port": config.get("port", 3306),
            "database": config.get("name", "rag_flow"),
            "max_connections": config.get("max_connections", 900),
            "stale_timeout": config.get("stale_timeout", 300),
        }
```

### 2.2 api/db/db_models.py

**修改内容**：更新数据库连接和初始化

关键修改点：

```python
from playhouse.pool import PooledMySQLDatabase, PooledPostgresqlDatabase
from common.config_utils import decrypt_database_config
from common.settings import DATABASE_TYPE

def init_database():
    """初始化数据库连接"""
    global DB
    
    db_config = decrypt_database_config(name=DATABASE_TYPE)
    dialect = db_config.get("dialect", "mysql")
    
    if dialect == "dameng":
        # 达梦数据库连接
        DB = PooledMySQLDatabase(
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
            host=db_config["host"],
            port=db_config["port"],
            max_connections=db_config.get("max_connections", 900),
            stale_timeout=db_config.get("stale_timeout", 300),
            charset='utf8mb4',
            init_command="SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE'",
        )
    elif dialect == "mysql":
        # MySQL 数据库连接
        DB = PooledMySQLDatabase(
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"],
            host=db_config["host"],
            port=db_config["port"],
            max_connections=db_config.get("max_connections", 900),
            stale_timeout=db_config.get("stale_timeout", 300),
            charset='utf8mb4',
        )
    else:
        raise ValueError(f"Unsupported database type: {dialect}")
    
    return DB

# 初始化
DB = init_database()
```

### 2.3 达梦特定的 SQL 兼容性处理

**新建文件**：`api/db/dameng_compat.py`

```python
"""
达梦数据库兼容性处理模块

达梦与 MySQL 的差异处理：
1. 数据类型映射
2. SQL 语法差异
3. 时间戳格式
4. 字符编码
"""

# 数据类型映射表
DAMENG_TYPE_MAPPING = {
    "BIGINT": "BIGINT",
    "INT": "INTEGER",
    "VARCHAR": "VARCHAR",
    "TEXT": "CLOB",
    "LONGTEXT": "CLOB",
    "TIMESTAMP": "TIMESTAMP",
    "DATETIME": "TIMESTAMP",
    "DATE": "DATE",
    "DOUBLE": "DOUBLE",
    "FLOAT": "FLOAT",
    "DECIMAL": "DECIMAL",
    "BOOLEAN": "SMALLINT",  # 达梦用 SMALLINT(0/1) 表示布尔值
    "JSON": "VARCHAR",      # 达梦用 VARCHAR 存储 JSON
}

def get_dameng_type(mysql_type: str) -> str:
    """将 MySQL 类型转换为达梦类型"""
    return DAMENG_TYPE_MAPPING.get(mysql_type.upper(), mysql_type)

def adapt_sql_for_dameng(sql: str) -> str:
    """
    将 MySQL SQL 语句适配为达梦 SQL
    处理常见的语法差异
    """
    # 1. ON DUPLICATE KEY UPDATE -> MERGE INTO
    if "ON DUPLICATE KEY UPDATE" in sql.upper():
        sql = convert_duplicate_key_to_merge(sql)
    
    # 2. AUTO_INCREMENT -> IDENTITY
    sql = sql.replace("AUTO_INCREMENT", "IDENTITY")
    
    # 3. UNSIGNED 修饰符
    sql = sql.replace("UNSIGNED", "")
    
    # 4. 反引号替换为双引号
    sql = sql.replace("`", '"')
    
    return sql

def convert_duplicate_key_to_merge(sql: str) -> str:
    """
    将 MySQL 的 ON DUPLICATE KEY UPDATE 转换为达梦的 MERGE INTO
    
    示例转换：
    MySQL:  INSERT INTO t (id, name) VALUES (1, 'test') 
            ON DUPLICATE KEY UPDATE name = 'test'
    
    达梦:   MERGE INTO t USING dual 
            WHEN MATCHED THEN UPDATE SET name = 'test' 
            WHEN NOT MATCHED THEN INSERT (id, name) VALUES (1, 'test')
    """
    # 这是一个简化的实现，实际场景需要更复杂的 SQL 解析
    import re
    
    # 提取 INSERT 和 UPDATE 部分
    insert_match = re.search(r'INSERT INTO (\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)', sql, re.IGNORECASE)
    update_match = re.search(r'ON DUPLICATE KEY UPDATE\s*(.*?)(?:;|$)', sql, re.IGNORECASE)
    
    if insert_match and update_match:
        table = insert_match.group(1)
        columns = insert_match.group(2)
        values = insert_match.group(3)
        update_clause = update_match.group(1)
        
        # 构建 MERGE 语句（简化版本）
        # 完整实现需要更复杂的解析逻辑
        merged_sql = f"""
        MERGE INTO {table} t
        USING (SELECT {values} AS ({columns})) s
        ON (t.id = s.id)
        WHEN MATCHED THEN
            UPDATE SET {update_clause}
        WHEN NOT MATCHED THEN
            INSERT ({columns}) VALUES (s.{columns.replace(', ', ', s.')})
        """
        return merged_sql
    
    return sql

def get_auto_increment_query(table_name: str, column_name: str = "id") -> str:
    """获取自增 ID，达梦方式"""
    return f"SELECT CURRVAL('{table_name}_{column_name}_seq') FROM DUAL"

class DamengDialect:
    """达梦数据库方言类"""
    
    name = "dameng"
    supports_sane_rowcount = True
    supports_sane_multi_rowcount = True
    
    @staticmethod
    def get_create_table_sql(table_name: str, columns: dict) -> str:
        """生成达梦格式的建表语句"""
        parts = [f'CREATE TABLE "{table_name}" (']
        
        for col_name, col_def in columns.items():
            col_type = get_dameng_type(col_def['type'])
            parts.append(f'  "{col_name}" {col_type}')
            
            if col_def.get('primary_key'):
                parts.append(' PRIMARY KEY')
            if col_def.get('not_null'):
                parts.append(' NOT NULL')
            if col_def.get('default'):
                parts.append(f" DEFAULT {col_def['default']}")
            
            parts.append(',')
        
        # 移除最后的逗号
        parts[-1] = parts[-1].rstrip(',')
        parts.append(')')
        
        return '\n'.join(parts)
```

### 2.4 common/settings.py 修改

**修改位置**：第 73-74 行

```python
# 原有代码
DATABASE_TYPE = os.getenv("DB_TYPE", "mysql")
DATABASE = decrypt_database_config(name=DATABASE_TYPE)

# 新增兼容性检查
def _normalize_db_type(db_type: str) -> str:
    """规范化数据库类型名称"""
    db_type = db_type.lower()
    if db_type in ["dameng", "dm"]:
        return "dameng"
    return db_type

DATABASE_TYPE = _normalize_db_type(os.getenv("DB_TYPE", "mysql"))
DATABASE = decrypt_database_config(name=DATABASE_TYPE)
```

---

## 三、数据库初始化脚本

### 3.1 创建达梦初始化脚本

**新建文件**：`sql/dameng_init.sql`

```sql
-- RAGFlow 达梦数据库初始化脚本
-- 版本: 1.0
-- 说明: 为达梦数据库创建 RAGFlow 所需的所有表

-- 创建数据库（如果不存在）
CREATE SCHEMA IF NOT EXISTS "rag_flow";
USE "rag_flow";

-- 设置字符集
ALTER SESSION SET NLS_CHARACTERSET = 'UTF-8';

-- 创建基础表
-- 用户表
CREATE TABLE "user" (
    "id" VARCHAR(32) PRIMARY KEY,
    "username" VARCHAR(255) NOT NULL UNIQUE,
    "password" VARCHAR(255) NOT NULL,
    "email" VARCHAR(255),
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    "status" SMALLINT DEFAULT 1
);

-- 租户表
CREATE TABLE "tenant" (
    "id" VARCHAR(32) PRIMARY KEY,
    "name" VARCHAR(255) NOT NULL,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL
);

-- 知识库表
CREATE TABLE "knowledge_base" (
    "id" VARCHAR(32) PRIMARY KEY,
    "tenant_id" VARCHAR(32) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "description" CLOB,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("tenant_id") REFERENCES "tenant"("id")
);

-- 文档表
CREATE TABLE "document" (
    "id" VARCHAR(32) PRIMARY KEY,
    "kb_id" VARCHAR(32) NOT NULL,
    "name" VARCHAR(255) NOT NULL,
    "size" BIGINT,
    "status" SMALLINT DEFAULT 1,
    "create_time" BIGINT NOT NULL,
    "create_date" DATE NOT NULL,
    "update_time" BIGINT NOT NULL,
    "update_date" DATE NOT NULL,
    FOREIGN KEY ("kb_id") REFERENCES "knowledge_base"("id")
);

-- 创建索引优化查询
CREATE INDEX "idx_user_username" ON "user"("username");
CREATE INDEX "idx_tenant_id" ON "knowledge_base"("tenant_id");
CREATE INDEX "idx_kb_id" ON "document"("kb_id");
CREATE INDEX "idx_doc_status" ON "document"("status");

-- 授权（可选）
-- GRANT ALL PRIVILEGES ON "rag_flow".* TO 'rag_flow'@'localhost';
```

### 3.2 创建迁移脚本

**新建文件**：`sql/migrate_mysql_to_dameng.sql`

```sql
-- MySQL 到达梦的数据迁移脚本
-- 说明: 这是一个辅助脚本，用于数据库迁移

-- 步骤 1: 导出 MySQL 数据
-- 使用命令: mysqldump -u root -p rag_flow > mysql_backup.sql

-- 步骤 2: 修改备份文件
-- - 移除 MySQL 特定的注释
-- - 修改数据类型
-- - 修改字符集声明

-- 步骤 3: 导入到达梦
-- 使用达梦的客户端工具导入修改后的 SQL 文件

-- 常见转换规则
-- VARCHAR(255) -> VARCHAR(255)
-- LONGTEXT -> CLOB
-- TIMESTAMP -> TIMESTAMP
-- BIGINT UNSIGNED -> BIGINT
-- AUTO_INCREMENT -> 使用序列或触发器
```

---

## 四、环境变量配置

### 4.1 启用达梦数据库

在启动 RAGFlow 时，设置以下环境变量：

```bash
# 使用达梦数据库
export DB_TYPE=dameng

# 或在 Docker 中
docker run -e DB_TYPE=dameng \
           -e DAMENG_HOST=localhost \
           -e DAMENG_PORT=5236 \
           -e DAMENG_USER=SYSDBA \
           -e DAMENG_PASSWORD=DmPassword \
           -e DAMENG_DB=rag_flow \
           ragflow:latest
```

### 4.2 Docker Compose 配置示例

```yaml
version: '3.8'

services:
  ragflow:
    image: ragflow:latest
    environment:
      DB_TYPE: dameng
      DAMENG_HOST: dameng-db
      DAMENG_PORT: 5236
      DAMENG_USER: SYSDBA
      DAMENG_PASSWORD: DmPassword
      DAMENG_DB: rag_flow
    depends_on:
      - dameng-db
    ports:
      - "9380:9380"
      - "9381:9381"

  dameng-db:
    image: dameng:8.0  # 达梦官方镜像
    environment:
      DAMENG_ADMIN_PWD: DmPassword
    ports:
      - "5236:5236"
    volumes:
      - dameng_data:/opt/dmdbms/data
      - ./sql/dameng_init.sql:/docker-entrypoint-initdb.d/init.sql

volumes:
  dameng_data:
```

---

## 五、兼容性注意事项

### 5.1 数据类型兼容性

| MySQL | 达梦 | 说明 |
|-------|------|------|
| BIGINT UNSIGNED | BIGINT | 达梦不支持 UNSIGNED |
| LONGTEXT | CLOB | 大文本类型 |
| TEXT | CLOB | 文本类型 |
| TIMESTAMP | TIMESTAMP | 时间戳类型 |
| JSON | VARCHAR(4000) | JSON 存储为字符串 |
| BOOLEAN | SMALLINT(0/1) | 布尔值用整数表示 |

### 5.2 SQL 语法差异

| 功能 | MySQL | 达梦 | 处理方案 |
|------|-------|------|---------|
| 自增主键 | AUTO_INCREMENT | IDENTITY / 序列 | 使用兼容层转换 |
| 重复键更新 | ON DUPLICATE KEY UPDATE | MERGE INTO | 在代码中处理 |
| 查询偏移 | LIMIT offset, count | OFFSET offset ROWS FETCH count ROWS ONLY | ORM 层处理 |
| 分页 | LIMIT | FETCH NEXT ... ROWS | ORM 层处理 |
| 事务隔离 | READ_COMMITTED | READ_COMMITTED | 保持一致 |
| 时间函数 | NOW() | SYSDATE() | SQL 适配层处理 |

### 5.3 字符集与排序规则

```sql
-- 达梦字符集设置
SET NLS_CHARACTERSET = 'UTF-8';
SET NLS_NCHARSET = 'UTF-8';

-- 校对规则（可选）
SET NLS_SORT = 'SCHINESE_RADICAL_M';  -- 中文排序
```

---

## 六、性能优化建议

### 6.1 连接池配置

```python
# 根据 RAGFlow 的并发需求调整
max_connections = 900
stale_timeout = 300
connection_init_timeout = 30
```

### 6.2 索引创建

```sql
-- 关键查询索引
CREATE INDEX "idx_kb_tenant" ON "knowledge_base"("tenant_id", "name");
CREATE INDEX "idx_doc_kb_status" ON "document"("kb_id", "status");
CREATE INDEX "idx_user_create_time" ON "user"("create_time" DESC);
```

### 6.3 批量操作优化

```python
# 使用批量插入而不是逐行插入
INSERT INTO "table_name" (col1, col2) VALUES (?, ?), (?, ?), (?, ?);

# 批量大小建议：1000-5000 条记录
BATCH_SIZE = 1000
```

---

## 七、测试清单

### 7.1 功能测试

- [ ] 数据库连接测试
- [ ] 表创建和数据插入
- [ ] 基本 CRUD 操作
- [ ] 事务处理
- [ ] 连接池管理
- [ ] 批量操作
- [ ] 复杂查询（JOIN、分组聚合等）

### 7.2 性能测试

- [ ] 单条记录插入/查询时间
- [ ] 批量操作吞吐量
- [ ] 连接池稳定性
- [ ] 并发操作能力
- [ ] 长连接稳定性

### 7.3 集成测试

- [ ] RAGFlow 启动和初始化
- [ ] 用户认证和会话管理
- [ ] 知识库操作
- [ ] 文档上传和处理
- [ ] 搜索和检索功能

---

## 八、故障排查

### 8.1 常见错误

#### 错误 1: "连接被拒绝"
```
原因: 达梦数据库未启动或端口不正确
解决: 检查达梦服务状态和端口配置（默认 5236）
```

#### 错误 2: "字符集不匹配"
```
原因: 数据库和应用程序字符集不一致
解决: 确保使用 UTF-8 字符集，在 SQL 会话中设置 NLS_CHARACTERSET
```

#### 错误 3: "事务隔离级别冲突"
```
原因: 达梦的事务隔离级别设置不当
解决: 使用 READ_COMMITTED 隔离级别
```

### 8.2 调试日志

```python
# 启用 SQL 调试日志
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('peewee').setLevel(logging.DEBUG)

# 查看生成的 SQL 语句
from api.db.db_models import DB
DB.set_debug_sql_enabled(True)
```

---

## 九、维护和升级

### 9.1 数据库备份

```bash
# 达梦数据库备份
dmexp userid=SYSDBA/password@localhost:5236 directory=./backup

# 恢复备份
dmimp userid=SYSDBA/password@localhost:5236 directory=./backup
```

### 9.2 版本升级路径

当升级 RAGFlow 版本时：

1. 备份现有达梦数据库
2. 执行新版本的迁移脚本
3. 运行数据校验脚本
4. 测试关键功能
5. 更新文档和配置

---

## 十、参考资源

### 达梦官方资源

- [达梦数据库官网](https://www.dameng.com/)
- [达梦数据库文档](https://eco.dameng.com/document)
- [达梦 Python 驱动](https://github.com/dameng-open-source/python-driver)

### RAGFlow 资源

- [RAGFlow GitHub](https://github.com/infiniflow/ragflow)
- [RAGFlow 文档](https://docs.ragflow.io/)

---

## 更新历史

| 版本 | 日期 | 内容 |
|------|------|------|
| 1.0 | 2024-06-15 | 初版，完整的达梦适配指南 |

---

## 许可证

本文档遵循 Apache License 2.0，与 RAGFlow 项目保持一致。
