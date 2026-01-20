# backend/app/services/legal_search_skill.py
"""
法律检索 Skill - 可复用的法律信息检索工具

功能：
1. 使用 DuckDuckGo 搜索公开的法律信息
2. 搜索法律法规和司法解释
3. 搜索相关案例和裁判文书
4. 支持多模块复用（法律咨询、合同生成、风险分析等）

依赖：
- duckduckgo-search (已在 requirements.txt 中)
"""

import logging
import time
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from dataclasses import dataclass
from functools import wraps

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class SearchResult:
    """搜索结果"""
    title: str                           # 标题
    url: str                             # URL
    snippet: str                          # 摘要
    source: str                          # 来源网站
    relevance_score: float               # 相关性分数（0-1）


class LegalSearchRequest(BaseModel):
    """法律检索请求"""
    query: str = Field(description="检索查询")
    search_type: Literal["laws", "cases", "general", "all"] = Field(
        default="all",
        description="检索类型：laws=法规，cases=案例，general=通用搜索，all=全部"
    )
    max_results: int = Field(default=5, description="返回结果数量")


class LegalSearchResponse(BaseModel):
    """法律检索响应"""
    query: str = Field(description="检索查询")
    results: List[Dict[str, Any]] = Field(description="检索结果列表")
    total_found: int = Field(description="找到的结果总数")
    summary: str = Field(description="检索结果摘要")


# ==================== 法律检索 Skill ====================

def retry_on_ratelimit(max_retries=3, delay=5):
    """
    重试装饰器，处理限流错误

    Args:
        max_retries: 最大重试次数
        delay: 基础延迟时间（秒）
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_str = str(e)
                    # 检查是否为限流错误
                    if 'Ratelimit' in error_str or '202' in error_str or '429' in error_str:
                        if attempt < max_retries - 1:
                            wait_time = delay * (attempt + 1)  # 递增延迟
                            logger.warning(f"[法律检索] 遇到限流错误，等待 {wait_time} 秒后重试 ({attempt+1}/{max_retries})")
                            time.sleep(wait_time)
                        else:
                            logger.error(f"[法律检索] 达到最大重试次数 ({max_retries})，放弃搜索")
                            raise
                    else:
                        # 其他错误直接抛出
                        raise
        return wrapper
    return decorator


class LegalSearchSkill:
    """
    法律检索 Skill

    使用 DuckDuckGo 搜索公开的法律信息和案例
    """

    def __init__(self):
        """初始化检索 Skill"""
        # 延迟导入 DuckDuckGo
        self._ddgs = None

        # 法律网站白名单
        self.trusted_sources = [
            "npc.gov.cn",            # 全国人大
            "gov.cn",                # 政府网站
            "court.gov.cn",          # 最高人民法院
            "chinacourt.org",        # 中国法院网
            "wenshu.court.gov.cn",   # 裁判文书网
            "12348.gov.cn",          # 法律服务网
            "iolaw.org.cn",          # 中国法院网
        ]

        logger.info("[法律检索Skill] 初始化完成")

    @property
    def ddgs(self):
        """延迟初始化 DuckDuckGo 搜索器（修复版）"""
        if self._ddgs is None:
            try:
                from duckduckgo_search import DDGS
                # 新版本初始化方式，使用 timeout 参数
                self._ddgs = DDGS(timeout=20)
                logger.info("[法律检索Skill] DuckDuckGo 初始化成功（timeout=20s）")
            except ImportError:
                logger.error("[法律检索Skill] DuckDuckGo 未安装，请运行: pip install duckduckgo-search")
                raise ImportError("duckduckgo-search 未安装")
            except Exception as e:
                logger.error(f"[法律检索Skill] DuckDuckGo 初始化失败: {e}")
                raise
        return self._ddgs

    @retry_on_ratelimit(max_retries=3, delay=5)
    async def search(
        self,
        query: str,
        search_type: str = "all",
        max_results: int = 5
    ) -> LegalSearchResponse:
        """
        执行法律检索

        Args:
            query: 检索查询
            search_type: 检索类型（laws/cases/general/all）
            max_results: 最大结果数

        Returns:
            检索响应
        """
        logger.info(f"[法律检索] 开始检索: query='{query}', type={search_type}")

        # 1. 构建增强的搜索查询
        enhanced_query = self._build_search_query(query, search_type)

        # 2. 执行搜索
        try:
            raw_results = self._duckduckgo_search(enhanced_query, max_results)
        except Exception as e:
            logger.error(f"[法律检索] 搜索失败: {e}")
            return self._empty_response(query)

        # 3. 过滤和排序
        filtered_results = self._filter_and_rank(raw_results, query)

        # 4. 限制数量
        filtered_results = filtered_results[:max_results]

        # 5. 转换为字典格式
        results_dict = [
            {
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source,
                "relevance_score": r.relevance_score
            }
            for r in filtered_results
        ]

        # 6. 生成摘要
        summary = self._generate_summary(query, filtered_results)

        logger.info(f"[法律检索] 检索完成: 找到 {len(filtered_results)} 条结果")

        return LegalSearchResponse(
            query=query,
            results=results_dict,
            total_found=len(filtered_results),
            summary=summary
        )

    def _build_search_query(self, query: str, search_type: str) -> str:
        """
        构建增强的搜索查询

        Args:
            query: 原始查询
            search_type: 搜索类型

        Returns:
            增强后的查询
        """
        # 添加法律相关关键词
        keywords = []

        if search_type in ["laws", "all"]:
            keywords.extend(["法规", "法律", "条"])

        if search_type in ["cases", "all"]:
            keywords.extend(["案例", "裁判", "判决"])

        if keywords:
            # 在查询中添加关键词
            keyword_str = " ".join(keywords[:2])  # 限制关键词数量
            return f"{query} {keyword_str}"
        else:
            return query

    def _duckduckgo_search(self, query: str, max_results: int) -> List[SearchResult]:
        """
        使用 DuckDuckGo 搜索

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            搜索结果列表
        """
        results = []

        try:
            # 使用 DuckDuckGo 搜索
            search_results = self.ddgs.text(
                query,
                max_results=max_results * 2  # 多获取一些，用于后续过滤
            )

            for result in search_results:
                results.append(SearchResult(
                    title=result.get("title", ""),
                    url=result.get("link", ""),
                    snippet=result.get("body", ""),
                    source=self._extract_source(result.get("link", "")),
                    relevance_score=0.5  # 默认分数
                ))

        except Exception as e:
            logger.error(f"[法律检索] DuckDuckGo 搜索失败: {e}")

        return results

    def _extract_source(self, url: str) -> str:
        """
        从 URL 提取来源网站

        Args:
            url: URL

        Returns:
            来源网站
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            source = parsed.netloc.replace('www.', '')
            return source
        except Exception:
            return "unknown"

    def _filter_and_rank(self, results: List[SearchResult], query: str) -> List[SearchResult]:
        """
        过滤和排序搜索结果

        Args:
            results: 原始搜索结果
            query: 搜索查询

        Returns:
            过滤和排序后的结果
        """
        filtered = []

        for result in results:
            # 1. 过滤非法律网站
            if not self._is_legal_source(result.source):
                continue

            # 2. 计算相关性分数
            relevance = self._calculate_relevance(result, query)
            result.relevance_score = relevance

            # 3. 过滤低相关性结果
            if relevance >= 0.3:
                filtered.append(result)

        # 按相关性排序
        filtered.sort(key=lambda x: x.relevance_score, reverse=True)
        return filtered

    def _is_legal_source(self, source: str) -> bool:
        """
        判断是否为可信的法律网站

        Args:
            source: 来源网站

        Returns:
            是否可信
        """
        # 检查白名单
        for trusted in self.trusted_sources:
            if trusted in source:
                return True

        # 检查法律相关关键词
        legal_keywords = [
            "court", "gov", "law", "justice", "npc", "procurement"
        ]
        return any(keyword in source.lower() for keyword in legal_keywords)

    def _calculate_relevance(self, result: SearchResult, query: str) -> float:
        """
        计算相关性分数

        Args:
            result: 搜索结果
            query: 搜索查询

        Returns:
            相关性分数（0-1）
        """
        score = 0.0

        # 1. 标题匹配
        query_lower = query.lower()
        title_lower = result.title.lower()

        if query_lower in title_lower:
            score += 0.5

        # 2. URL 可信度
        for trusted in self.trusted_sources:
            if trusted in result.source:
                score += 0.2
                break

        # 3. 关键词匹配
        keywords = query_lower.split()
        for keyword in keywords:
            if keyword in title_lower:
                score += 0.1

        return min(score, 1.0)

    def _generate_summary(self, query: str, results: List[SearchResult]) -> str:
        """
        生成搜索结果摘要

        Args:
            query: 搜索查询
            results: 搜索结果

        Returns:
            摘要文本
        """
        if not results:
            return f"未找到与「{query}」相关的内容。"

        # 统计来源
        sources = set(r.source for r in results)

        return f"找到 {len(results)} 条相关内容（来源：{', '.join(list(sources)[:3])}）"

    def _empty_response(self, query: str) -> LegalSearchResponse:
        """返回空响应"""
        return LegalSearchResponse(
            query=query,
            results=[],
            total_found=0,
            summary=f"未找到与「{query}」相关的内容。"
        )

    async def search_laws(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索法律法规

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            法规列表
        """
        response = await self.search(query, search_type="laws", max_results=max_results)
        return response.results

    async def search_cases(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        搜索相关案例

        Args:
            query: 搜索查询
            max_results: 最大结果数

        Returns:
            案例列表
        """
        response = await self.search(query, search_type="cases", max_results=max_results)
        return response.results


# ==================== 单例 ====================

_search_skill_instance: Optional[LegalSearchSkill] = None


def get_legal_search_skill() -> LegalSearchSkill:
    """获取法律检索 Skill 单例"""
    global _search_skill_instance
    if _search_skill_instance is None:
        _search_skill_instance = LegalSearchSkill()
        logger.info("[法律检索Skill] 创建单例实例")
    return _search_skill_instance


# ==================== LangGraph 节点封装 ====================

async def legal_search_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph 节点：法律检索

    输入：
    - state["question"]: 用户问题
    - state["classification_result"]: 分类结果（可选）

    输出：
    - state["search_results"]: 检索结果
    - state["relevant_laws"]: 相关法规
    - state["similar_cases"]: 类似案例
    """
    logger.info("[检索节点] 开始检索相关法律信息...")

    question = state.get("question", "")
    classification = state.get("classification_result", {})

    # 获取检索 Skill
    skill = get_legal_search_skill()

    # 并行检索法规和案例
    import asyncio

    laws_task = skill.search_laws(question, max_results=3)
    cases_task = skill.search_cases(question, max_results=3)

    laws, cases = await asyncio.gather(laws_task, cases_task)

    # 更新状态
    state["search_results"] = {
        "laws": laws,
        "cases": cases
    }
    state["relevant_laws"] = [law["title"] for law in laws]
    state["similar_cases"] = [case["title"] for case in cases]

    logger.info(f"[检索节点] 检索完成: {len(laws)}条法规, {len(cases)}条案例")

    return state


# ==================== 工具函数 ====================

def format_search_results_for_llm(search_results: Dict[str, Any]) -> str:
    """
    格式化搜索结果，供 LLM 使用

    Args:
        search_results: 搜索结果

    Returns:
        格式化的文本
    """
    parts = []

    laws = search_results.get("laws", [])
    if laws:
        parts.append("【相关法律法规】")
        for i, law in enumerate(laws[:5], 1):
            parts.append(f"{i}. {law['title']}")
            if law.get('snippet'):
                parts.append(f"   {law['snippet'][:100]}...")
        parts.append("")

    cases = search_results.get("cases", [])
    if cases:
        parts.append("【相关案例】")
        for i, case in enumerate(cases[:3], 1):
            parts.append(f"{i}. {case['title']}")
            if case.get('snippet'):
                parts.append(f"   {case['snippet'][:100]}...")
        parts.append("")

    return "\n".join(parts)


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import asyncio

    async def test_search():
        """测试法律检索功能"""
        skill = get_legal_search_skill()

        # 测试1：搜索法规
        print("=" * 60)
        print("测试1：搜索劳动法相关法规")
        print("=" * 60)
        laws = await skill.search_laws("劳动合同解除赔偿", max_results=3)
        for law in laws:
            print(f"- {law['title']}")
            print(f"  来源: {law['source']}")
            print()

        # 测试2：搜索案例
        print("=" * 60)
        print("测试2：搜索合同纠纷案例")
        print("=" * 60)
        cases = await skill.search_cases("违约责任认定", max_results=3)
        for case in cases:
            print(f"- {case['title']}")
            print(f"  来源: {case['source']}")
            print()

        # 测试3：综合搜索
        print("=" * 60)
        print("测试3：综合搜索")
        print("=" * 60)
        response = await skill.search(
            query="公司设立流程",
            search_type="all",
            max_results=5
        )
        print(f"摘要: {response.summary}")

    asyncio.run(test_search())
