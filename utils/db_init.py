"""
数据库初始化入口

启动时执行，按顺序先建表、再灌数据：
  1. db_schema.create_tables   — DDL（表结构）
  2. db_seed.seed_faq          — FAQ → ChromaDB
  3. db_seed.seed_orders       — 订单模拟数据 → SQLite
  4. db_seed.seed_products      — 产品模拟数据 → SQLite
"""
from utils.db_schema import create_tables
from utils.db_seed import seed_faq, seed_orders, seed_products


def seed_all(db_path: str, chroma_persist_dir: str, embeddings) -> None:
    """启动时统一执行数据库初始化"""
    print("🔧 正在初始化数据库...")
    create_tables(db_path)
    seed_faq(chroma_persist_dir, embeddings)
    seed_orders(db_path)
    seed_products(db_path)
    print("✅ 数据库初始化全部完成")
