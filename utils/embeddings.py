"""
嵌入模型适配器

将阿里云 DashScope Embedding API 封装为 LangChain 标准接口，
使得 Chroma、检索器等 LangChain 组件可以直接调用。
"""
from typing import List
from dashscope import TextEmbedding
from langchain_core.embeddings import Embeddings


class AliyunEmbeddings(Embeddings):
    """实现 LangChain Embeddings 接口，底层调用阿里云 TextEmbedding"""

    def __init__(self, model: str = "qwen3.7-text-embedding"):
        self.model = model

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询文本，text_type="query" 生成方向性向量，优化检索匹配"""
        rsp = TextEmbedding.call(model=self.model, input=text, text_type="query")
        if rsp.output is None or not rsp.output.get("embeddings"):
            raise RuntimeError(f"Embedding API 返回为空: {rsp}")
        return rsp.output["embeddings"][0]["embedding"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档文本，text_type="document" 生成全面向量，优化被匹配效果"""
        batch_size = 20
        all_embeddings: List[List[float]] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            rsp = TextEmbedding.call(model=self.model, input=batch, text_type="document")
            if rsp.output is None or not rsp.output.get("embeddings"):
                raise RuntimeError(f"Embedding API 返回为空 (batch {i // batch_size}): {rsp}")
            all_embeddings.extend(emb["embedding"] for emb in rsp.output["embeddings"])
        return all_embeddings
