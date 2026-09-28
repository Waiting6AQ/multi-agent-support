"""
SQLAlchemy ORM 模型（业务表）

注意：LangGraph 的 checkpoint 表不在这里。它由 AsyncPostgresSaver 自己创建
（checkpoints / checkpoint_blobs / checkpoint_writes / checkpoint_migrations），
结构和迁移都由框架管理，不参与 ORM 映射。
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Float, Index, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""


class Conversation(Base):
    """对话摘要（列表页用；完整消息在 LangGraph checkpoint 里）"""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # TIMESTAMPTZ 而非 TEXT：
    # ① 旧实现存裸 ISO 字符串（无时区），跨时区会静默错序，且 JS 的 new Date() 会当本地时间解析
    # ② server_default=NOW() 让时间由数据库生成，不依赖应用容器的时区设置
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # 列表页按 updated_at 倒序。单列排序不需要 DESC 索引——
    # PostgreSQL 的 btree 索引可以反向扫描，两种写法执行计划相同
    __table_args__ = (Index("conversations_updated_at_idx", "updated_at"),)


class Order(Base):
    """订单（Agent 工具查询用）"""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    product: Mapped[str] = mapped_column(Text, nullable=False)
    # 金额用 NUMERIC 而不是 REAL：浮点存钱会有精度误差，NUMERIC 是精确十进制
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    shipping: Mapped[str | None] = mapped_column(Text)
    tracking: Mapped[str | None] = mapped_column(Text)
    estimated_delivery: Mapped[str | None] = mapped_column(Text)

    # track_shipping 工具按物流单号查
    __table_args__ = (Index("orders_tracking_idx", "tracking"),)


class Product(Base):
    """产品（Agent 工具查询用）"""

    __tablename__ = "products"

    name: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text, nullable=False, server_default="其他")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    # 原来存的是 JSON 字符串（代码里 json.loads 解析），换 JSONB 后读出来直接是 list，
    # 且能在数据库侧按内容查询/建 GIN 索引
    features: Mapped[list | None] = mapped_column(JSONB)
    stock: Mapped[int] = mapped_column(Integer, server_default="0")
    # 评分是统计值不是金额，用 Float 即可
    rating: Mapped[float] = mapped_column(Float, server_default="0.0")

    # get_recommendations 按 品类 + 价格 过滤后按评分排序
    __table_args__ = (Index("products_category_price_idx", "category", "price"),)
