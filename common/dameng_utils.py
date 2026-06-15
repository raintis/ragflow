#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#

"""
达梦数据库兼容性处理模块

本模块提供达梦数据库与 MySQL 之间的兼容性处理，包括：
- SQL 语法转换
- 数据类型映射
- 时间函数适配
- 批量操作优化
"""

import re
import logging
from typing import Dict, List, Tuple, Optional, Any

logger = logging.getLogger(__name__)

# 数据类型映射表
DAMENG_TYPE_MAPPING = {
    "BIGINT UNSIGNED": "BIGINT",
    "BIGINT": "BIGINT",
    "INT UNSIGNED": "INTEGER",
    "INT": "INTEGER",
    "INTEGER UNSIGNED": "INTEGER",
    "INTEGER": "INTEGER",
    "SMALLINT UNSIGNED": "SMALLINT",
    "SMALLINT": "SMALLINT",
    "TINYINT": "SMALLINT",
    "VARCHAR": "VARCHAR",
    "CHAR": "CHAR",
    "TEXT": "CLOB",
    "MEDIUMTEXT": "CLOB",
    "LONGTEXT": "CLOB",
    "TIMESTAMP": "TIMESTAMP",
    "DATETIME": "TIMESTAMP",
    "DATE": "DATE",
    "TIME": "TIME",
    "DOUBLE UNSIGNED": "DOUBLE",
    "DOUBLE": "DOUBLE",
    "FLOAT UNSIGNED": "FLOAT",
    "FLOAT": "FLOAT",
    "DECIMAL": "DECIMAL",
    "NUMERIC": "NUMERIC",
    "BOOLEAN": "SMALLINT",
    "BOOL": "SMALLINT",
    "JSON": "VARCHAR",
    "BINARY": "BLOB",
    "VARBINARY": "BLOB",
    "BLOB": "BLOB",
    "LONGBLOB": "BLOB",
}

# SQL 关键字映射
DAMENG_KEYWORD_MAPPING = {
    "AUTO_INCREMENT": "IDENTITY",
    "UNSIGNED": "",
    "ZEROFILL": "",
}

# 时间函数映射
DAMENG_TIME_FUNCTION_MAPPING = {
    "NOW()": "SYSDATE()",
    "CURRENT_TIMESTAMP()": "SYSDATE()",
    "UNIX_TIMESTAMP()": "EXTRACT(EPOCH FROM SYSDATE())",
    "FROM_UNIXTIME": "TO_TIMESTAMP",
    "CURDATE()": "TRUNC(SYSDATE())",
    "CURRENT_DATE()": "TRUNC(SYSDATE())",
    "CURTIME()": "TO_CHAR(SYSDATE(), 'HH24:MI:SS')",
    "CURRENT_TIME()": "TO_CHAR(SYSDATE(), 'HH24:MI:SS')",
}

# 字符串函数映射
DAMENG_STRING_FUNCTION_MAPPING = {
    "CONCAT": "||",
    "SUBSTRING": "SUBSTR",
    "SUBSTR": "SUBSTR",
    "LENGTH": "LENGTH",
    "CHAR_LENGTH": "LENGTH",
    "UPPER": "UPPER",
    "LOWER": "LOWER",
    "TRIM": "TRIM",
    "LTRIM": "LTRIM",
    "RTRIM": "RTRIM",
    "REPLACE": "REPLACE",
    "INSTR": "INSTR",
}


def get_dameng_type(mysql_type: str) -> str:
    """
    将 MySQL 类型转换为达梦类型
    
    Args:
        mysql_type: MySQL 数据类型字符串
        
    Returns:
        达梦数据类型字符串
    """
    # 清理输入
    mysql_type = mysql_type.upper().strip()
    
    # 精确匹配
    if mysql_type in DAMENG_TYPE_MAPPING:
        return DAMENG_TYPE_MAPPING[mysql_type]
    
    # 前缀匹配（处理带长度的类型，如 VARCHAR(255)）
    for key, value in DAMENG_TYPE_MAPPING.items():
        if mysql_type.startswith(key):
            # 保留长度信息
            if "(" in mysql_type:
                length = mysql_type[mysql_type.index("("):]
                return value + length
            return value
    
    # 默认返回原始类型
    logger.warning(f"Unknown MySQL type: {mysql_type}, using as-is")
    return mysql_type


def adapt_sql_for_dameng(sql: str) -> str:
    """
    将 MySQL SQL 语句适配为达梦 SQL
    
    处理以下转换：
    1. 数据类型
    2. 关键字
    3. 时间函数
    4. 字符串函数
    5. 分页语法
    
    Args:
        sql: MySQL SQL 语句
        
    Returns:
        达梦 SQL 语句
    """
    if not sql:
        return sql
    
    original_sql = sql
    sql = sql.strip()
    
    try:
        # 1. 转换关键字
        sql = _convert_keywords(sql)
        
        # 2. 转换时间函数
        sql = _convert_time_functions(sql)
        
        # 3. 转换字符串函数
        sql = _convert_string_functions(sql)
        
        # 4. 处理反引号（MySQL 中用于标识符）
        sql = sql.replace("`", '"')
        
        # 5. 处理 ON DUPLICATE KEY UPDATE
        if "ON DUPLICATE KEY UPDATE" in sql.upper():
            sql = _convert_duplicate_key_to_merge(sql)
        
        # 6. 处理分页语法
        sql = _convert_pagination_syntax(sql)
        
        logger.debug(f"SQL adapted from MySQL to DaMeng:\nOriginal: {original_sql}\nAdapted: {sql}")
        
        return sql
        
    except Exception as e:
        logger.error(f"Error adapting SQL for DaMeng: {e}\nSQL: {original_sql}")
        return original_sql


def _convert_keywords(sql: str) -> str:
    """转换 MySQL 关键字为达梦关键字"""
    for mysql_kw, dameng_kw in DAMENG_KEYWORD_MAPPING.items():
        # 使用正则表达式进行不区分大小写的替换
        pattern = re.compile(re.escape(mysql_kw), re.IGNORECASE)
        sql = pattern.sub(dameng_kw, sql)
    
    return sql


def _convert_time_functions(sql: str) -> str:
    """转换时间函数"""
    for mysql_func, dameng_func in DAMENG_TIME_FUNCTION_MAPPING.items():
        # 处理大小写
        pattern = re.compile(re.escape(mysql_func), re.IGNORECASE)
        sql = pattern.sub(dameng_func, sql)
    
    return sql


def _convert_string_functions(sql: str) -> str:
    """转换字符串函数"""
    for mysql_func, dameng_func in DAMENG_STRING_FUNCTION_MAPPING.items():
        # 使用单词边界匹配，避免部分匹配
        pattern = re.compile(r'\b' + re.escape(mysql_func) + r'\b', re.IGNORECASE)
        sql = pattern.sub(dameng_func, sql)
    
    return sql


def _convert_duplicate_key_to_merge(sql: str) -> str:
    """
    将 MySQL 的 ON DUPLICATE KEY UPDATE 转换为达梦的 MERGE INTO
    
    示例转换：
    MySQL:  INSERT INTO t (id, name) VALUES (1, 'test') 
            ON DUPLICATE KEY UPDATE name = 'test'
    
    达梦:   MERGE INTO t USING DUAL 
            WHEN MATCHED THEN UPDATE SET name = 'test'
            WHEN NOT MATCHED THEN INSERT (id, name) VALUES (1, 'test')
    
    注意：此转换仅适用于简单情况。复杂的 SQL 语句需要应用层处理。
    """
    try:
        # 提取 INSERT 部分
        insert_pattern = r'INSERT\s+INTO\s+(\w+)\s*\((.*?)\)\s*VALUES\s*\((.*?)\)'
        insert_match = re.search(insert_pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not insert_match:
            logger.warning("Could not parse INSERT statement for ON DUPLICATE KEY UPDATE conversion")
            return sql
        
        table_name = insert_match.group(1)
        columns = insert_match.group(2).strip()
        values = insert_match.group(3).strip()
        
        # 提取 UPDATE 部分
        update_pattern = r'ON\s+DUPLICATE\s+KEY\s+UPDATE\s+(.*?)(?:;|$)'
        update_match = re.search(update_pattern, sql, re.IGNORECASE | re.DOTALL)
        
        if not update_match:
            logger.warning("Could not parse ON DUPLICATE KEY UPDATE clause")
            return sql
        
        update_clause = update_match.group(1).strip()
        
        # 构建 MERGE INTO 语句
        merged_sql = f"""MERGE INTO \"{table_name}\" t
USING DUAL
WHEN MATCHED THEN
    UPDATE SET {update_clause}
WHEN NOT MATCHED THEN
    INSERT ({columns}) VALUES ({values})"""
        
        logger.debug(f"Converted ON DUPLICATE KEY UPDATE to MERGE INTO:\n{merged_sql}")
        
        return merged_sql
        
    except Exception as e:
        logger.error(f"Error converting ON DUPLICATE KEY UPDATE: {e}")
        return sql


def _convert_pagination_syntax(sql: str) -> str:
    """
    转换分页语法
    
    MySQL: LIMIT offset, count 或 LIMIT count OFFSET offset
    达梦:  OFFSET offset ROWS FETCH NEXT count ROWS ONLY
    """
    # 处理 LIMIT offset, count 格式
    limit_pattern = r'LIMIT\s+(\d+)\s*,\s*(\d+)'
    sql = re.sub(limit_pattern, r'OFFSET \1 ROWS FETCH NEXT \2 ROWS ONLY', sql, flags=re.IGNORECASE)
    
    # 处理 LIMIT count OFFSET offset 格式
    limit_offset_pattern = r'LIMIT\s+(\d+)\s+OFFSET\s+(\d+)'
    sql = re.sub(limit_offset_pattern, r'OFFSET \2 ROWS FETCH NEXT \1 ROWS ONLY', sql, flags=re.IGNORECASE)
    
    # 处理单独 LIMIT count 格式（无 OFFSET）
    limit_only_pattern = r'LIMIT\s+(\d+)(?!\s*OFFSET)'
    sql = re.sub(limit_only_pattern, r'FETCH NEXT \1 ROWS ONLY', sql, flags=re.IGNORECASE)
    
    return sql


def get_auto_increment_query(table_name: str, column_name: str = "id") -> str:
    """
    获取自增 ID（达梦方式）
    
    Args:
        table_name: 表名
        column_name: 列名（默认为 id）
        
    Returns:
        获取自增 ID 的 SQL 语句
    """
    # 达梦使用 LASTVAL() 或序列
    return f'SELECT LASTVAL() FROM DUAL'


def create_sequence_sql(table_name: str, column_name: str = "id", start: int = 1, increment: int = 1) -> str:
    """
    创建序列（用于自增）
    
    Args:
        table_name: 表名
        column_name: 列名
        start: 起始值
        increment: 增量
        
    Returns:
        创建序列的 SQL 语句
    """
    sequence_name = f"seq_{table_name}_{column_name}"
    return f"""CREATE SEQUENCE \"{sequence_name}\" 
    START WITH {start} 
    INCREMENT BY {increment} 
    NOCYCLE 
    CACHE 20"""


def create_trigger_sql(table_name: str, column_name: str = "id") -> str:
    """
    创建触发器（用于自动生成 ID）
    
    Args:
        table_name: 表名
        column_name: 列名
        
    Returns:
        创建触发器的 SQL 语句
    """
    sequence_name = f"seq_{table_name}_{column_name}"
    trigger_name = f"trg_{table_name}_{column_name}"
    
    return f"""CREATE TRIGGER \"{trigger_name}\"
    BEFORE INSERT ON \"{table_name}\"
    REFERENCING NEW AS new
    FOR EACH ROW
    BEGIN
        IF :new.{column_name} IS NULL THEN
            SELECT {sequence_name}.NEXTVAL INTO :new.{column_name} FROM DUAL;
        END IF;
    END
    /"""


class DamengCompatibilityLayer:
    """达梦兼容性层"""
    
    def __init__(self):
        self.type_mapping = DAMENG_TYPE_MAPPING
        self.keyword_mapping = DAMENG_KEYWORD_MAPPING
        self.time_function_mapping = DAMENG_TIME_FUNCTION_MAPPING
        self.string_function_mapping = DAMENG_STRING_FUNCTION_MAPPING
    
    def convert_sql(self, sql: str, **kwargs) -> str:
        """转换 SQL 语句"""
        return adapt_sql_for_dameng(sql)
    
    def convert_type(self, mysql_type: str) -> str:
        """转换数据类型"""
        return get_dameng_type(mysql_type)
    
    def get_dialect_info(self) -> Dict[str, Any]:
        """获取达梦方言信息"""
        return {
            "name": "dameng",
            "driver": "pydmdb",
            "default_port": 5236,
            "default_user": "SYSDBA",
            "charset": "UTF-8",
            "max_varchar_length": 32767,
            "max_identifier_length": 255,
            "supports_transactions": True,
            "transaction_isolation": "READ_COMMITTED",
        }
    
    def is_connection_error(self, error: Exception) -> bool:
        """判断是否是连接错误"""
        error_str = str(error).upper()
        connection_errors = [
            "CONNECTION REFUSED",
            "CONNECTION TIMEOUT",
            "NETWORK UNREACHABLE",
            "HOST UNREACHABLE",
            "CONNECTION RESET",
        ]
        return any(err in error_str for err in connection_errors)


# 全局兼容性层实例
_dameng_compat = None


def get_compatibility_layer() -> DamengCompatibilityLayer:
    """获取达梦兼容性层单例"""
    global _dameng_compat
    if _dameng_compat is None:
        _dameng_compat = DamengCompatibilityLayer()
    return _dameng_compat
