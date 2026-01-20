# backend/app/services/template_feature_extractor.py
"""
合同模板法律特征自动提取服务

功能：
1. 从Word文档中提取文本内容
2. 使用 RequirementAnalyzer 分析并提取法律特征
3. 智能推荐合同分类

集成模块：
- DocumentPreprocessor: 文档内容提取
- RequirementAnalyzer: 需求分析和特征提取（基于知识图谱）
"""
import os
import logging
from typing import Dict, Optional, Tuple
from langchain_openai import ChatOpenAI

from app.services.document_preprocessor import get_preprocessor
from app.services.contract_generation.agents.requirement_analyzer import RequirementAnalyzer
from app.core.config import settings

logger = logging.getLogger(__name__)


class TemplateFeatureExtractor:
    """
    合同模板法律特征自动提取器

    工作流程：
    1. 使用DocumentPreprocessor提取Word文档文本
    2. 使用RequirementAnalyzer分析文本并提取法律特征
    3. 返回结构化的特征数据（基于知识图谱）
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.preprocessor = get_preprocessor()
        self.requirement_analyzer = RequirementAnalyzer(llm)

    def extract_from_file(
        self,
        file_path: str,
        category_hint: Optional[str] = None
    ) -> Tuple[Dict, str]:
        """
        从Word文档中自动提取法律特征

        Args:
            file_path: Word文档路径
            category_hint: 分类提示（可选，用于辅助判断）

        Returns:
            (特征字典, 提取说明)
        """
        try:
            logger.info(f"[TemplateFeatureExtractor] 开始提取文件特征: {file_path}")

            # Step 1: 提取文档文本内容
            logger.info("[TemplateFeatureExtractor] Step 1: 提取文档文本内容...")
            doc_text = self._extract_document_text(file_path)

            if not doc_text or len(doc_text.strip()) < 50:
                logger.warning("[TemplateFeatureExtractor] 文档内容过短，无法准确提取特征")
                return self._get_default_features(), "文档内容过短，使用默认特征"

            # Step 2: 使用 RequirementAnalyzer 提取特征
            logger.info("[TemplateFeatureExtractor] Step 2: 使用 RequirementAnalyzer 提取特征...")

            # 构建分析输入（使用文档前3000字符）
            analysis_input = doc_text[:3000]
            if category_hint:
                analysis_input = f"合同类型：{category_hint}\n\n{analysis_input}"

            # 调用 RequirementAnalyzer
            analysis_result = self.requirement_analyzer.analyze(analysis_input)

            # 提取法律特征
            legal_features = analysis_result.get("legal_features", {})
            key_info = analysis_result.get("key_info", {})

            # 转换为简化的特征字典（兼容旧格式）
            features = self._convert_to_v2_format(legal_features, key_info)

            reasoning = f"合同类型：{key_info.get('合同类型', '未知')}"

            logger.info(f"[TemplateFeatureExtractor] 特征提取完成: {features}")
            logger.info(f"[TemplateFeatureExtractor] 提取理由: {reasoning}")

            return features, reasoning

        except Exception as e:
            logger.error(f"[TemplateFeatureExtractor] 特征提取失败: {str(e)}", exc_info=True)
            return self._get_default_features(), f"特征提取失败: {str(e)}"

    def _extract_document_text(self, file_path: str) -> str:
        """
        提取Word文档的文本内容

        使用统一文档服务确保与其他模块一致的文档处理。

        Args:
            file_path: 文档路径

        Returns:
            提取的文本内容
        """
        try:
            # 使用统一文档服务提取文本
            from app.services.unified_document_service import get_unified_document_service
            service = get_unified_document_service()
            text = service.convert_to_markdown(file_path)

            if not text:
                logger.warning(f"[TemplateFeatureExtractor] 文档内容提取为空: {file_path}")
                return ""

            logger.info(f"[TemplateFeatureExtractor] 成功提取文本，长度: {len(text)} 字符")
            return text

        except Exception as e:
            logger.error(f"[TemplateFeatureExtractor] 文档内容提取失败: {str(e)}", exc_info=True)
            return ""

    def _convert_to_v2_format(self, legal_features: Dict, key_info: Dict) -> Dict:
        """
        将知识图谱的法律特征转换为简化的V2格式

        Args:
            legal_features: 从知识图谱获取的法律特征
            key_info: 关键信息

        Returns:
            简化的特征字典
        """
        # 如果有知识图谱特征，使用它
        if legal_features:
            transaction_nature = legal_features.get("transaction_nature", "service_delivery")
            contract_object = legal_features.get("contract_object", "ip")
            stance = legal_features.get("stance", "neutral")
        else:
            # 降级：使用默认值
            transaction_nature = "service_delivery"
            contract_object = "ip"
            stance = "neutral"

        # 复杂度根据合同类型推断
        contract_type = key_info.get("合同类型", "")
        complexity = self._infer_complexity(contract_type)

        return {
            "transaction_nature": transaction_nature,
            "contract_object": contract_object,
            "complexity": complexity,
            "stance": stance,
            "contract_type": contract_type,
        }

    def _infer_complexity(self, contract_type: str) -> str:
        """
        根据合同类型推断复杂度

        Args:
            contract_type: 合同类型

        Returns:
            复杂度级别
        """
        # 复杂合同类型
        complex_types = [
            "股权转让合同", "股权收购合同", "增资扩股协议",
            "合资经营合同", "联营合同",
            "建设工程施工合同", "EPC工程总承包合同",
        ]

        # 简单合同类型
        simple_types = [
            "借款合同", "赠与合同",
            "实习协议", "退休返聘协议",
        ]

        if any(t in contract_type for t in complex_types):
            return "complex_strategic"
        elif any(t in contract_type for t in simple_types):
            return "internal_simple"
        else:
            return "standard_commercial"

    def _get_default_features(self) -> Dict:
        """
        获取默认特征值

        当自动提取失败时使用这些默认值
        """
        return {
            "transaction_nature": "service_delivery",
            "contract_object": "ip",
            "complexity": "standard_commercial",
            "stance": "neutral",
            "contract_type": "委托合同",
        }


# 全局实例
_extractor_instance: Optional[TemplateFeatureExtractor] = None


def get_template_feature_extractor() -> TemplateFeatureExtractor:
    """
    获取TemplateFeatureExtractor单例实例

    Returns:
        TemplateFeatureExtractor实例
    """
    global _extractor_instance

    if _extractor_instance is None:
        # 初始化LLM
        llm = ChatOpenAI(
            model=settings.OPENAI_MODEL_NAME,
            temperature=0,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE
        )

        _extractor_instance = TemplateFeatureExtractor(llm)
        logger.info("[TemplateFeatureExtractor] 初始化完成")

    return _extractor_instance
