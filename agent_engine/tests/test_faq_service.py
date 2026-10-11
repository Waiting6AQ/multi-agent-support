"""FaqService 单元测试：FAQ 落库、检索排序与阈值（PostgreSQL + pgvector）

FAQ 的向量和业务字段同存在 faqs 表里，检索是一条带余弦距离排序的 SELECT。
这些测试用离线假嵌入（不碰 DashScope），把"距离排序"和"阈值过滤"变成确定性断言。

注：连的是 .env 里 POSTGRES_DSN 指向的真实库（开发库），每个测试前后会清空 faqs 表。
没装 pytest-asyncio，用 asyncio.run 驱动（与 test_db_seed.py 一致）。
"""
import asyncio

import pytest
from sqlalchemy import delete, func, select

from core.config import settings
from core.database import dispose_engine, get_session_factory, init_database
from models.tables import Faq
from services.faq_service import FaqService
from utils.db_seed import FAQ_ENTRIES, seed_faq

DIM = settings.EMBEDDING_DIM


def _vec(*values: float) -> list[float]:
    """DIM 维向量：前几维取给定值（用来构造夹角），其余补 0"""
    v = [0.0] * DIM
    v[: len(values)] = values
    return v


class _FixedEmbeddings:
    """所有文本都返回同一条单位向量——只验证落库和幂等，不关心相似度"""

    def __init__(self, dim: int = DIM):
        self._dim = dim

    def embed_documents(self, texts):
        return [[1.0] + [0.0] * (self._dim - 1) for _ in texts]

    def embed_query(self, text):
        return [1.0] + [0.0] * (self._dim - 1)


class _TableEmbeddings:
    """按文本查表返回向量，用来精确控制检索结果的顺序和距离"""

    def __init__(self, table: dict[str, list[float]]):
        self._table = table

    def embed_documents(self, texts):
        return [self._table[t] for t in texts]

    def embed_query(self, text):
        return self._table[text]


async def _count_faq() -> int:
    async with get_session_factory()() as session:
        return await session.scalar(select(func.count()).select_from(Faq)) or 0


async def _clear_faq() -> None:
    async with get_session_factory()() as session:
        await session.execute(delete(Faq))
        await session.commit()


async def _insert(question: str, category: str, vector: list[float]) -> None:
    async with get_session_factory()() as session:
        session.add(
            Faq(
                question=question,
                answer=f"{question}的解答",
                category=category,
                embedding=vector,
            )
        )
        await session.commit()


@pytest.fixture
def prepared():
    """建表（含 pgvector 扩展）+ 清空 faqs 表，让每个测试从干净状态开始"""

    async def setup():
        await init_database()   # 幂等；同时触发 CREATE EXTENSION + Base.metadata.create_all
        await _clear_faq()

    asyncio.run(setup())
    yield

    async def teardown():
        await _clear_faq()
        await dispose_engine()

    asyncio.run(teardown())


def test_seed_faq_is_idempotent(prepared):
    async def run():
        sf = get_session_factory()
        fake = _FixedEmbeddings()
        await seed_faq(sf, fake)
        await seed_faq(sf, fake)      # 第二次启动：已有数据，必须跳过
        assert await _count_faq() == len(FAQ_ENTRIES)

    asyncio.run(run())


def test_seed_faq_rejects_wrong_dimension(prepared):
    """嵌入模型的维度和 EMBEDDING_DIM 对不上时必须抛，而不是把错维度的向量写进表"""

    async def run():
        with pytest.raises(RuntimeError, match="维度"):
            await seed_faq(get_session_factory(), _FixedEmbeddings(dim=3))
        assert await _count_faq() == 0

    asyncio.run(run())


def test_search_orders_by_distance(prepared):
    """三条 FAQ 与查询的夹角不同，结果必须按距离由近到远"""

    async def run():
        # 与查询向量 (1, 0) 的余弦相似度依次是 1.0 / 0.9 / 0.6 → 距离 0 / 0.1 / 0.4
        await _insert("近", "分类近", _vec(1.0, 0.0))
        await _insert("中", "分类中", _vec(0.9, 0.435))
        await _insert("远", "分类远", _vec(0.6, 0.8))

        embeddings = _TableEmbeddings({"查询": _vec(1.0, 0.0)})
        hits = await FaqService(get_session_factory(), embeddings=embeddings).search("查询")

        assert [h.question for h in hits] == ["近", "中", "远"]
        assert hits[0].distance < hits[1].distance < hits[2].distance

    asyncio.run(run())


def test_search_filters_by_threshold(prepared):
    """与所有 FAQ 都正交的查询（距离 1.0）必须返回空，让 skill 排查流程接手"""

    async def run():
        await _insert("近", "分类近", _vec(1.0, 0.0))
        await _insert("中", "分类中", _vec(0.6, 0.8))

        embeddings = _TableEmbeddings({"不相关的问题": _vec(0.0, 0.0, 1.0)})
        hits = await FaqService(get_session_factory(), embeddings=embeddings).search(
            "不相关的问题"
        )

        assert hits == []

    asyncio.run(run())
