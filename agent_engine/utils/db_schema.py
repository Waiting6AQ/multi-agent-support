"""
数据库 Schema 定义

负责创建表结构（DDL），与种子数据分离。
"""
import sqlite3


def create_tables(db_path: str) -> None:
    """创建所有业务表（IF NOT EXISTS，幂等安全）"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            product TEXT NOT NULL,
            price REAL NOT NULL,
            status TEXT NOT NULL,
            shipping TEXT,
            tracking TEXT,
            estimated_delivery TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            name TEXT PRIMARY KEY,
            category TEXT NOT NULL DEFAULT '其他',
            price REAL NOT NULL,
            features TEXT,
            stock INTEGER DEFAULT 0,
            rating REAL DEFAULT 0.0
        )
    """)

    conn.commit()
    conn.close()
    print("✅ 数据库表结构初始化完成")
