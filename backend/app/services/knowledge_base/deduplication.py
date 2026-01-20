# backend/app/services/knowledge_base/deduplication.py
"""
知识库去重和优先级管理服务

处理系统知识库和用户知识库的重复内容问题
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from difflib import SequenceMatcher
from dataclasses import dataclass, field
import re

from .base_interface import KnowledgeItem

logger = logging.getLogger(__name__)


@dataclass
class DuplicateInfo:
    """重复信息"""
    is_duplicate: bool  # 是否重复
    similarity: float  # 相似度（0-1）
    original_item: Optional[KnowledgeItem] = None  # 原始条目（系统知识库）
    user_item: Optional[KnowledgeItem] = None  # 用户条目
    source: str = "none"  # 重复来源：system, user, none
    recommendation: str = ""  # 建议文本
    diff_sections: List[str] = field(default_factory=list)  # 差异部分


class KnowledgeDeduplicator:
    """
    知识库去重服务

    功能：
    1. 检测用户上传内容与系统知识库的重复
    2. 在搜索结果中标记重复内容
    3. 按优先级返回结果（系统知识库优先）
    """

    # 相似度阈值
    SIMILARITY_THRESHOLD = 0.85  # 高相似度阈值（判定为重复）
    SIMILARITY_WARNING = 0.70  # 警告阈值（提示用户）

    def __init__(self):
        """初始化去重服务"""
        # 系统知识库内容指纹（缓存）
        self._system_fingerprints: Dict[str, str] = {}
        self._load_system_fingerprints()

    def _load_system_fingerprints(self):
        """加载系统知识库指纹"""
        try:
            from .local_legal_kb import get_local_legal_kb
            kb = get_local_legal_kb()

            # 为每个条文生成指纹
            for law_name, articles in kb.articles.items():
                for article in articles:
                    # article 是 LegalArticle 对象
                    content = article.content
                    title = f"{article.law_name} {article.article_number}"

                    # 简化内容（去除空格、标点）
                    simplified_content = self._simplify_text(content)

                    self._system_fingerprints[title] = simplified_content

            logger.info(f"[知识库去重] 已加载 {len(self._system_fingerprints)} 条系统知识库指纹")
        except Exception as e:
            logger.warning(f"[知识库去重] 加载系统知识库指纹失败: {e}")
            import traceback
            traceback.print_exc()

    def _simplify_text(self, text: str) -> str:
        """
        简化文本用于比较

        去除：
        - 空格、换行
        - 标点符号
        - 大小写差异
        """
        # 去除标点符号和空格
        text = re.sub(r'[^\w]', '', text)
        # 转小写
        text = text.lower()
        return text

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度

        使用多种方法综合判断：
        1. 标题相似度（权重 0.6）
        2. 内容相似度（权重 0.4）

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            相似度（0-1）
        """
        # 使用 SequenceMatcher 计算相似度
        return SequenceMatcher(None, text1, text2).ratio()

    def calculate_content_similarity(self, content1: str, content2: str) -> float:
        """
        计算内容相似度（更精确的方法）

        使用简化后的文本进行比较
        """
        sim1 = self._simplify_text(content1)
        sim2 = self._simplify_text(content2)

        # 计算相似度
        if not sim1 or not sim2:
            return 0.0

        return SequenceMatcher(None, sim1, sim2).ratio()

    def check_duplicate_on_upload(
        self,
        title: str,
        content: str,
        category: Optional[str] = None
    ) -> DuplicateInfo:
        """
        用户上传内容时检查是否与系统知识库重复

        Args:
            title: 文档标题
            content: 文档内容
            category: 分类（可选，用于缩小搜索范围）

        Returns:
            重复信息
        """
        max_similarity = 0.0
        most_similar_title = None
        most_similar_content = None

        # 简化输入内容
        simplified_input = self._simplify_text(content)

        # 遍历系统知识库指纹
        for sys_title, sys_content in self._system_fingerprints.items():
            # 计算标题相似度
            title_sim = self.calculate_similarity(
                self._simplify_text(title),
                self._simplify_text(sys_title)
            )

            # 计算内容相似度
            content_sim = SequenceMatcher(None, simplified_input, sys_content).ratio()

            # 综合相似度（标题权重更高）
            combined_sim = title_sim * 0.6 + content_sim * 0.4

            if combined_sim > max_similarity:
                max_similarity = combined_sim
                most_similar_title = sys_title
                most_similar_content = sys_content

        # 判断是否重复
        is_duplicate = max_similarity >= self.SIMILARITY_THRESHOLD

        # 生成建议
        recommendation = self._get_recommendation(max_similarity)

        # 创建虚拟的原始条目
        original_item = None
        if most_similar_title:
            original_item = KnowledgeItem(
                id=f"system_{hash(most_similar_title)}",
                title=most_similar_title,
                content=most_similar_content or "",
                source="系统知识库",
                source_store="系统知识库",
                metadata={
                    'kb_type': 'system',
                    'is_duplicate_target': True
                },
                relevance_score=max_similarity
            )

        return DuplicateInfo(
            is_duplicate=is_duplicate,
            similarity=max_similarity,
            original_item=original_item,
            user_item=None,
            source="system" if is_duplicate else "none",
            recommendation=recommendation
        )

    def deduplicate_search_results(
        self,
        all_items: List[KnowledgeItem],
        user_id: Optional[int] = None
    ) -> Tuple[List[KnowledgeItem], List[Dict[str, Any]]]:
        """
        去重搜索结果

        规则：
        1. 系统知识库优先级高于用户知识库
        2. 如果用户有定制版本，优先使用用户的
        3. 标记重复内容

        Args:
            all_items: 所有搜索结果（系统+用户）
            user_id: 当前用户ID

        Returns:
            (去重后的结果列表, 重复信息列表)
        """
        # 分离系统和用户条目
        system_items = []
        user_items = []

        for item in all_items:
            # 从 metadata 中获取 kb_type
            kb_type = item.metadata.get('kb_type', 'user')

            if kb_type == 'system':
                system_items.append(item)
            else:
                # 检查是否是当前用户的条目
                item_user_id = item.metadata.get('user_id')
                if item_user_id == user_id:
                    user_items.append(item)

        # 去重：对于每个系统条目，检查用户是否有类似内容
        final_items = []
        duplicate_info = []
        processed_user_items = set()

        for sys_item in system_items:
            # 添加系统条目
            final_items.append(sys_item)

            # 检查用户是否有类似内容
            for user_item in user_items:
                if id(user_item) in processed_user_items:
                    continue

                similarity = self.calculate_content_similarity(
                    sys_item.content,
                    user_item.content
                )

                if similarity >= self.SIMILARITY_WARNING:
                    # 发现重复或类似内容
                    duplicate_info.append({
                        'system_item': sys_item,
                        'user_item': user_item,
                        'similarity': similarity,
                        'is_duplicate': similarity >= self.SIMILARITY_THRESHOLD,
                        'recommendation': self._get_recommendation(similarity)
                    })
                    processed_user_items.add(id(user_item))

                    # 如果是高度重复，且用户有定制，替换为用户版本
                    if similarity >= self.SIMILARITY_THRESHOLD:
                        # 检查用户版本是否有额外注释或修改
                        user_extra = user_item.metadata.get('extra_data', {})
                        if user_extra.get('has_user_notes'):
                            # 用户有定制，使用用户版本
                            final_items[-1] = user_item
                            # 标记为定制版
                            user_item.metadata['is_custom_version'] = True

        # 添加无重复的用户条目
        for user_item in user_items:
            is_duplicate = any(
                dup['user_item'] == user_item
                for dup in duplicate_info
            )
            if not is_duplicate:
                final_items.append(user_item)

        return final_items, duplicate_info

    def _get_recommendation(self, similarity: float) -> str:
        """
        根据相似度给出建议

        Args:
            similarity: 相似度

        Returns:
            建议文本
        """
        if similarity >= self.SIMILARITY_THRESHOLD:
            return "该内容与系统知识库高度重复，建议直接使用系统版本"
        elif similarity >= self.SIMILARITY_WARNING:
            return "该内容与系统知识库较为相似，请确认是否需要保留"
        else:
            return "该内容为独立内容"

    def highlight_differences(self, text1: str, text2: str) -> List[str]:
        """
        高亮显示两个文本的差异

        Args:
            text1: 文本1（系统版本）
            text2: 文本2（用户版本）

        Returns:
            差异部分列表
        """
        # 简单实现：按段落对比
        paragraphs1 = text1.split('\n')
        paragraphs2 = text2.split('\n')

        differences = []

        for i, (p1, p2) in enumerate(zip(paragraphs1, paragraphs2)):
            if p1 != p2:
                differences.append(f"段落{i+1}:\n  系统: {p1}\n  用户: {p2}")

        return differences


# ==================== 全局实例 ====================

_deduplicator: Optional[KnowledgeDeduplicator] = None


def get_deduplicator() -> KnowledgeDeduplicator:
    """获取去重服务实例"""
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = KnowledgeDeduplicator()
    return _deduplicator
