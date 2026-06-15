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
达梦数据库 ORM 兼容性处理

提供与 Peewee ORM 的集成和兼容性处理
"""

import logging
from typing import Dict, Any, Optional, Type
from playhouse.pool import PooledDatabase

logger = logging.getLogger(__name__)


class DamengPooledDatabase(PooledDatabase):
    """达梦数据库连接池"""
    
    def __init__(self, database, *args, **kwargs):
        """
        初始化达梦连接池
        
        Args:
            database: 数据库名称
            *args: 其他位置参数
            **kwargs: 其他关键字参数
        """
        super().__init__(database, *args, **kwargs)
        self.init_commands = [
            "SET SESSION sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE'",
        ]
    
    def _state(self, state):
        """处理连接状态"""
        super()._state(state)
        # 达梦特定的初始化命令
        for cmd in self.init_commands:
            try:
                self.execute_sql(cmd)
            except Exception as e:
                logger.warning(f"Failed to execute init command '{cmd}': {e}")


class DamengDatabaseAdapter:
    """达梦数据库适配器"""
    
    def __init__(self):
        self.type_converters = {
            'TEXT': 'CLOB',
            'LONGTEXT': 'CLOB',
            'MEDIUMTEXT': 'CLOB',
            'UNSIGNED': '',
            'ZEROFILL': '',
        }
    
    def get_field_definition(self, field_type: str, **field_kwargs) -> str:
        """
        获取达梦字段定义
        
        Args:
            field_type: Peewee 字段类型
            **field_kwargs: 字段参数
            
        Returns:
            达梦 SQL 字段定义
        """
        # 转换类型
        if field_type in self.type_converters:
            field_type = self.type_converters[field_type]
        
        # 构建定义
        definition = field_type
        
        if field_kwargs.get('null'):
            definition += ' NULL'
        else:
            definition += ' NOT NULL'
        
        if 'default' in field_kwargs:
            definition += f" DEFAULT {field_kwargs['default']}"
        
        if field_kwargs.get('primary_key'):
            definition += ' PRIMARY KEY'
        
        if field_kwargs.get('unique'):
            definition += ' UNIQUE'
        
        return definition
    
    def convert_model_sql(self, sql: str) -> str:
        """
        转换 Peewee 模型 SQL
        
        Args:
            sql: Peewee 生成的 SQL
            
        Returns:
            转换后的达梦 SQL
        """
        from common.dameng_utils import adapt_sql_for_dameng
        return adapt_sql_for_dameng(sql)
    
    def on_conflict_clause(self, preserve: tuple) -> str:
        """
        生成冲突处理子句
        
        Args:
            preserve: 要保留的列元组
            
        Returns:
            达梦的冲突处理子句
        """
        # 达梦使用 MERGE INTO，在 ORM 层需要特殊处理
        logger.warning("DaMeng ON CONFLICT requires application-level handling")
        return ""


def create_dameng_database(db_config: Dict[str, Any]):
    """
    创建达梦数据库实例
    
    Args:
        db_config: 数据库配置字典
        
    Returns:
        达梦数据库实例
    """
    try:
        from playhouse.pool import PooledMySQLDatabase
        
        # 使用 MySQL 驱动连接达梦（兼容模式）
        db = PooledMySQLDatabase(
            database=db_config.get('database', 'rag_flow'),
            user=db_config.get('user', 'SYSDBA'),
            password=db_config.get('password', ''),
            host=db_config.get('host', 'localhost'),
            port=db_config.get('port', 5236),
            max_connections=db_config.get('max_connections', 900),
            stale_timeout=db_config.get('stale_timeout', 300),
            charset='utf8mb4',
        )
        
        logger.info(f"Created DaMeng database connection: {db_config.get('host')}:{db_config.get('port')}/{db_config.get('database')}")
        return db
        
    except Exception as e:
        logger.error(f"Failed to create DaMeng database: {e}")
        raise


def initialize_dameng_database(db, tables: list = None):
    """
    初始化达梦数据库
    
    Args:
        db: 数据库实例
        tables: 要创建的表列表
    """
    try:
        # 连接测试
        db.connection()
        logger.info("DaMeng database initialized successfully")
        
        # 创建表
        if tables:
            db.create_tables(tables, safe=True)
            logger.info(f"Created {len(tables)} tables in DaMeng database")
            
    except Exception as e:
        logger.error(f"Failed to initialize DaMeng database: {e}")
        raise
