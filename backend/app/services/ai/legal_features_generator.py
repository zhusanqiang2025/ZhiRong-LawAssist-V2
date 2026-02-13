# backend/app/services/ai/legal_features_generator.py
"""
AI 法律特征生成服务

利用大语言模型为合同类型生成专业的法律特征定义。
"""
import logging
import httpx
from typing import Dict, Optional
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class LegalFeaturesPrompt(BaseModel):
    """法律特征生成提示词"""
    contract_name: str
    category: str
    subcategory: Optional[str] = None


class LegalFeaturesGenerator:
    """
    AI 法律特征生成器

    使用 Qwen3 模型为合同类型生成专业的法律特征。
    """

    def __init__(self):
        # 使用硬编码配置
        self.api_url = settings.QWEN3_API_BASE
        self.api_key = settings.QWEN3_API_KEY
        self.model_name = settings.QWEN3_MODEL
        self.timeout = settings.QWEN3_TIMEOUT

        if not self.api_url or not self.api_key:
            logger.warning("[LegalFeaturesGenerator] AI 模型配置缺失，无法使用 AI 功能")

    def is_available(self) -> bool:
        """检查 AI 服务是否可用"""
        return bool(self.api_url and self.api_key)

    async def generate_legal_features(self, prompt: LegalFeaturesPrompt) -> Dict:
        """
        为指定合同类型生成法律特征

        Args:
            prompt: 包含合同名称、分类信息的提示词

        Returns:
            Dict: 生成的法律特征字典
        """
        if not self.is_available():
            raise ValueError("AI 服务不可用，请检查配置")

        # 构建提示词
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(prompt)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.api_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3,  # 降低随机性，提高稳定性
                        "max_tokens": 2000,
                        "response_format": {"type": "json_object"}  # 强制 JSON 输出
                    }
                )
                response.raise_for_status()

                result = response.json()
                content = result["choices"][0]["message"]["content"]

                # 解析 JSON 响应
                import json
                features = json.loads(content)

                # 验证并补全必要字段
                return self._validate_and_complete(features)

        except httpx.HTTPError as e:
            logger.error(f"[LegalFeaturesGenerator] HTTP 请求失败: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"[LegalFeaturesGenerator] JSON 解析失败: {e}")
            raise
        except Exception as e:
            logger.error(f"[LegalFeaturesGenerator] 生成法律特征失败: {e}")
            raise

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一位资深的合同法专家，精通中国合同法和各类合同的法律特征分析。

你的任务是为给定的合同类型生成准确、专业的法律特征定义。

请严格按照以下 JSON 格式输出：
{
  "transaction_nature": "交易性质（必须从以下选项选择：转移所有权、提供服务、许可使用、合作经营、融资借贷、劳动用工、争议解决）",
  "contract_object": "合同标的（必须从以下选项选择：货物、工程、智力成果、服务、股权、资金、劳动力、不动产、动产）",
  "stance": "起草立场（必须从以下选项选择：甲方、乙方、中立、平衡）",
  "consideration_type": "交易对价类型（必须从以下选项选择：有偿、无偿、混合）",
  "consideration_detail": "交易对价的具体说明（10字以内，如：双方协商、固定价格、按市场价格、利息形式、租金形式等）",
  "transaction_characteristics": "交易特征（简明扼要地描述该合同类型的核心法律特征，30字以内）",
  "usage_scenario": "适用场景（描述该合同类型的主要应用场景，30字以内）",
  "legal_basis": ["法律依据1", "法律依据2"]
}

注意事项：
1. 交易性质、合同标的、起草立场、交易对价类型必须严格从给定的选项中选择
2. 交易特征要抓住核心法律特征，如：占有转移+办理所有权转移登记实现交付
3. 法律依据要准确，优先引用《民法典》相关条文
4. 起草立场通常选择"平衡"，除非有明显偏向
"""

    def _build_user_prompt(self, prompt: LegalFeaturesPrompt) -> str:
        """构建用户提示词"""
        category_info = f"分类：{prompt.category}"
        if prompt.subcategory:
            category_info += f" > {prompt.subcategory}"

        return f"""请为以下合同类型生成法律特征：

合同名称：{prompt.contract_name}
{category_info}

请分析该合同类型的核心法律特征，并生成相应的特征定义。"""

    def _validate_and_complete(self, features: Dict) -> Dict:
        """验证并补全生成的法律特征"""
        # ✨ 定义有效的枚举值选项
        valid_options = {
            "transaction_nature": ["转移所有权", "提供服务", "许可使用", "合作经营", "融资借贷", "劳动用工", "争议解决"],
            "contract_object": ["货物", "工程", "智力成果", "服务", "股权", "资金", "劳动力", "不动产", "动产"],
            "stance": ["甲方", "乙方", "中立", "平衡"],
            "consideration_type": ["有偿", "无偿", "混合"]
        }

        # 必要字段的默认值
        defaults = {
            "transaction_nature": "提供服务",
            "contract_object": "服务",
            "stance": "平衡",
            "consideration_type": "有偿",
            "consideration_detail": "双方协商",
            "transaction_characteristics": "待完善",
            "usage_scenario": f"适用于{features.get('contract_name', '该合同')}",
            "legal_basis": []
        }

        # ✨ 验证并修正枚举值
        for field, valid_values in valid_options.items():
            if field in features and features[field]:
                # 如果值不在有效选项中，尝试模糊匹配或使用默认值
                if features[field] not in valid_values:
                    logger.warning(
                        f"[LegalFeaturesGenerator] {field} 值 '{features[field]}' 不在有效选项中，"
                        f"使用默认值: {defaults[field]}"
                    )
                    features[field] = defaults[field]
            else:
                # 字段缺失，使用默认值
                features[field] = defaults[field]

        # 补全其他非枚举字段
        for key, default_value in defaults.items():
            if key not in features or not features[key]:
                features[key] = default_value

        # 确保 legal_basis 是列表
        if not isinstance(features.get("legal_basis"), list):
            features["legal_basis"] = []

        return features


# 单例模式
_generator_instance: Optional[LegalFeaturesGenerator] = None


def get_legal_features_generator() -> LegalFeaturesGenerator:
    """获取法律特征生成器单例"""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = LegalFeaturesGenerator()
    return _generator_instance
