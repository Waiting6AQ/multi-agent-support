"""db_seed / db_schema 单元测试：建表与种子数据的幂等性

背景：启动时自动灌种子数据，必须保证「重启不重复插入」（幂等），
否则每次重启订单/产品数据都会翻倍。
"""
import sqlite3

from utils.db_schema import create_tables
from utils.db_seed import ORDERS, PRODUCTS, seed_orders, seed_products


def count_rows(db_path: str, table: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def table_names(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def test_create_tables_creates_orders_and_products(tmp_path):
    db = str(tmp_path / "app.db")

    create_tables(db)

    assert {"orders", "products"} <= table_names(db)


def test_seed_orders_is_idempotent(tmp_path):
    db = str(tmp_path / "app.db")
    create_tables(db)

    seed_orders(db)
    seed_orders(db)          # 第二次启动：已有数据，必须跳过

    assert count_rows(db, "orders") == len(ORDERS)


def test_seed_products_is_idempotent(tmp_path):
    db = str(tmp_path / "app.db")
    create_tables(db)

    seed_products(db)
    seed_products(db)

    assert count_rows(db, "products") == len(PRODUCTS)


def test_seeded_order_is_queryable(tmp_path):
    db = str(tmp_path / "app.db")
    create_tables(db)
    seed_orders(db)

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM orders WHERE id = ?", ("ORD001",)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["product"]          # 商品名非空
    assert row["status"]           # 订单状态非空
