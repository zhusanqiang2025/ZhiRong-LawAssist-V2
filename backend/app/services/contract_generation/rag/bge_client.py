# backend/app/services/contract_generation/rag/bge_client.py
"""
BGE 服务客户端

封装公司内部部署的 BGE-M3 嵌入模型和 BGE-Reranker-v2-m3 重排序模型的 API 调用。

API 文档:
- Embedding: POST http://115.190.43.141:11434/api/embed (Ollama)
- Reranking: POST http://115.190.43.141:9997/v1/rerank
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入结果"""
    embedding: List[float]  # 向量（维度 1024 for BGE-M3）
    model: str
    tokens_used: Optional[int] = None


@dataclass
class RerankResult:
    """重排序结果"""
    index: int  # 原始文档索引
    document: str  # 文档内容
    relevance_score: float  # 相关性分数 (0-1)
    text: Optional[str] = None  # 匹配的文本片段


class BGEClient:
    """
    BGE 服务客户端类

    封装嵌入和重排序功能，支持同步和异步调用。
    """

    def __init__(
        self,
        embedding_api_url: Optional[str] = None,
        reranker_api_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: int = 30,
    ):
        """
        初始化 BGE 客户端

        Args:
            embedding_api_url: 嵌入 API 地址，默认从配置读取
            reranker_api_url: 重排序 API 地址，默认从配置读取
            model_name: 模型名称，默认 bge-m3
            timeout: 请求超时时间（秒）
        """
        self.embedding_api_url = embedding_api_url or settings.BGE_EMBEDDING_API_URL
        self.reranker_api_url = reranker_api_url or settings.BGE_RERANKER_API_URL
        self.model_name = model_name or settings.BGE_MODEL_NAME
        self.timeout = timeout

        # 创建 HTTP 客户端
        self._client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取异步 HTTP 客户端（懒加载）"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
        return self._client

    @property
    def sync_client(self) -> httpx.Client:
        """获取同步 HTTP 客户端（懒加载）"""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
            )
        return self._sync_client

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    # ==================== Embedding API ====================

    def _prepare_embedding_payload(self, text: str, model: Optional[str] = None) -> Dict[str, Any]:
        """
        准备 Embedding API 请求负载

        Ollama /api/embed 格式:
        {
            "model": "bge-m3",
            "input": "要嵌入的文本"
        }
        """
        return {
            "model": model or self.model_name,
            "input": text
        }

    def _parse_embedding_response(self, response_data: Dict[str, Any]) -> EmbeddingResult:
        """
        解析 Embedding API 响应

        实际 API 响应格式（Ollama）:
        {
            "model": "bge-m3",
            "embeddings": [[0.1, 0.2, ...]],  # 嵌入向量数组（复数形式）
            "total_duration": 2012207844,
            "load_duration": 1277164423
        }

        兼容格式（标准 Ollama）:
        {
            "embedding": [0.1, 0.2, ...],  # 单个嵌入向量
            "model": "bge-m3",
            "prompt_eval_count": 10
        }
        """
        # 支持两种格式：embeddings（复数，数组）或 embedding（单数，向量）
        if "embeddings" in response_data:
            embeddings = response_data["embeddings"]
            if isinstance(embeddings, list) and len(embeddings) > 0:
                embedding = embeddings[0]  # 取第一个向量
            else:
                raise ValueError(f"Invalid embeddings format in response")
        elif "embedding" in response_data:
            embedding = response_data["embedding"]
        else:
            raise ValueError(f"Invalid embedding response: missing 'embedding' or 'embeddings' field")

        # 验证向量维度
        if len(embedding) != settings.BGE_EMBEDDING_DIM:
            logger.warning(
                f"Embedding dimension mismatch: expected {settings.BGE_EMBEDDING_DIM}, "
                f"got {len(embedding)}"
            )

        return EmbeddingResult(
            embedding=embedding,
            model=response_data.get("model", self.model_name),
            tokens_used=response_data.get("prompt_eval_count")
        )

    async def embed_async(self, text: str, model: Optional[str] = None) -> EmbeddingResult:
        """
        异步嵌入单个文本

        Args:
            text: 要嵌入的文本
            model: 模型名称，默认使用初始化时的模型

        Returns:
            EmbeddingResult: 包含嵌入向量和元数据

        Raises:
            httpx.HTTPError: API 请求失败
            ValueError: 响应格式错误
        """
        payload = self._prepare_embedding_payload(text, model)

        logger.debug(f"Calling BGE embedding API: {self.embedding_api_url}")
        logger.debug(f"Request payload keys: {list(payload.keys())}")

        response = await self.client.post(
            self.embedding_api_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        response_data = response.json()
        return self._parse_embedding_response(response_data)

    def embed(self, text: str, model: Optional[str] = None) -> EmbeddingResult:
        """
        同步嵌入单个文本

        Args:
            text: 要嵌入的文本
            model: 模型名称

        Returns:
            EmbeddingResult: 包含嵌入向量和元数据
        """
        payload = self._prepare_embedding_payload(text, model)

        logger.debug(f"Calling BGE embedding API (sync): {self.embedding_api_url}")

        response = self.sync_client.post(
            self.embedding_api_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        response_data = response.json()
        return self._parse_embedding_response(response_data)

    async def embed_batch_async(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> List[EmbeddingResult]:
        """
        异步批量嵌入多个文本

        Args:
            texts: 文本列表
            model: 模型名称

        Returns:
            List[EmbeddingResult]: 嵌入结果列表
        """
        # 并发请求所有文本
        tasks = [self.embed_async(text, model) for text in texts]
        return await asyncio.gather(*tasks)

    def embed_batch(self, texts: List[str], model: Optional[str] = None) -> List[EmbeddingResult]:
        """
        同步批量嵌入多个文本

        Args:
            texts: 文本列表
            model: 模型名称

        Returns:
            List[EmbeddingResult]: 嵌入结果列表
        """
        return [self.embed(text, model) for text in texts]

    # ==================== Reranking API ====================

    def _prepare_rerank_payload(
        self,
        query: str,
        documents: List[str],
        model: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        准备 Rerank API 请求负载

        BGE-Reranker v2 格式:
        {
            "model": "bge-reranker-v2-m3",
            "query": "查询文本",
            "documents": ["文档1", "文档2", ...],
            "top_n": 5  // 可选，返回前 N 个结果
        }
        """
        payload = {
            "model": model or "bge-reranker-v2-m3",
            "query": query,
            "documents": documents
        }

        if top_n is not None:
            payload["top_n"] = top_n

        return payload

    def _parse_rerank_response(self, response_data: Dict[str, Any]) -> List[RerankResult]:
        """
        解析 Rerank API 响应

        BGE-Reranker v2 响应格式:
        {
            "model": "bge-reranker-v2-m3",
            "results": [
                {
                    "index": 0,
                    "document": "文档内容",
                    "relevance_score": 0.95,
                    "text": "匹配的片段"
                },
                ...
            ]
        }
        """
        if "results" not in response_data:
            raise ValueError(f"Invalid rerank response: missing 'results' field")

        results = []
        for item in response_data["results"]:
            results.append(RerankResult(
                index=item["index"],
                document=item["document"],
                relevance_score=item["relevance_score"],
                text=item.get("text")
            ))

        # 按相关性分数降序排序
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        return results

    async def rerank_async(
        self,
        query: str,
        documents: List[str],
        model: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> List[RerankResult]:
        """
        异步重排序文档列表

        Args:
            query: 用户查询
            documents: 候选文档列表
            model: 模型名称，默认 bge-reranker-v2-m3
            top_n: 返回前 N 个结果，None 表示返回全部

        Returns:
            List[RerankResult]: 按相关性排序的结果
        """
        if not documents:
            return []

        payload = self._prepare_rerank_payload(query, documents, model, top_n)

        logger.debug(f"Calling BGE reranker API: {self.reranker_api_url}")
        logger.debug(f"Reranking {len(documents)} documents")

        response = await self.client.post(
            self.reranker_api_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        response_data = response.json()
        return self._parse_rerank_response(response_data)

    def rerank(
        self,
        query: str,
        documents: List[str],
        model: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> List[RerankResult]:
        """
        同步重排序文档列表

        Args:
            query: 用户查询
            documents: 候选文档列表
            model: 模型名称
            top_n: 返回前 N 个结果

        Returns:
            List[RerankResult]: 按相关性排序的结果
        """
        if not documents:
            return []

        payload = self._prepare_rerank_payload(query, documents, model, top_n)

        logger.debug(f"Calling BGE reranker API (sync): {self.reranker_api_url}")

        response = self.sync_client.post(
            self.reranker_api_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        response_data = response.json()
        return self._parse_rerank_response(response_data)

    # ==================== 工具方法 ====================

    async def health_check(self) -> Dict[str, bool]:
        """
        检查 BGE 服务健康状态

        Returns:
            Dict[str, bool]: {"embedding": True/False, "reranker": True/False}
        """
        health_status = {
            "embedding": False,
            "reranker": False
        }

        # 检查 Embedding API
        try:
            result = await self.embed_async("健康检查", self.model_name)
            health_status["embedding"] = len(result.embedding) > 0
            logger.info(f"BGE Embedding API health check: OK (dimension={len(result.embedding)})")
        except Exception as e:
            logger.error(f"BGE Embedding API health check: FAILED - {e}")

        # 检查 Reranker API
        try:
            result = await self.rerank_async(
                query="测试查询",
                documents=["测试文档1", "测试文档2"],
                top_n=1
            )
            health_status["reranker"] = len(result) > 0
            logger.info(f"BGE Reranker API health check: OK (results={len(result)})")
        except Exception as e:
            logger.error(f"BGE Reranker API health check: FAILED - {e}")

        return health_status


# ==================== 单例模式 ====================

_bge_client_instance: Optional[BGEClient] = None


def get_bge_client() -> BGEClient:
    """
    获取 BGE 客户端单例

    Returns:
        BGEClient: BGE 服务客户端实例
    """
    global _bge_client_instance
    if _bge_client_instance is None:
        _bge_client_instance = BGEClient()
    return _bge_client_instance
