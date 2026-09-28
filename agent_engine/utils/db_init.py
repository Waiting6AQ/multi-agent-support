"""
数据库初始化入口

启动时执行，按顺序灌数据：
  1. db_seed.seed_faq      — FAQ → ChromaDB
  2. db_seed.seed_orders   — 订单模拟数据 → PostgreSQL
  3. db_seed.seed_products — 产品模拟数据 → PostgreSQL

注：建表不在这里 —— 表结构由 models/tables.py 的 ORM 模型定义，
由 core/database.py 的 init_database() 用 Base.metadata.create_all 建出来。
"""
from sqlalchemy.ext.asyncio import async_sessionmaker

from utils.db_seed import seed_faq, seed_orders, seed_products


async def seed_all(
    session_factory: async_sessionmaker,
    chroma_persist_dir: str,
    embeddings,
) -> None:
    """启动时统一执行种子数据初始化"""
    print("🔧 正在初始化种子数据...")
    seed_faq(chroma_persist_dir, embeddings)
    await seed_orders(session_factory)
    await seed_products(session_factory)
    print("✅ 种子数据初始化全部完成")
