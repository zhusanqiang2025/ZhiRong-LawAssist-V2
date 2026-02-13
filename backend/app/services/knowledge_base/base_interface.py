# backend/app/services/knowledge_base/base_interface.py
"""
知识库基类接口

定义所有知识库实现必须遵循的接口规范
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class KnowledgeItem:
    """知识条目"""
    id: str                                    # 唯一标识
    title: str                                 # 标题
    content: str                               # 内容
    source: str                                # 来源知识库名称
    source_store: str = ""                     # 来源知识库标识（动态添加）
    url: Optional[str] = None                  # 原始 URL
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    relevance_score: float = 0.0               # 相关性分数（0-1）
    created_at: Optional[datetime] = None      # 创建时间
    updated_at: Optional[datetime] = None      # 更新时间

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "source": self.source,
            "source_store": self.source_store,
            "url": self.url,
            "metadata": self.metadata,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class KnowledgeSearchResult:
    """知识库搜索结果"""
    query: str                                 # 搜索查询
    items: List[KnowledgeItem] = field(default_factory=list)  # 结果列表
    total: int = 0                             # 总数
    search_intent: Optional['SearchIntent'] = None  # 搜索意图

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "query": self.query,
            "items": [item.to_dict() for item in self.items],
            "total": self.total,
            "search_intent": {
                "original_query": self.search_intent.original_query,
                "optimized_query": self.search_intent.optimized_query,
                "target_domains": self.search_intent.target_domains,
            } if self.search_intent else None,
        }


@dataclass
class SearchIntent:
    """搜索意图"""
    original_query: str                        # 原始查询
    optimized_query: str                       # 优化后的查询
    target_domains: List[str] = field(default_factory=list)  # 目标知识域
    confidence: float = 1.0                    # 置信度（0-1）


# ==================== 基类接口 ====================

class BaseKnowledgeStore(ABC):
    """
    知识库基类接口

    所有知识库实现都必须继承此类并实现抽象方法
    """

    def __init__(self, name: str, priority: int = 100):
        """
        初始化知识库

        Args:
            name: 知识库名称（唯一标识）
            priority: 优先级（数字越小优先级越高）
        """
        self.name = name
        self._priority = priority
        logger.info(f"[{self.name}] 知识库初始化完成 (优先级: {priority})")

    @abstractmethod
    async def search(
        self,
        query: str,
        domain: str = "",
        limit: int = 5,
        user_id: Optional[int] = None
    ) -> List[KnowledgeItem]:
        """
        搜索知识

        Args:
            query: 搜索查询
            domain: 法律领域（可选）
            limit: 返回结果数量
            user_id: 用户ID（可选，用于私有知识库过滤）

        Returns:
            知识条目列表
        """
        pass

    @abstractmethod
    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        """
        通过 ID 获取知识

        Args:
            item_id: 知识条目 ID

        Returns:
            知识条目，如果不存在则返回 None
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查知识库是否可用

        Returns:
            是否可用
        """
        pass

    @property
    def priority(self) -> int:
        """优先级（数字越小优先级越高）"""
        return self._priority

    async def health_check(self) -> Dict[str, Any]:
        """
        健康检查

        Returns:
            健康状态信息
        """
        return {
            "name": self.name,
            "available": self.is_available(),
            "priority": self.priority,
        }
