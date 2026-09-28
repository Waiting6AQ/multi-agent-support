"""db_seed 单元测试：种子数据的幂等性（PostgreSQL / ORM 版）

背景：启动时自动灌种子数据，必须保证「重启不重复插入」（幂等），
否则每次重启订单/产品数据都会翻倍。

注：这些测试连的是 .env 里 POSTGRES_DSN 指向的真实库（开发库）。
每个测试开始前会清空 orders / products 两张表 —— 它们是种子数据，可随时重建；
conversations 表（真实对话记录）不受影响。

没装 pytest-asyncio，用 asyncio.run 驱动（与 test_file_utils.py 一致）。
"""
import asyncio

import pytest
from sqlalchemy import delete, func, select

from core.database import dispose_engine, get_session_factory, init_database
from models.tables import Order, Product
from utils.db_seed import ORDERS, PRODUCTS, seed_orders, seed_products


async def _count(model) -> int:
    async with get_session_factory()() as session:
        return await session.scalar(select(func.count()).select_from(model)) or 0


async def _clear(model) -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(model))
        await session.commit()


@pytest.fixture
def prepared():
    """建表 + 清空业务表，让每个测试从干净状态开始"""

    async def setup():
        await init_database()          # 幂等；同时触发 Base.metadata.create_all
        await _clear(Order)
        await _clear(Product)

    asyncio.run(setup())
    yield

    async def teardown():
        await _clear(Order)
        await _clear(Product)
        await dispose_engine()

    asyncio.run(teardown())


def test_seed_orders_is_idempotent(prepared):
    async def run():
        sf = get_session_factory()
        await seed_orders(sf)
        await seed_orders(sf)          # 第二次启动：已有数据，必须跳过
        assert await _count(Order) == len(ORDERS)

    asyncio.run(run())


def test_seed_products_is_idempotent(prepared):
    async def run():
        sf = get_session_factory()
        await seed_products(sf)
        await seed_products(sf)
        assert await _count(Product) == len(PRODUCTS)

    asyncio.run(run())


def test_seeded_order_is_queryable(prepared):
    """种子数据能被 ORM 查出来，且字段类型正确（NUMERIC → Decimal）"""
    from decimal import Decimal

    async def run():
        await seed_orders(get_session_factory())
        async with get_session_factory()() as session:
            order = await session.get(Order, "ORD001")
        assert order is not None
        assert order.product               # 商品名非空
        assert order.status                # 订单状态非空
        assert isinstance(order.price, Decimal)   # NUMERIC 列读出来是 Decimal

    asyncio.run(run())


def test_seeded_product_features_is_list(prepared):
    """features 是 JSONB 列，读出来应该直接是 list（不再是 JSON 字符串）"""

    async def run():
        await seed_products(get_session_factory())
        async with get_session_factory()() as session:
            product = await session.get(Product, "智能手表 Pro")
        assert product is not None
        assert isinstance(product.features, list)
        assert "心率监测" in product.features

    asyncio.run(run())
