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

    def __init__(self, model: str = "text-embedding-v4"):
        self.model = model

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询文本，返回一维向量"""
        rsp = TextEmbedding.call(model=self.model, input=text)
        return rsp.output["embeddings"][0]["embedding"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档文本，返回二维向量列表"""
        rsp = TextEmbedding.call(model=self.model, input=texts)
        return [emb["embedding"] for emb in rsp.output["embeddings"]]
