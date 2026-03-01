"""
SQLite缓存管理

使用SQLite缓存市场数据和模型评分，减少API调用次数。
"""

import sqlite3
import json
import logging
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from pathlib import Path

from ..config_short_swing import CACHE_CONFIG

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器"""

    def __init__(self, db_path: str = CACHE_CONFIG["db_path"]):
        """
        初始化缓存管理器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path

        # 确保目录存在
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        logger.info(f"CacheManager initialized with db: {db_path}")

    def _init_db(self) -> None:
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 创建缓存表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_category
                ON cache(category)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_expires_at
                ON cache(expires_at)
            """)

            conn.commit()

    def get(self, key: str, category: str = "default") -> Optional[Any]:
        """
        获取缓存数据

        Args:
            key: 缓存键
            category: 缓存分类（market_data, model_score, stock_info等）

        Returns:
            缓存的数据，如果不存在或已过期则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT value, expires_at
                FROM cache
                WHERE key = ? AND category = ?
            """, (key, category))

            row = cursor.fetchone()

            if not row:
                logger.debug(f"Cache miss: {category}/{key}")
                return None

            value_json, expires_at = row

            # 检查是否过期
            if datetime.fromisoformat(expires_at) < datetime.now():
                logger.debug(f"Cache expired: {category}/{key}")
                self.delete(key, category)
                return None

            logger.debug(f"Cache hit: {category}/{key}")
            return json.loads(value_json)

    def set(
        self,
        key: str,
        value: Any,
        category: str = "default",
        ttl: Optional[int] = None
    ) -> None:
        """
        设置缓存数据

        Args:
            key: 缓存键
            value: 要缓存的数据（需可JSON序列化）
            category: 缓存分类
            ttl: 生存时间（秒），如果为None则使用配置中的默认值
        """
        if ttl is None:
            ttl = CACHE_CONFIG["ttl"].get(category, 60)

        expires_at = datetime.now() + timedelta(seconds=ttl)
        value_json = json.dumps(value, ensure_ascii=False)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO cache (key, value, category, expires_at)
                VALUES (?, ?, ?, ?)
            """, (key, value_json, category, expires_at.isoformat()))

            conn.commit()

        logger.debug(f"Cache set: {category}/{key} (TTL={ttl}s)")

    def delete(self, key: str, category: str = "default") -> None:
        """
        删除缓存数据

        Args:
            key: 缓存键
            category: 缓存分类
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM cache
                WHERE key = ? AND category = ?
            """, (key, category))

            conn.commit()

        logger.debug(f"Cache deleted: {category}/{key}")

    def clear_category(self, category: str) -> int:
        """
        清空指定分类的所有缓存

        Args:
            category: 缓存分类

        Returns:
            删除的记录数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM cache
                WHERE category = ?
            """, (category,))

            deleted_count = cursor.rowcount
            conn.commit()

        logger.info(f"Cleared {deleted_count} cache entries in category: {category}")
        return deleted_count

    def clear_expired(self) -> int:
        """
        清理所有过期缓存

        Returns:
            删除的记录数
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM cache
                WHERE expires_at < ?
            """, (datetime.now().isoformat(),))

            deleted_count = cursor.rowcount
            conn.commit()

        logger.info(f"Cleared {deleted_count} expired cache entries")
        return deleted_count

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计数据
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # 总记录数
            cursor.execute("SELECT COUNT(*) FROM cache")
            total_count = cursor.fetchone()[0]

            # 过期记录数
            cursor.execute("""
                SELECT COUNT(*) FROM cache
                WHERE expires_at < ?
            """, (datetime.now().isoformat(),))
            expired_count = cursor.fetchone()[0]

            # 各分类记录数
            cursor.execute("""
                SELECT category, COUNT(*)
                FROM cache
                GROUP BY category
            """)
            category_counts = dict(cursor.fetchall())

        return {
            "total": total_count,
            "expired": expired_count,
            "valid": total_count - expired_count,
            "by_category": category_counts,
        }


# 全局缓存实例
_cache_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    """获取全局缓存实例（单例模式）"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = CacheManager()
    return _cache_instance
