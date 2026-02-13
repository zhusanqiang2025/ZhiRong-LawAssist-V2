# backend/app/services/knowledge_base/local_legal_kb.py
"""
本地法律知识库

存储常用的现行法律条文，作为在线搜索的备用方案

功能：
1. 存储常用的现行法律条文
2. 支持关键词搜索
3. 格式化输出供 LLM 使用
4. 作为在线搜索失败时的备用方案
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from .base_interface import BaseKnowledgeStore, KnowledgeItem, KnowledgeSearchResult

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class LegalArticle:
    """法律条文"""
    law_name: str           # 法律名称
    article_number: str     # 条文编号
    content: str            # 条文内容
    keywords: List[str]     # 关键词（用于搜索匹配）


# ==================== 本地法律知识库 ====================

class LocalLegalKnowledgeBase(BaseKnowledgeStore):
    """
    本地法律知识库

    优先级：1（最高优先级）
    """

    def __init__(self):
        """初始化知识库"""
        super().__init__(name="本地法律知识库", priority=1)
        self.articles: Dict[str, List[LegalArticle]] = {}
        self._load_common_laws()
        logger.info(f"[本地法律知识库] 初始化完成，已加载 {sum(len(v) for v in self.articles.values())} 条法律条文")

    def _load_common_laws(self):
        """加载常用法律条文"""
        # ==================== 民法典合同编 ====================
        self.articles["合同法"] = [
            LegalArticle(
                law_name="《中华人民共和国民法典》合同编",
                article_number="第577条",
                content="当事人一方不履行合同义务或者履行合同义务不符合约定的，应当承担继续履行、采取补救措施或者赔偿损失等违约责任。",
                keywords=["违约", "违约责任", "不履行合同", "合同纠纷", "违反合同"]
            ),
            LegalArticle(
                law_name="《中华人民共和国民法典》合同编",
                article_number="第509条",
                content="当事人应当按照约定全面履行自己的义务。当事人应当遵循诚信原则，根据合同的性质、目的和交易习惯履行通知、协助、保密等义务。",
                keywords=["履行义务", "全面履行", "诚信原则", "合同义务"]
            ),
            LegalArticle(
                law_name="《中华人民共和国民法典》合同编",
                article_number="第563条",
                content="有下列情形之一的，当事人可以解除合同：（一）因不可抗力致使不能实现合同目的；（二）在履行期限届满前，当事人一方明确表示或者以自己的行为表明不履行主要债务；（三）当事人一方迟延履行主要债务，经催告后在合理期限内仍未履行；（四）当事人一方迟延履行债务或者有其他违约行为致使不能实现合同目的；（五）法律规定的其他情形。",
                keywords=["解除合同", "合同解除", "法定解除", "终止合同"]
            ),
            LegalArticle(
                law_name="《中华人民共和国民法典》合同编",
                article_number="第585条",
                content="当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。约定的违约金低于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以增加；约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。",
                keywords=["违约金", "赔偿", "损失赔偿", "违约金调整"]
            ),
        ]

        # ==================== 劳动争议调解仲裁法 ====================
        self.articles["劳动法"] = [
            LegalArticle(
                law_name="《中华人民共和国劳动争议调解仲裁法》",
                article_number="第2条",
                content="中华人民共和国境内的用人单位与劳动者发生的下列劳动争议，适用本法：（一）因确认劳动关系发生的争议；（二）因订立、履行、变更、解除和终止劳动合同发生的争议；（三）因除名、辞退和辞职、离职发生的争议；（四）因工作时间、休息休假、社会保险、福利、培训以及劳动保护发生的争议；（五）因劳动报酬、工伤医疗费、经济补偿或者赔偿金等发生的争议；（六）法律、法规规定的其他劳动争议。",
                keywords=["劳动争议", "仲裁", "劳动仲裁", "劳动纠纷"]
            ),
            LegalArticle(
                law_name="《中华人民共和国劳动争议调解仲裁法》",
                article_number="第27条",
                content="仲裁庭处理劳动争议案件，应当自劳动争议仲裁委员会受理仲裁申请之日起四十五日内结案。案情复杂需要延期的，经劳动争议仲裁委员会主任批准，可以延期并书面通知当事人，但是延长期限不得超过十五日。逾期未作出仲裁裁决的，当事人可以就该劳动争议事项向人民法院提起诉讼。",
                keywords=["仲裁期限", "仲裁时效", "诉讼", "审理期限"]
            ),
            LegalArticle(
                law_name="《中华人民共和国劳动争议调解仲裁法》",
                article_number="第5条",
                content="发生劳动争议，当事人不愿协商、协商不成或者达成和解协议后不履行的，可以向调解组织申请调解；不愿调解、调解不成或者达成调解协议后不履行的，可以向劳动争议仲裁委员会申请仲裁；对仲裁裁决不服的，除本法另有规定的外，可以向人民法院提起诉讼。",
                keywords=["协商", "调解", "仲裁", "诉讼", "劳动争议处理程序"]
            ),
        ]

        # ==================== 公司法 ====================
        self.articles["公司法"] = [
            LegalArticle(
                law_name="《中华人民共和国公司法》",
                article_number="第3条",
                content="公司是企业法人，有独立的法人财产，享有法人财产权。公司以其全部财产对公司的债务承担责任。",
                keywords=["公司", "法人", "独立财产", "债务承担责任", "有限责任"]
            ),
            LegalArticle(
                law_name="《中华人民共和国公司法》",
                article_number="第4条",
                content="有限责任公司的股东以其认缴的出资额为限对公司承担责任；股份有限公司的股东以其认购的股份为限对公司承担责任。",
                keywords=["股东", "出资额", "股份", "股东责任", "有限责任"]
            ),
        ]

        # ==================== 破产法 ====================
        self.articles["破产法"] = [
            LegalArticle(
                law_name="《中华人民共和国企业破产法》",
                article_number="第2条",
                content="企业法人不能清偿到期债务，并且资产不足以清偿全部债务或者明显缺乏清偿能力的，依照本法规定清理债务。",
                keywords=["破产", "清算", "资不抵债", "不能清偿到期债务", "破产原因"]
            ),
            LegalArticle(
                law_name="《中华人民共和国企业破产法》",
                article_number="第7条",
                content="债务人有本法第二条规定的情形，可以向人民法院提出重整、和解或者破产清算申请。债务人不能清偿到期债务，债权人可以向人民法院提出对债务人进行重整或者破产清算的申请。",
                keywords=["破产申请", "重整", "和解", "破产清算", "债权人申请"]
            ),
        ]

        # ==================== 民事诉讼法 ====================
        self.articles["民事诉讼法"] = [
            LegalArticle(
                law_name="《中华人民共和国民事诉讼法》",
                article_number="第239条",
                content="申请执行的期间为二年。申请执行时效的中止、中断，适用法律有关诉讼时效中止、中断的规定。",
                keywords=["执行", "申请执行", "执行时效", "执行期限", "申请执行期间"]
            ),
            LegalArticle(
                law_name="《中华人民共和国民事诉讼法》",
                article_number="第243条",
                content="发生法律效力的民事判决、裁定，以及刑事判决、裁定中的财产部分，由第一审人民法院或者与第一审人民法院同级的被执行的财产所在地人民法院执行。法律规定由人民法院执行的其他法律文书，由被执行人住所地或者被执行的财产所在地人民法院执行。",
                keywords=["执行管辖", "执行法院", "管辖法院", "执行地"]
            ),
        ]

        # ==================== 合伙企业法 ====================
        self.articles["合伙企业法"] = [
            LegalArticle(
                law_name="《中华人民共和国合伙企业法》",
                article_number="第2条",
                content="本法所称合伙企业，是指依照本法在中国境内设立的由各合伙人订立合伙协议，共同出资、合伙经营、共享收益、共担风险，并对合伙企业债务承担无限连带责任的营利性组织。",
                keywords=["合伙企业", "合伙协议", "无限连带责任", "合伙人"]
            ),
        ]

        logger.info(f"[本地法律知识库] 已加载 {sum(len(v) for v in self.articles.values())} 条法律条文")

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

        Returns:
            知识条目列表
        """
        results = []
        query_lower = query.lower()

        # 如果指定了法律领域，优先搜索该领域的条文
        if domain:
            for law_domain, articles in self.articles.items():
                if law_domain in domain or domain in law_domain:
                    for article in articles:
                        # 检查关键词匹配
                        for keyword in article.keywords:
                            if keyword in query_lower:
                                item = KnowledgeItem(
                                    id=f"local_{law_domain}_{article.article_number}",
                                    title=f"{article.law_name} {article.article_number}",
                                    content=article.content,
                                    source=self.name,
                                    metadata={
                                        "law_name": article.law_name,
                                        "article_number": article.article_number,
                                        "keywords": article.keywords,
                                        "domain": law_domain,
                                    },
                                    relevance_score=0.8,
                                )
                                results.append(item)
                                break

        # 如果结果不足，搜索所有领域
        if len(results) < limit:
            for law_domain, articles in self.articles.items():
                for article in articles:
                    # 检查是否已添加
                    if any(r.metadata.get("article_number") == article.article_number for r in results):
                        continue

                    # 检查关键词匹配
                    for keyword in article.keywords:
                        if keyword in query_lower:
                            item = KnowledgeItem(
                                id=f"local_{law_domain}_{article.article_number}",
                                title=f"{article.law_name} {article.article_number}",
                                content=article.content,
                                source=self.name,
                                metadata={
                                    "law_name": article.law_name,
                                    "article_number": article.article_number,
                                    "keywords": article.keywords,
                                    "domain": law_domain,
                                },
                                relevance_score=0.7,
                            )
                            results.append(item)
                            break

        return results[:limit]

    async def get_by_id(self, item_id: str) -> Optional[KnowledgeItem]:
        """
        通过 ID 获取知识

        Args:
            item_id: 知识条目 ID

        Returns:
            知识条目，如果不存在则返回 None
        """
        # 解析 ID 格式：local_{domain}_{article_number}
        parts = item_id.split("_")
        if len(parts) < 3 or parts[0] != "local":
            return None

        domain = parts[1]
        article_number = parts[2]

        # 查找对应条文
        if domain in self.articles:
            for article in self.articles[domain]:
                if article.article_number == article_number:
                    return KnowledgeItem(
                        id=item_id,
                        title=f"{article.law_name} {article.article_number}",
                        content=article.content,
                        source=self.name,
                        metadata={
                            "law_name": article.law_name,
                            "article_number": article.article_number,
                            "keywords": article.keywords,
                            "domain": domain,
                        },
                    )

        return None

    def is_available(self) -> bool:
        """
        检查知识库是否可用

        Returns:
            始终返回 True（本地知识库始终可用）
        """
        return True

    def format_for_llm(self, articles: List[LegalArticle]) -> str:
        """
        格式化条文供 LLM 使用

        Args:
            articles: 条文列表

        Returns:
            格式化的文本
        """
        if not articles:
            return ""

        parts = ["【相关法律条文】"]
        for article in articles:
            parts.append(f"- {article.law_name} {article.article_number}")
            parts.append(f"  {article.content}")
            parts.append("")

        return "\n".join(parts)


# ==================== 单例 ====================

_kb_instance: Optional[LocalLegalKnowledgeBase] = None


def get_local_legal_kb() -> LocalLegalKnowledgeBase:
    """获取本地法律知识库单例"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = LocalLegalKnowledgeBase()
        logger.info("[本地法律知识库] 创建单例实例")
    return _kb_instance


# ==================== 测试代码 ====================

if __name__ == "__main__":
    import asyncio

    async def test_local_kb():
        """测试本地知识库功能"""
        kb = get_local_legal_kb()

        # 测试1：搜索违约相关条文
        print("=" * 80)
        print("测试1：搜索违约相关条文")
        print("=" * 80)
        items = await kb.search("合同违约怎么办", "合同法", limit=3)
        print(f"找到 {len(items)} 条相关条文")
        for item in items:
            print(f"- {item.title}")
            print(f"  {item.content[:100]}...")
            print()

        # 测试2：搜索劳动争议相关条文
        print()
        print("=" * 80)
        print("测试2：搜索劳动争议相关条文")
        print("=" * 80)
        items = await kb.search("公司不给我发工资", "劳动法", limit=3)
        print(f"找到 {len(items)} 条相关条文")
        for item in items:
            print(f"- {item.title}")
            print(f"  {item.content[:100]}...")
            print()

    asyncio.run(test_local_kb())
