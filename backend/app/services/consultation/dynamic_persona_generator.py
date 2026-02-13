"""
动态人设与策略生成器
实现模型分层架构，根据任务复杂度调用不同模型，将硬编码知识迁移到知识库
"""

from typing import Dict, List, Any, Optional
import json
import logging
from sqlalchemy.orm import Session

from app.core.llm_config import get_assistant_model
from app.models.category import Category
from app.services.consultation.prompt_utils import get_category_reference_table

logger = logging.getLogger(__name__)


class DynamicPersonaGenerator:
    """动态人设与策略生成器"""
    
    def __init__(self):
        self.assistant_llm = get_assistant_model()
        
    async def generate_persona_and_strategy(
        self,
        question: str,
        db: Session,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        生成动态人设和策略

        Args:
            question: 用户问题
            db: 数据库会话
            context: 上下文信息

        Returns:
            包含 primary_type, persona_definition 和 strategic_focus 的字典
        """
        logger.info(f"[动态人设生成器] 开始生成人设和策略，问题: {question[:50]}...")

        # 【P1 优化】获取活跃法律领域列表，确保精准分类
        available_domains = self._get_available_domains(db)
        logger.info(f"[动态人设生成器] 可用法律领域: {available_domains}")

        # 获取分类参考表
        reference_table = get_category_reference_table(db)

        # 获取类别元信息
        category_meta_info = self._get_category_meta_info(db, question)

        # 【P1 优化】将可用领域列表注入到系统提示词中
        system_prompt = self._build_system_prompt(category_meta_info, available_domains)

        # 构建人类输入
        human_content = self._build_human_input(question, context, reference_table)
        
        # 调用快速模型生成人设和策略
        from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_content)
        ]
        
        try:
            response: AIMessage = await self.assistant_llm.ainvoke(messages)
            response_text = response.content
            
            logger.debug(f"[动态人设生成器] LLM响应: {response_text}")
            
            # 解析响应
            persona_strategy = self._parse_response(response_text)
            
            logger.info(f"[动态人设生成器] 生成完成，人设角色: {persona_strategy.get('specialist_role')}")
            
            return persona_strategy
            
        except Exception as e:
            logger.error(f"[动态人设生成器] 生成失败: {str(e)}")
            # 返回默认值
            return self._get_default_persona_strategy()
    
    def _build_system_prompt(self, category_meta_info: Dict[str, Any], available_domains: List[str] = None) -> str:
        """构建系统提示词"""
        # 【P1 优化】动态生成可用领域列表提示
        domains_hint = ""
        if available_domains:
            domains_list = "、".join(available_domains[:10])  # 限制显示前10个
            domains_hint = f"\n\n**重要提示**：primary_type 必须从以下可用法律领域中选择：\n{domains_list}\n如果无法精准匹配，选择最接近的领域。"

        return f"""
你是律师事务所的专业咨询系统，负责为特定法律问题生成定制化的专家人设和分析策略。

【任务】
根据用户问题生成：
1. **primary_type** - 法律领域分类（必须从可用领域中选择）
2. **specialist_role** - 专业律师角色名称
3. persona_definition - 专业的律师角色设定
4. strategic_focus - 针对性分析要点
{domains_hint}

【参考知识】
{json.dumps(category_meta_info, ensure_ascii=False, indent=2)}

【输出要求】
- primary_type 必须是具体的法律领域（如"劳动法"、"合同法"），禁止使用"法律咨询"、"法律问题"等泛化词汇
- 人设定义应包含专业背景、执业经验、专长领域
- 战略重点应包含分析角度、关注要点、注意事项
- 必须严格按JSON格式输出，不能有其他内容

【输出格式】
{{
    "primary_type": "具体法律领域（如：劳动法、合同法、侵权责任法等）",
    "specialist_role": "专业律师角色名称",
    "persona_definition": {{
        "role_title": "角色头衔",
        "professional_background": "专业背景",
        "years_of_experience": "执业年限",
        "expertise_area": "专长领域",
        "approach_style": "分析风格"
    }},
    "strategic_focus": {{
        "analysis_angle": "分析角度",
        "key_points": ["关键关注点1", "关键关注点2"],
        "risk_alerts": ["风险预警1", "风险预警2"],
        "attention_matters": ["注意事项1", "注意事项2"],
        "force_rag": "是否强制RAG检索(true/false)"
    }},
    "confidence": "置信度(0-1)",
    "urgency": "紧急程度(high/medium/low)",
    "complexity": "复杂程度(high/medium/low)"
}}
"""
    
    def _build_human_input(
        self, 
        question: str, 
        context: Optional[Dict[str, Any]], 
        reference_table: str
    ) -> str:
        """构建人类输入"""
        input_text = f"""
客户咨询问题：
{question}

法律领域快速参考表：
{reference_table}

请根据上述问题生成相应的专家人设和分析策略。
"""
        
        if context:
            input_text += f"\n\n上下文信息：\n{json.dumps(context, ensure_ascii=False)}"
            
        return input_text
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM响应"""
        # 尝试提取JSON部分
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        
        if json_match:
            json_str = json_match.group()
            try:
                parsed = json.loads(json_str)
                return parsed
            except json.JSONDecodeError as e:
                logger.error(f"[动态人设生成器] JSON解析失败: {e}")
                
        # 如果无法解析JSON，返回默认值
        logger.warning("[动态人设生成器] 无法解析JSON响应，使用默认值")
        return self._get_default_persona_strategy()
    
    def _get_default_persona_strategy(self) -> Dict[str, Any]:
        """获取默认人设和策略"""
        return {
            "specialist_role": "专业律师",
            "persona_definition": {
                "role_title": "资深执业律师",
                "professional_background": "法学硕士，具备深厚的法学理论功底和丰富的实务经验",
                "years_of_experience": "10年以上",
                "expertise_area": "综合法律咨询",
                "approach_style": "严谨务实，注重可操作性"
            },
            "strategic_focus": {
                "analysis_angle": "法律关系分析",
                "key_points": ["事实认定", "法律适用", "程序要求"],
                "risk_alerts": ["法律风险", "程序风险"],
                "attention_matters": ["时效性", "证据效力"],
                "force_rag": False
            },
            "confidence": 0.8,
            "urgency": "medium",
            "complexity": "medium"
        }
    
    def _get_category_meta_info(self, db: Session, question: str) -> Dict[str, Any]:
        """获取类别元信息"""
        # 简单的关键词匹配来确定类别
        categories = db.query(Category).all()

        # 根据问题关键词匹配最相关的类别
        matched_category = None
        max_keywords_matched = 0

        for cat in categories:
            keywords = cat.meta_info.get('keywords', []) if cat.meta_info else []
            matched_count = sum(1 for kw in keywords if kw.lower() in question.lower())

            if matched_count > max_keywords_matched:
                max_keywords_matched = matched_count
                matched_category = cat

        if matched_category:
            return {
                "category_name": matched_category.name,
                "meta_info": matched_category.meta_info or {},
                "force_rag": matched_category.meta_info.get('force_rag', False) if matched_category.meta_info else False
            }

        return {
            "category_name": "通用咨询",
            "meta_info": {},
            "force_rag": False
        }

    def _get_available_domains(self, db: Session) -> List[str]:
        """获取所有活跃的法律领域列表"""
        try:
            categories = db.query(Category).filter(
                Category.is_active == True,
                Category.parent_id == None
            ).all()
            return [cat.name for cat in categories]
        except Exception as e:
            logger.error(f"[动态人设生成器] 获取可用领域失败: {e}")
            # 返回默认领域列表
            return ["劳动法", "合同法", "侵权责任法", "公司法", "婚姻家庭法", "建设工程", "刑法", "行政法"]


# 全局实例
dynamic_persona_generator = DynamicPersonaGenerator()