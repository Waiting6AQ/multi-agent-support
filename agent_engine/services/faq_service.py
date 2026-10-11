"""
FAQ 检索服务（PostgreSQL + pgvector）

FAQ 存在 faqs 表里：question / answer / category 是普通字段，embedding 是 pgvector 向量列，
检索就是一条带距离排序的 SELECT，没有独立的向量库进程，也不用维护第二套索引。

命中判据是余弦距离阈值 settings.FAQ_MAX_DISTANCE：超过它就算没找到，退回 skill 排查流程。
"""
import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.config import settings
from models.tables import Faq
from utils.embeddings import AliyunEmbeddings


@dataclass(frozen=True)
class FaqHit:
    """一条 FAQ 命中结果

    distance 是余弦距离（0 = 完全相同），检索本身不用它，留着是为了校准备阈值时有据可依。
    """

    question: str
    answer: str
    category: str
    distance: float


class FaqService:
    """FAQ 向量检索"""

    def __init__(self, session_factory: async_sessionmaker, embeddings=None):
        self._session_factory = session_factory
        self._embeddings = embeddings or AliyunEmbeddings(
            model=settings.EMBEDDING_MODEL_NAME
        )

    async def search(self, query: str) -> list[FaqHit]:
        """按余弦距离检索 FAQ，超过阈值的丢掉；没有命中返回空列表"""
        # DashScope 的 SDK 是同步阻塞的，扔线程池里跑，别占住事件循环
        qvec = await asyncio.to_thread(self._embeddings.embed_query, query)

        # 同一个距离表达式同时用于过滤和排序
        distance = Faq.embedding.cosine_distance(qvec)
        stmt = (
            select(Faq, distance.label("distance"))
            .where(distance <= settings.FAQ_MAX_DISTANCE)
            .order_by(distance)
            .limit(settings.FAQ_TOP_K)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(stmt)).all()

        return [
            FaqHit(
                question=faq.question,
                answer=faq.answer,
                category=faq.category,
                distance=float(dist),
            )
            for faq, dist in rows
        ]
