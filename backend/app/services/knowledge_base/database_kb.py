import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import SessionLocal
from app.models.knowledge_base import KnowledgeDocument
from app.models.category import Category
from .base_interface import BaseKnowledgeStore, KnowledgeItem

logger = logging.getLogger(__name__)

class DatabaseKnowledgeStore(BaseKnowledgeStore):
    """
    数据库知识库
    
    基于 PostgreSQL (PGVector) 的 RAG 知识库
    支持 category_id 范围搜索和 user_id 权限过滤
    """
    
    def __init__(self):
        super().__init__(name="企业知识库", priority=50) # Priority higher than generic web search but lower than local rules? Or adjust.
        # Actually LocalKB is priority 1. This should be priority 10?
        # Let's set to 10.
        self._priority = 10
        
    async def search(
        self,
        query: str,
        domain: str = "",
        limit: int = 5,
        user_id: Optional[int] = None
    ) -> List[KnowledgeItem]:
        """
        搜索知识库文档
        
        Args:
            query: 搜索查询 (TODO: Use vector search)
            domain: 法律领域/分类名称
            limit: 限制数量
            user_id: 当前用户ID
            
        Returns:
            KnowledgeItem 列表
        """
        db = SessionLocal()
        try:
            # 1. 确定 Category ID (如果提供了 domain)
            category_id = None
            if domain:
                # 尝试查找对应的 Category
                # 这里假设 domain 可能就是 Category.name 或者包含它
                # 简单实现：精确匹配或模糊匹配
                cat = db.query(Category).filter(Category.name.ilike(f"%{domain}%")).first()
                if cat:
                    category_id = cat.id
            
            # 2. 构建查询
            # 基础过滤：Status active
            filters = [KnowledgeDocument.status == 'active']
            
            # 权限过滤：
            # (kb_type='system') OR (kb_type='user' AND user_id=current_user_id)
            # 如果 user_id 为 None，只能查 system
            if user_id:
                filters.append(
                    or_(
                        KnowledgeDocument.kb_type == 'system',
                        and_(KnowledgeDocument.kb_type == 'user', KnowledgeDocument.user_id == user_id)
                    )
                )
            else:
                filters.append(KnowledgeDocument.kb_type == 'system')
                
            # 分类过滤
            if category_id:
                # 包含子分类? 暂时只查当前分类
                filters.append(KnowledgeDocument.category_id == category_id)
                
            # 关键词搜索 (简单文本匹配，未来应替换为 Vector Search)
            # PGVector通常使用 embedding，这里先用 content/title ILIKE 模拟
            filters.append(
                or_(
                    KnowledgeDocument.title.ilike(f"%{query}%"),
                    KnowledgeDocument.content.ilike(f"%{query}%")
                )
            )
            
            # 执行查询
            docs = db.query(KnowledgeDocument).filter(*filters).limit(limit).all()
            
            items = []
            for doc in docs:
                item = KnowledgeItem(
                    id=str(doc.id),
                    title=doc.title,
                    content=doc.content,
                    source=self.name,
                    source_store=self.name,
                    url=doc.source_url,
                    metadata={
                        "doc_id": doc.doc_id,
                        "category_id": doc.category_id,
                        "kb_type": doc.kb_type,
                        "source_type": doc.source_type
                    },
                    relevance_score=0.8, # Mock score
                    created_at=doc.created_at,
                    updated_at=doc.updated_at
                )
                items.append(item)
                
            return items
            
        except Exception as e:
            logger.error(f"[DatabaseKB] Search failed: {e}")
            return []
        finally:
            db.close()
            
    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        # TODO: Implement get by ID
        return None

    def is_available(self) -> bool:
        return True
