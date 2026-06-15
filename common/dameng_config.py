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
达梦数据库配置管理模块

处理达梦数据库的配置、连接字符串生成和验证
"""

import os
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class DamengConfig:
    """达梦数据库配置类"""
    
    host: str = "localhost"
    port: int = 5236
    user: str = "SYSDBA"
    password: str = ""
    database: str = "rag_flow"
    charset: str = "UTF-8"
    max_connections: int = 900
    stale_timeout: int = 300
    connection_timeout: int = 30
    max_allowed_packet: int = 1073741824
    
    # 可选配置
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    echo: bool = False
    
    # 达梦特定配置
    use_unicode: bool = True
    autocommit: bool = False
    isolation_level: str = "READ_COMMITTED"
    
    # 额外参数
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_connection_string(self, driver: str = "pydmdb") -> str:
        """
        生成连接字符串
        
        Args:
            driver: 驱动名称（默认为 pydmdb）
            
        Returns:
            连接字符串
        """
        if not self.password:
            # 不包含密码
            connection_string = f"dm://{self.user}@{self.host}:{self.port}/{self.database}"
        else:
            connection_string = f"dm://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        
        # 添加字符集参数
        if self.charset:
            connection_string += f"?charset={self.charset}"
        
        return connection_string
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def validate(self) -> bool:
        """
        验证配置
        
        Returns:
            配置是否有效
        """
        if not self.host:
            logger.error("DaMeng host is required")
            return False
        
        if not (0 < self.port < 65536):
            logger.error(f"DaMeng port must be between 0 and 65536, got {self.port}")
            return False
        
        if not self.user:
            logger.error("DaMeng user is required")
            return False
        
        if not self.database:
            logger.error("DaMeng database name is required")
            return False
        
        return True
    
    @classmethod
    def from_env(cls) -> 'DamengConfig':
        """
        从环境变量创建配置
        
        Returns:
            DamengConfig 实例
        """
        return cls(
            host=os.getenv("DAMENG_HOST", "localhost"),
            port=int(os.getenv("DAMENG_PORT", 5236)),
            user=os.getenv("DAMENG_USER", "SYSDBA"),
            password=os.getenv("DAMENG_PASSWORD", ""),
            database=os.getenv("DAMENG_DB", "rag_flow"),
            charset=os.getenv("DAMENG_CHARSET", "UTF-8"),
            max_connections=int(os.getenv("DAMENG_MAX_CONNECTIONS", 900)),
            stale_timeout=int(os.getenv("DAMENG_STALE_TIMEOUT", 300)),
            connection_timeout=int(os.getenv("DAMENG_CONNECTION_TIMEOUT", 30)),
            max_allowed_packet=int(os.getenv("DAMENG_MAX_ALLOWED_PACKET", 1073741824)),
        )
    
    @classmethod
    def from_yaml(cls, config_dict: Dict[str, Any]) -> 'DamengConfig':
        """
        从 YAML 配置字典创建配置
        
        Args:
            config_dict: YAML 中的 dameng 配置字典
            
        Returns:
            DamengConfig 实例
        """
        return cls(
            host=config_dict.get("host", "localhost"),
            port=config_dict.get("port", 5236),
            user=config_dict.get("user", "SYSDBA"),
            password=config_dict.get("password", ""),
            database=config_dict.get("name", "rag_flow"),
            charset=config_dict.get("charset", "UTF-8"),
            max_connections=config_dict.get("max_connections", 900),
            stale_timeout=config_dict.get("stale_timeout", 300),
            connection_timeout=config_dict.get("connection_timeout", 30),
            max_allowed_packet=config_dict.get("max_allowed_packet", 1073741824),
        )


class DamengConnectionManager:
    """达梦数据库连接管理器"""
    
    def __init__(self, config: DamengConfig):
        """
        初始化连接管理器
        
        Args:
            config: DamengConfig 实例
        """
        self.config = config
        self._connection = None
        self._pool = None
    
    def get_connection_string(self) -> str:
        """获取连接字符串"""
        return self.config.to_connection_string()
    
    def get_connection_params(self) -> Dict[str, Any]:
        """
        获取连接参数（用于 Peewee）
        
        Returns:
            连接参数字典
        """
        return {
            "database": self.config.database,
            "user": self.config.user,
            "password": self.config.password,
            "host": self.config.host,
            "port": self.config.port,
            "charset": self.config.charset,
            "max_connections": self.config.max_connections,
            "stale_timeout": self.config.stale_timeout,
            "timeout": self.config.connection_timeout,
        }
    
    def test_connection(self) -> bool:
        """
        测试数据库连接
        
        Returns:
            连接是否成功
        """
        try:
            # 尝试导入达梦驱动
            try:
                import dmdb
            except ImportError:
                logger.warning("pydmdb driver not installed, trying fallback")
                import pymysql as dmdb
            
            # 建立测试连接
            conn = dmdb.connect(
                host=self.config.host,
                port=self.config.port,
                user=self.config.user,
                password=self.config.password,
                database=self.config.database,
                charset=self.config.charset,
                connect_timeout=self.config.connection_timeout,
            )
            
            # 执行简单查询
            cursor = conn.cursor()
            cursor.execute("SELECT SYSDATE() FROM DUAL")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            logger.info(f"DaMeng connection test successful: {result}")
            return True
            
        except Exception as e:
            logger.error(f"DaMeng connection test failed: {e}")
            return False
    
    def get_version(self) -> Optional[str]:
        """
        获取数据库版本
        
        Returns:
            数据库版本字符串
        """
        try:
            import dmdb
            conn = dmdb.connect(**self.get_connection_params())
            cursor = conn.cursor()
            cursor.execute("SELECT DB_VERSION() FROM DUAL")
            version = cursor.fetchone()[0]
            cursor.close()
            conn.close()
            return version
        except Exception as e:
            logger.error(f"Failed to get DaMeng version: {e}")
            return None


def load_dameng_config(config_source: Dict[str, Any]) -> DamengConfig:
    """
    加载达梦配置
    
    Args:
        config_source: 配置源（通常来自 service_conf.yaml）
        
    Returns:
        DamengConfig 实例
    """
    if isinstance(config_source, dict):
        return DamengConfig.from_yaml(config_source)
    else:
        return DamengConfig.from_env()
