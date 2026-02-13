import logging
from typing import List, Optional
from .base_interface import BaseKnowledgeStore, KnowledgeItem

logger = logging.getLogger(__name__)

class WebSearchStore(BaseKnowledgeStore):
    """
    网络搜索知识库 (DuckDuckGo Wrapper)

    优先级：100 (最低优先级，作为兜底)
    """

    def __init__(self):
        super().__init__(name="全网法律检索", priority=100)
        # 【修复】延迟加载，避免启动时因网络问题失败
        self.skill = None

    def _get_skill(self):
        """延迟加载 skill，只在需要时初始化"""
        if self.skill is None:
            try:
                from app.services.legal_search.legal_search_skill import get_legal_search_skill
                self.skill = get_legal_search_skill()
            except Exception as e:
                logger.warning(f"[WebSearchStore] 无法加载搜索模块: {e}")
                self.skill = None
        return self.skill

    async def search(
        self,
        query: str,
        domain: str = "",
        limit: int = 5,
        user_id: Optional[int] = None
    ) -> List[KnowledgeItem]:
        """
        搜索网络
        """
        # 【修复】检查是否启用网络搜索
        import os
        if os.getenv("ENABLE_WEB_SEARCH", "false").lower() == "false":
            logger.info(f"[WebSearchStore] 网络搜索已禁用（环境变量 ENABLE_WEB_SEARCH=false）")
            return []

        skill = self._get_skill()
        if skill is None:
            logger.warning(f"[WebSearchStore] 搜索模块不可用")
            return []

        try:
            # 使用 Skill 搜索
            # Skill.search_laws / search_cases
            # 这里简单使用通用搜索或者特定搜索
            # 如果 domain 指向案例，搜案例；否则搜法规/综合

            search_type = "all"
            if domain and ("案例" in domain or "纠纷" in domain):
                search_type = "cases"
            elif domain and "法" in domain:
                search_type = "laws"

            response = await skill.search(query, search_type=search_type, max_results=limit)

            items = []
            for res in response.results:
                item = KnowledgeItem(
                    id=f"web_{abs(hash(res['url']))}",
                    title=res['title'],
                    content=str(res['snippet']), # Ensure string
                    source=self.name,
                    source_store=self.name,
                    url=res['url'],
                    metadata={
                        "source": res['source'],
                        "relevance": res['relevance_score']
                    },
                    relevance_score=res['relevance_score'],
                )
                items.append(item)

            return items

        except Exception as e:
            logger.warning(f"[WebSearchStore] Search failed: {e}")
            return []
            
    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        return None  # 不支持通过ID获取
        
    def is_available(self) -> bool:
        return True
