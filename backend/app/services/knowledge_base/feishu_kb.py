# backend/app/services/knowledge_base/feishu_kb.py
"""
飞书知识库客户端

支持：
1. 飞书 Wiki 文档获取
2. 飞书文档搜索
3. 增量同步
4. 内容提取和清洗
"""

import logging
import httpx
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio

from .base_interface import BaseKnowledgeStore, KnowledgeItem

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class FeishuConfig:
    """飞书配置"""
    app_id: str
    app_secret: str
    wiki_space_id: str
    enabled: bool = True


@dataclass
class FeishuDocument:
    """飞书文档"""
    document_id: str
    title: str
    content: str
    url: str
    updated_at: datetime


# ==================== 飞书知识库 ====================

class FeishuKnowledgeBase(BaseKnowledgeStore):
    """
    飞书知识库

    优先级：2（仅次于本地知识库）
    """

    def __init__(self, config: Optional[FeishuConfig] = None):
        """
        初始化飞书知识库

        Args:
            config: 飞书配置（可选，如果未提供则从环境变量读取）
        """
        super().__init__(name="飞书知识库", priority=2)

        self.config = config
        self._access_token = None
        self._token_expires_at = None
        self._client: Optional[httpx.AsyncClient] = None

        # 缓存
        self._document_cache: Dict[str, FeishuDocument] = {}
        self._cache_ttl = timedelta(hours=1)

        if self.config and self.config.enabled:
            logger.info(f"[飞书知识库] 初始化完成 (app_id: {self.config.app_id})")
        else:
            logger.warning("[飞书知识库] 未配置或已禁用")

    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _get_access_token(self) -> Optional[str]:
        """
        获取访问令牌

        Returns:
            访问令牌，如果失败则返回 None
        """
        if not self.config or not self.config.enabled:
            return None

        # 检查令牌是否有效
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token

        # 获取新令牌
        try:
            client = await self._get_client()

            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.config.app_id,
                    "app_secret": self.config.app_secret
                }
            )

            data = response.json()

            if data.get("code") == 0:
                self._access_token = data.get("tenant_access_token")
                expires_in = data.get("expire", 7200)
                self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # 提前5分钟过期
                logger.info("[飞书知识库] 访问令牌获取成功")
                return self._access_token
            else:
                logger.error(f"[飞书知识库] 获取访问令牌失败: {data.get('msg')}")
                return None

        except Exception as e:
            logger.error(f"[飞书知识库] 获取访问令牌异常: {e}")
            return None

    async def search(
        self,
        query: str,
        domain: str = "",
        limit: int = 5
    ) -> List[KnowledgeItem]:
        """
        搜索知识

        Args:
            query: 搜索查询
            domain: 法律领域（可选）
            limit: 返回结果数量

        Returns:
            知识条目列表
        """
        if not self.is_available():
            logger.warning("[飞书知识库] 不可用，跳过搜索")
            return []

        try:
            # 方案1：使用飞书搜索 API
            items = await self._search_via_api(query, limit)

            # 方案2：如果搜索 API 不可用，使用本地缓存
            if not items:
                items = await self._search_in_cache(query, limit)

            return items

        except Exception as e:
            logger.error(f"[飞书知识库] 搜索失败: {e}")
            return []

    async def _search_via_api(self, query: str, limit: int) -> List[KnowledgeItem]:
        """使用飞书搜索 API"""
        access_token = await self._get_access_token()
        if not access_token:
            return []

        try:
            client = await self._get_client()

            # 使用飞书搜索 API（搜索文档）
            response = await client.post(
                "https://open.feishu.cn/open-apis/search/v1/message",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "query": query,
                    "search_type": "message",
                    "count": limit
                }
            )

            data = response.json()

            if data.get("code") == 0:
                items = []
                for item in data.get("data", {}).get("items", [])[:limit]:
                    # 提取文档信息
                    doc_id = item.get("doc_id") or item.get("message_id")
                    title = item.get("title") or item.get("snippet", "")[:50]
                    content = item.get("snippet", "")
                    url = item.get("url", "")

                    knowledge_item = KnowledgeItem(
                        id=f"feishu_{doc_id}",
                        title=title,
                        content=content,
                        source=self.name,
                        url=url,
                        metadata={
                            "doc_id": doc_id,
                            "source_type": "feishu",
                        },
                        relevance_score=0.7,
                    )
                    items.append(knowledge_item)

                logger.info(f"[飞书知识库] 搜索 API 返回 {len(items)} 条结果")
                return items

            else:
                logger.warning(f"[飞书知识库] 搜索 API 失败: {data.get('msg')}")
                return []

        except Exception as e:
            logger.error(f"[飞书知识库] 搜索 API 异常: {e}")
            return []

    async def _search_in_cache(self, query: str, limit: int) -> List[KnowledgeItem]:
        """在本地缓存中搜索"""
        query_lower = query.lower()

        items = []
        for doc_id, doc in self._document_cache.items():
            # 检查缓存是否过期
            if datetime.now() - doc.updated_at > self._cache_ttl:
                continue

            # 简单的关键词匹配
            if query_lower in doc.title.lower() or query_lower in doc.content.lower():
                item = KnowledgeItem(
                    id=f"feishu_{doc_id}",
                    title=doc.title,
                    content=doc.content[:500],  # 限制长度
                    source=self.name,
                    url=doc.url,
                    metadata={
                        "doc_id": doc_id,
                        "source_type": "feishu",
                        "cached": True,
                    },
                    relevance_score=0.6,
                )
                items.append(item)

            if len(items) >= limit:
                break

        logger.info(f"[飞书知识库] 缓存搜索返回 {len(items)} 条结果")
        return items

    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        """
        通过 ID 获取知识

        Args:
            item_id: 知识条目 ID

        Returns:
            知识条目，如果不存在则返回 None
        """
        # 解析 ID 格式：feishu_{doc_id}
        parts = item_id.split("_")
        if len(parts) < 2 or parts[0] != "feishu":
            return None

        doc_id = parts[1]

        # 检查缓存
        if doc_id in self._document_cache:
            doc = self._document_cache[doc_id]
            return KnowledgeItem(
                id=item_id,
                title=doc.title,
                content=doc.content,
                source=self.name,
                url=doc.url,
                metadata={
                    "doc_id": doc_id,
                    "source_type": "feishu",
                },
            )

        # 从飞书获取
        if not self.is_available():
            return None

        try:
            doc = await self._fetch_document(doc_id)
            if doc:
                return KnowledgeItem(
                    id=item_id,
                    title=doc.title,
                    content=doc.content,
                    source=self.name,
                    url=doc.url,
                    metadata={
                        "doc_id": doc_id,
                        "source_type": "feishu",
                    },
                )
        except Exception as e:
            logger.error(f"[飞书知识库] 获取文档失败: {e}")

        return None

    async def _fetch_document(self, doc_id: str) -> Optional[FeishuDocument]:
        """获取飞书文档内容"""
        access_token = await self._get_access_token()
        if not access_token:
            return None

        try:
            client = await self._get_client()

            # 获取文档内容
            response = await client.get(
                f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                }
            )

            data = response.json()

            if data.get("code") == 0:
                # 提取文本内容
                content = self._extract_text_from_blocks(data.get("data", {}))

                doc = FeishuDocument(
                    document_id=doc_id,
                    title=data.get("data", {}).get("title", "未命名文档"),
                    content=content,
                    url=f"https://feishu.cn/docx/{doc_id}",
                    updated_at=datetime.now()
                )

                # 缓存文档
                self._document_cache[doc_id] = doc

                return doc
            else:
                logger.warning(f"[飞书知识库] 获取文档失败: {data.get('msg')}")
                return None

        except Exception as e:
            logger.error(f"[飞书知识库] 获取文档异常: {e}")
            return None

    def _extract_text_from_blocks(self, data: Dict[str, Any]) -> str:
        """从文档块中提取文本"""
        # 简化实现，实际需要递归处理所有块
        blocks = data.get("blocks", {})
        text_parts = []

        for block_id, block in blocks.items():
            block_type = block.get("type", "")
            if block_type == "text":
                text_elements = block.get("text", {}).get("elements", [])
                for element in text_elements:
                    if element.get("type") == "text_run":
                        text_parts.append(element.get("text_run", {}).get("content", ""))

        return "\n".join(text_parts)

    def is_available(self) -> bool:
        """
        检查知识库是否可用

        Returns:
            是否可用
        """
        return self.config is not None and self.config.enabled

    async def sync_documents(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, int]:
        """
        增量同步文档

        Args:
            since: 上次同步时间（None 表示全量同步）

        Returns:
            同步统计：{"created": X, "updated": Y, "deleted": Z}
        """
        if not self.is_available():
            logger.warning("[飞书知识库] 不可用，跳过同步")
            return {"created": 0, "updated": 0, "deleted": 0, "failed": 0}

        access_token = await self._get_access_token()
        if not access_token:
            return {"created": 0, "updated": 0, "deleted": 0, "failed": 0}

        stats = {"created": 0, "updated": 0, "deleted": 0, "failed": 0}

        try:
            client = await self._get_client()

            # 获取 Wiki 空间下的文档列表
            response = await client.get(
                f"https://open.feishu.cn/open-apis/wiki/v2/spaces/{self.config.wiki_space_id}/nodes",
                headers={
                    "Authorization": f"Bearer {access_token}",
                },
                params={
                    "page_size": 50,
                }
            )

            data = response.json()

            if data.get("code") == 0:
                items = data.get("data", {}).get("items", [])

                for item in items:
                    try:
                        obj_type = item.get("obj_type")
                        node_token = item.get("node_token")

                        # 只处理文档类型
                        if obj_type == "docx" or obj_type == "doc":
                            # 检查是否需要更新
                            if node_token in self._document_cache:
                                stats["updated"] += 1
                            else:
                                stats["created"] += 1

                            # 获取文档内容
                            doc = await self._fetch_document(node_token)
                            if doc:
                                self._document_cache[node_token] = doc

                    except Exception as e:
                        logger.error(f"[飞书知识库] 同步文档 {item.get('node_token')} 失败: {e}")
                        stats["failed"] += 1

                logger.info(f"[飞书知识库] 同步完成: {stats}")
                return stats

            else:
                logger.error(f"[飞书知识库] 获取文档列表失败: {data.get('msg')}")
                return stats

        except Exception as e:
            logger.error(f"[飞书知识库] 同步异常: {e}")
            return stats

    async def close(self):
        """关闭连接"""
        if self._client:
            await self._client.aclose()
            self._client = None


# ==================== 工厂函数 ====================

def create_feishu_kb_from_config(config: Dict[str, Any]) -> FeishuKnowledgeBase:
    """
    从配置字典创建飞书知识库

    Args:
        config: 配置字典，包含 app_id, app_secret, wiki_space_id, enabled

    Returns:
        飞书知识库实例
    """
    feishu_config = FeishuConfig(
        app_id=config.get("app_id", ""),
        app_secret=config.get("app_secret", ""),
        wiki_space_id=config.get("wiki_space_id", ""),
        enabled=config.get("enabled", True)
    )

    return FeishuKnowledgeBase(config=feishu_config)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import asyncio

    async def test_feishu_kb():
        """测试飞书知识库"""
        # 测试配置（需要替换为实际的凭证）
        config = FeishuConfig(
            app_id="cli_xxxxxxxxxxxxx",
            app_secret="xxxxxxxxxxxxxxxxxxxx",
            wiki_space_id="xxxxxxxxxxxxxxxxxxxx",
            enabled=True
        )

        kb = FeishuKnowledgeBase(config=config)

        # 测试1：搜索
        print("=" * 80)
        print("测试1：搜索")
        print("=" * 80)
        items = await kb.search("民法典", limit=3)
        print(f"找到 {len(items)} 条结果")
        for item in items:
            print(f"- {item.title}")
            print(f"  {item.content[:80]}...")
            print()

        # 测试2：健康检查
        print()
        print("=" * 80)
        print("测试2：健康检查")
        print("=" * 80)
        health = await kb.health_check()
        print(f"可用: {health['available']}")

        await kb.close()

    # asyncio.run(test_feishu_kb())
