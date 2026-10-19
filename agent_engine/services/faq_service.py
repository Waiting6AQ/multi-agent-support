"""
FAQ 检索与管理服务（PostgreSQL + pgvector）

FAQ 存在 faqs 表里：question / answer / category 是普通字段，embedding 是 pgvector 向量列，
检索就是一条带距离排序的 SELECT，没有独立的向量库进程，也不用维护第二套索引。

命中判据是余弦距离阈值 settings.FAQ_MAX_DISTANCE：超过它就算没找到，退回 skill 排查流程。

管理接口（增删改查）供后台维护知识库用；改问题时必须重算向量，否则检索会对不上。
"""
import asyncio
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.config import settings
from models.faq import FaqInfo
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

    # ==================== 管理（增删改查） ====================

    async def list_all(self) -> list[FaqInfo]:
        """列出全部 FAQ（管理页用；数据量小，不分页）"""
        async with self._session_factory() as session:
            rows = (await session.scalars(select(Faq).order_by(Faq.id))).all()

        return [
            FaqInfo(id=r.id, question=r.question, answer=r.answer, category=r.category)
            for r in rows
        ]

    async def create(self, question: str, answer: str, category: str) -> int:
        """新增 FAQ，返回自增 id；问题重复返回 409"""
        # 嵌入接口是同步阻塞的，扔线程池里跑
        vector = await asyncio.to_thread(self._embeddings.embed_query, question)

        async with self._session_factory() as session:
            dup = await session.scalar(select(Faq.id).where(Faq.question == question))
            if dup is not None:
                raise HTTPException(status_code=409, detail=f"问题已存在（id={dup}）")

            faq = Faq(question=question, answer=answer, category=category, embedding=vector)
            session.add(faq)
            await session.commit()
            # expire_on_commit=False：commit 后 id 仍可读，不用再查一次
            return faq.id

    async def update(self, faq_id: int, question: str, answer: str, category: str) -> None:
        """修改 FAQ；问题变了才重算向量（只改答案/分类不用动）"""
        async with self._session_factory() as session:
            faq = await session.get(Faq, faq_id)
            if faq is None:
                raise HTTPException(status_code=404, detail=f"FAQ {faq_id} 不存在")

            if question != faq.question:
                # 换了问法就得换向量，否则用新问题检索不到这条
                dup = await session.scalar(
                    select(Faq.id).where(Faq.question == question, Faq.id != faq_id)
                )
                if dup is not None:
                    raise HTTPException(status_code=409, detail=f"问题已存在（id={dup}）")
                faq.embedding = await asyncio.to_thread(
                    self._embeddings.embed_query, question
                )

            faq.question = question
            faq.answer = answer
            faq.category = category
            await session.commit()

    async def delete(self, faq_id: int) -> None:
        """删除 FAQ；不存在返回 404"""
        async with self._session_factory() as session:
            faq = await session.get(Faq, faq_id)
            if faq is None:
                raise HTTPException(status_code=404, detail=f"FAQ {faq_id} 不存在")
            await session.delete(faq)
            await session.commit()
