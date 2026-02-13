import httpx
import json
import re
from typing import Dict, Any, List, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class DeepseekService:
    """Deepseek API服务类，用于智能对话功能"""

    def __init__(self):
        self.api_url = settings.DEEPSEEK_API_URL
        self.api_key = settings.DEEPSEEK_API_KEY
        self.model = settings.DEEPSEEK_MODEL
        self.temperature = settings.DEEPSEEK_TEMPERATURE
        self.max_tokens = settings.DEEPSEEK_MAX_TOKENS
        self.timeout = settings.DEEPSEEK_TIMEOUT

        logger.info(f"LLM服务初始化完成 - API_URL: {self.api_url}, Model: {self.model}")
        logger.info("Action button functionality enabled")

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> str:
        """
        调用Deepseek API进行对话完成
        """
        # 构建请求头
        headers = {
            "Content-Type": "application/json",
        }

        # 如果有API密钥，添加到请求头
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # 构建请求payload
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": stream
        }

        logger.info(f"调用LLM API - 消息数量: {len(messages)}, 模型: {self.model}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # 根据API URL决定是否添加 /chat/completions
                if self.api_url.endswith('/chat/completions'):
                    request_url = self.api_url
                else:
                    request_url = f"{self.api_url}/chat/completions"

                response = await client.post(
                    request_url,
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()

                result = response.json()

                # 处理可能的编码问题
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    # 如果内容是bytes类型，尝试解码
                    if isinstance(content, bytes):
                        try:
                            content = content.decode('utf-8')
                        except UnicodeDecodeError:
                            try:
                                content = content.decode('gbk')
                            except UnicodeDecodeError:
                                content = str(content)
                    logger.info("Successfully parsed JSON and decoded content")
                    return content
                else:
                    raise ValueError(f"LLM API返回格式异常: {result}")

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM API HTTP错误: {e.response.status_code} - {e.response.text}")
            raise Exception(f"LLM API调用失败: HTTP {e.response.status_code}")

        except httpx.TimeoutException:
            logger.error(f"LLM API请求超时 (>{self.timeout}秒)")
            raise Exception("LLM API请求超时")

        except httpx.RequestError as e:
            logger.error(f"LLM API请求错误: {str(e)}")
            raise Exception(f"LLM API请求失败: {str(e)}")

        except json.JSONDecodeError as e:
            logger.error(f"LLM API响应解析失败: {str(e)}")
            raise Exception("LLM API响应格式错误")

        except Exception as e:
            logger.error(f"LLM API调用异常: {str(e)}")
            raise Exception(f"LLM API调用失败: {str(e)}")
            # =========================================================================
    #  核心修改区域：智能引导 (Intelligent Guidance) - 支持 JSON 意图识别与上下文穿透
    # =========================================================================

    async def intelligent_guidance(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        [重构版] 智能引导接口
        核心改进：
        1. 使用 CoT (思维链) 让 LLM 准确判断意图。
        2. 提取 summary 实现上下文穿透。
        """
        # 1. 强化的 System Prompt
        system_prompt = """你是一个智能法律应用的分发路由助手。你的任务不是直接回答法律问题，而是分析用户需求，将其引导至最合适的APP功能模块。

请分析用户输入，并严格按照下面的 JSON 格式返回结果（不要包含 Markdown 格式）：

{
    "thought": "简短的思考过程，分析用户核心痛点",
    "intents": ["意图代码1", "意图代码2"],
    "summary": "用户需求的高度浓缩摘要（用于传递给下游模块，保留关键事实、金额、诉求）",
    "reply": "给用户的简短引导语，语气亲切专业，告知已为其准备好相关工具"
}

=== 可用的意图代码 (Intents) ===
- CONTRACT_GENERATE: 合同生成/起草/写协议
- CONTRACT_REVIEW: 合同审查/审核/看风险
- RISK_ASSESSMENT: 风险评估/合规分析 (通用)
- CASE_ANALYSIS: 案件分析/打官司/诉讼策略
- DOC_DRAFTING: 起草律师函/起诉状/司法文书
- LEGAL_CONSULT: 复杂的法律咨询/不确定用什么工具
- COST_CALC: 算律师费/诉讼费
- TEMPLATE_SEARCH: 查找合同模板

=== 示例 ===
用户: "别人欠我50万货款不还，手里只有送货单，能打赢吗？"
返回:
{
    "thought": "用户涉及欠款纠纷，关心胜诉率，属于案件分析场景。",
    "intents": ["CASE_ANALYSIS"],
    "summary": "拖欠货款50万元，仅有送货单证据，咨询胜诉可能性",
    "reply": "针对您的货款纠纷，我为您推荐【案件分析】功能，可以帮您预判胜诉率并梳理证据链。"
}
"""

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
             messages.extend(conversation_history[-5:]) # 仅保留最近5条
        messages.append({"role": "user", "content": user_message})

        try:
            # 2. 调用 LLM (JSON模式)
            raw_response = await self.chat_completion(
                messages=messages,
                temperature=0.3, # 降低随机性，保证 JSON 格式稳定
                max_tokens=800
            )
            
            # 3. 解析 LLM 返回的 JSON
            parsed_data = self._parse_llm_json(raw_response)
            
            # 如果解析失败，回退到旧逻辑（兜底）
            if not parsed_data:
                logger.warning("LLM JSON解析失败，使用回退逻辑")
                return await self._fallback_guidance(user_message, conversation_history)

            # 4. 根据 LLM 的判断生成按钮 (传入 summary 实现上下文穿透)
            action_buttons = self._generate_buttons_from_intent(
                parsed_data.get("intents", []),
                parsed_data.get("summary", user_message)
            )

            return {
                "response": parsed_data.get("reply", "已为您找到相关服务："),
                "suggestions": self._map_intents_to_suggestions(parsed_data.get("intents", [])),
                "action_buttons": action_buttons,
                "confidence": 0.95
            }

        except Exception as e:
            logger.error(f"智能引导处理异常: {e}")
            # 发生异常时的兜底
            return await self._fallback_guidance(user_message, conversation_history)

    def _parse_llm_json(self, text: str) -> Optional[Dict]:
        """解析 LLM 返回的 JSON 字符串，支持 Markdown 代码块剥离"""
        try:
            # 尝试提取 ```json ... ``` 块
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                text = match.group(1)
            else:
                # 尝试提取纯 {} 
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    text = match.group(0)
            
            return json.loads(text)
        except:
            return None

    def _generate_buttons_from_intent(self, intents: List[str], summary: str) -> List[Dict]:
        """根据 Intent 生成按钮，并将 summary 注入到 params 中"""
        buttons = []
        
        # 意图到路由的映射表
        # params 中注入 'user_requirement' 或 'context'，前端需对应接收
        intent_map = {
            "CONTRACT_GENERATE": {
                "id": "btn_gen", "title": "✍️ 合同生成", "type": "contract_generation",
                "route": "/contract/generate", 
                "params": {"action": "generate", "user_requirement": summary} 
            },
            "CONTRACT_REVIEW": {
                "id": "btn_review", "title": "📝 合同审查", "type": "contract_review",
                "route": "/contract/review",
                "params": {"action": "review", "context": summary} 
            },
            "RISK_ASSESSMENT": {
                "id": "btn_risk", "title": "🛡️ 风险评估", "type": "risk_analysis",
                "route": "/risk-analysis",
                "params": {"action": "analyze", "description": summary}
            },
            "CASE_ANALYSIS": {
                "id": "btn_case", "title": "⚖️ 案件分析", "type": "case_analysis",
                "route": "/litigation-analysis",
                "params": {"action": "analyze", "case_desc": summary}
            },
            "DOC_DRAFTING": {
                "id": "btn_draft", "title": "📄 文书起草", "type": "document_drafting",
                "route": "/document-drafting",
                "params": {"action": "draft", "requirement": summary}
            },
            "LEGAL_CONSULT": {
                "id": "btn_consult", "title": "💬 智能咨询", "type": "legal_consultation",
                "route": "/consultation",
                "params": {"initial_input": summary}
            },
             "COST_CALC": {
                "id": "btn_cost", "title": "💰 费用测算", "type": "cost_calculation",
                "route": "/cost-calculation",
                "params": {"case_info": summary}
            },
             "TEMPLATE_SEARCH": {
                "id": "btn_template", "title": "📋 模板查询", "type": "template_query",
                "route": "/contract",
                "params": {"action": "query", "search": summary}
            },
            "DOC_PROCESS": {
                "id": "btn_process", 
                "title": "📂 文档处理", 
                "type": "document_processing",
                "route": "/document-processing",
                "params": {}
            }     

        }

        for intent in intents:
            if intent in intent_map:
                buttons.append(intent_map[intent])
        
        # 如果没有匹配到，或者按钮太少，补充默认按钮
        if not buttons:
             buttons.append(intent_map["LEGAL_CONSULT"])
        
        return buttons[:3]

    def _map_intents_to_suggestions(self, intents: List[str]) -> List[str]:
        """将意图代码转换为用户可读的建议标签"""
        mapping = {
            "CONTRACT_GENERATE": "生成合同",
            "CONTRACT_REVIEW": "审查合同",
            "RISK_ASSESSMENT": "风险评估",
            "CASE_ANALYSIS": "案件分析",
            "DOC_DRAFTING": "文书起草",
            "LEGAL_CONSULT": "智能咨询",
            "COST_CALC": "费用测算",
            "TEMPLATE_SEARCH": "查找模板"
        }
        suggestions = []
        for i in intents:
            if i in mapping:
                suggestions.append(mapping[i])
        
        # 补全建议以保持 UI 美观
        defaults = ["生成合同", "风险评估", "案件分析"]
        for d in defaults:
            if d not in suggestions and len(suggestions) < 4:
                suggestions.append(d)
                
        return suggestions

    async def _fallback_guidance(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        兜底逻辑：当 JSON 解析失败时，回退到基于文本生成的旧模式
        """
        logger.warning(f"触发兜底引导逻辑: {user_message[:20]}...")
        
        # 使用旧的 Prompt，不强制 JSON
        fallback_prompt = "你是一个AI法律助手。请根据用户输入简要回答，并推荐相关功能（合同生成、风险评估、案件分析等）。"
        messages = [{"role": "system", "content": fallback_prompt}]
        messages.append({"role": "user", "content": user_message})
        
        try:
            ai_response = await self.chat_completion(messages, temperature=0.7, max_tokens=800)
            
            # 使用旧的关键词匹配逻辑生成按钮
            action_buttons = self._generate_guidance_buttons_legacy(user_message, ai_response)
            suggestions = self._extract_guidance_suggestions_legacy(ai_response)
            
            return {
                "response": ai_response,
                "suggestions": suggestions,
                "action_buttons": action_buttons,
                "confidence": 0.6
            }
        except Exception as e:
            logger.error(f"兜底逻辑也失败了: {e}")
            return {
                "response": "抱歉，我现在无法连接到智能服务，请直接选择下方的功能卡片。",
                "suggestions": ["合同生成", "风险评估"],
                "action_buttons": [],
                "confidence": 0.0
            }

    def _generate_guidance_buttons_legacy(self, user_message: str, ai_response: str) -> List[Dict[str, Any]]:
        """旧的基于关键词的按钮生成逻辑"""
        action_buttons = []
        user_message_lower = user_message.lower()
        
        # 简化的关键词匹配
        if any(k in user_message_lower for k in ["分析", "风险", "合规"]):
            action_buttons.append({
                "id": "risk_legacy", "title": "风险评估", "type": "risk_analysis",
                "route": "/risk-analysis", "params": {"action": "analyze"},
                "description": "深度分析法律文件"
            })
        if any(k in user_message_lower for k in ["合同", "起草", "生成"]):
             action_buttons.append({
                "id": "gen_legacy", "title": "合同生成", "type": "contract_generation",
                "route": "/contract/generate", "params": {"action": "generate"},
                "description": "智能生成合同"
            })
        if not action_buttons:
             action_buttons.append({
                "id": "consult_legacy", "title": "智能咨询", "type": "legal_consultation",
                "route": "/consultation", "params": {},
                "description": "专业律师咨询"
            })
        return action_buttons

    def _extract_guidance_suggestions_legacy(self, ai_response: str) -> List[str]:
        """旧的建议提取逻辑"""
        keywords = ["合同生成", "风险评估", "案件分析", "合同审查"]
        suggestions = []
        for k in keywords:
            if k in ai_response:
                suggestions.append(k)
        if not suggestions:
            suggestions = ["合同生成", "风险评估"]
        return suggestions
        # =========================================================================
    #  其他保留方法 (Legal Consultation & Intent Analysis)
    # =========================================================================

    async def legal_consultation(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        法律咨询专用接口
        """
        # 构建系统提示词
        system_prompt = """你是一个专业的AI法律助手。你的职责是通过对话方式帮助用户明确具体需求，并推荐最合适的处理方案。

请遵循以下原则：
1. 使用友好、专业的语言
2. 仔细分析用户的问题和需求
3. 提供有针对性的法律建议
4. 当能够确定用户具体需求时，主动推荐相应的法律服务
5. 如果问题复杂，建议用户寻求专业律师帮助

你可以推荐的服务包括：
- 合同生成：帮助起草各类合同文书
- 法律分析：分析法律风险和合规问题
- 案件分析：分析和评估案件情况
- 合同审查：审查现有合同的法律风险
- 文书起草：起草律师函、起诉状等法律文书
- 法律检索：查询相关法律法规和判例"""

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            messages.extend(recent_history)

        messages.append({"role": "user", "content": user_message})

        try:
            ai_response = await self.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=1500
            )

            suggestions = self._extract_suggestions(ai_response)
            action_buttons = self._generate_action_buttons(user_message, ai_response, suggestions)

            return {
                "response": ai_response,
                "suggestions": suggestions,
                "action_buttons": action_buttons,
                "confidence": self._calculate_confidence(user_message, ai_response)
            }

        except Exception as e:
            logger.error(f"法律咨询对话失败: {str(e)}")
            raise

    def _extract_suggestions(self, ai_response: str) -> List[str]:
        all_suggestions = [
            "合同生成", "法律分析", "案件分析", "合同审查",
            "文书起草", "法律检索", "费用测算", "函件起草"
        ]

        suggestions = []
        suggestion_keywords = {
            "合同生成": ["合同", "协议", "起草", "生成", "制定"],
            "法律分析": ["分析", "风险", "合规", "法律问题"],
            "案件分析": ["案件", "诉讼", "起诉", "官司"],
            "合同审查": ["审查", "审核", "检查", "风险点"],
            "文书起草": ["律师函", "起诉状", "申请书", "文书"],
            "法律检索": ["查询", "检索", "法规", "条文"],
            "费用测算": ["费用", "成本", "计算", "多少钱"],
            "函件起草": ["函件", "通知", "函", "催告"]
        }

        for suggestion, keywords in suggestion_keywords.items():
            if any(keyword in ai_response for keyword in keywords):
                suggestions.append(suggestion)

        if not suggestions:
            suggestions = ["合同生成", "法律分析", "案件分析"]
        return suggestions[:4]

    def _generate_action_buttons(self, user_message: str, ai_response: str, suggestions: List[str]) -> List[Dict[str, Any]]:
        action_buttons = []
        user_message_lower = user_message.lower()

        if any(keyword in user_message_lower for keyword in ["劳动合同", "用工合同", "雇佣合同", "员工合同"]):
            action_buttons.extend([
                {
                    "id": "template_query_labor", "title": "📋 模板查询", "type": "template_query",
                    "route": "/contract", "params": {"type": "labor", "action": "query"},
                    "description": "查询劳动合同模板库"
                },
                {
                    "id": "contract_generate_labor", "title": "✍️ 合同生成", "type": "contract_generation",
                    "route": "/contract", "params": {"type": "labor", "action": "generate"},
                    "description": "智能生成劳动合同"
                }
            ])
        elif any(keyword in user_message_lower for keyword in ["租赁合同", "租房合同", "房屋租赁"]):
            action_buttons.extend([
                {
                    "id": "template_query_rental", "title": "📋 模板查询", "type": "template_query",
                    "route": "/contract", "params": {"type": "rental", "action": "query"},
                    "description": "查询租赁合同模板库"
                },
                {
                    "id": "contract_generate_rental", "title": "✍️ 合同生成", "type": "contract_generation",
                    "route": "/contract", "params": {"type": "rental", "action": "generate"},
                    "description": "智能生成租赁合同"
                }
            ])
        elif any(keyword in user_message_lower for keyword in ["合同", "协议"]):
            action_buttons.extend([
                {
                    "id": "template_query_general", "title": "📋 模板查询", "type": "template_query",
                    "route": "/contract", "params": {"action": "query"},
                    "description": "查询各类合同模板"
                },
                {
                    "id": "contract_generate_general", "title": "✍️ 合同生成", "type": "contract_generation",
                    "route": "/contract", "params": {"action": "generate"},
                    "description": "智能生成合同文档"
                }
            ])
        elif any(keyword in user_message_lower for keyword in ["分析", "风险", "合规", "法律问题"]):
            action_buttons.extend([
                {
                    "id": "legal_analysis_doc", "title": "🔍 文档分析", "type": "legal_analysis",
                    "route": "/analysis", "params": {"action": "analyze"},
                    "description": "上传文档进行法律分析"
                },
                {
                    "id": "case_analysis", "title": "⚖️ 案件分析", "type": "case_analysis",
                    "route": "/analysis", "params": {"action": "case"},
                    "description": "分析案件情况"
                }
            ])

        for suggestion in suggestions[:2]:
            if suggestion == "合同审查" and not any(btn["type"] == "contract_review" for btn in action_buttons):
                action_buttons.append({
                    "id": "contract_review", "title": "📝 合同审查", "type": "contract_review",
                    "route": "/review", "params": {"action": "review"},
                    "description": "审查合同法律风险"
                })
            elif suggestion == "文书起草" and not any(btn["type"] == "document_drafting" for btn in action_buttons):
                action_buttons.append({
                    "id": "document_drafting", "title": "📄 文书起草", "type": "document_drafting",
                    "route": "/contract", "params": {"action": "draft"},
                    "description": "起草法律文书"
                })
            elif suggestion == "法律检索" and not any(btn["type"] == "legal_research" for btn in action_buttons):
                action_buttons.append({
                    "id": "legal_research", "title": "📚 法律检索", "type": "legal_research",
                    "route": "/analysis", "params": {"action": "research"},
                    "description": "查询相关法律法规"
                })

        return action_buttons[:3]

    def _calculate_confidence(self, user_message: str, ai_response: str) -> float:
        user_length = len(user_message)
        ai_length = len(ai_response)
        if user_length < 10: return 0.5
        elif ai_length < 50: return 0.6
        elif ai_length > 1000: return 0.9
        else: return 0.75

    async def analyze_search_intent(self, query: str) -> Dict[str, Any]:
        """分析用户的搜索意图"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": """你是一个专业的法律文档搜索意图分析助手...（此处保持原Prompt不变）"""
                },
                {
                    "role": "user",
                    "content": f"请分析这个搜索查询：{query}"
                }
            ]

            response = await self.chat_completion(
                messages=messages,
                max_tokens=500,
                temperature=0.1
            )

            import re
            import json
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    intent_result = json.loads(json_str)
                    return intent_result
                except json.JSONDecodeError:
                    logger.warning(f"无法解析Deepseek返回的JSON: {json_str}")

            return self._fallback_intent_analysis(query)

        except Exception as e:
            logger.error(f"分析搜索意图失败: {str(e)}")
            return self._fallback_intent_analysis(query)

    def _fallback_intent_analysis(self, query: str) -> Dict[str, Any]:
        query_lower = query.lower()
        category_keywords = {
            "劳动合同": ["劳动", "用工", "雇佣", "员工", "工作", "职位"],
            "租赁合同": ["租赁", "出租", "承租", "房租", "房屋", "设备"],
            "买卖合同": ["买卖", "购销", "销售", "购买", "货物", "商品"],
            "借款合同": ["借款", "贷款", "借钱", "利息", "还款"],
            "保密协议": ["保密", "nda", "机密", "商业秘密"],
            "服务合同": ["服务", "技术服务", "咨询", "顾问"],
            "合作协议": ["合作", "合伙", "联合", "协议"],
            "股权转让": ["股权", "转让", "股份", "投资"],
            "建设工程": ["建设", "工程", "施工", "装修", "建筑"]
        }

        categories = []
        keywords = []

        for category, kw_list in category_keywords.items():
            if any(kw in query_lower for kw in kw_list):
                categories.append(category)
                keywords.extend([kw for kw in kw_list if kw in query_lower])

        generic_keywords = ["模板", "合同", "协议", "范本", "样本"]
        for keyword in generic_keywords:
            if keyword in query_lower:
                keywords.append(keyword)

        return {
            "intent": f"搜索{categories[0] if categories else '合同'}模板",
            "keywords": list(set(keywords)),
            "categories": categories,
            "specific_type": categories[0] if categories else "通用合同",
            "urgency": "medium",
            "complexity": "simple"
        }
    
    async def legal_expert_consultation(self, user_message: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        智能咨询专用接口 - 资深律师角色
        """
        consultation_system_prompt = """你是一位拥有15年执业经验的资深律师...（此处保持原Prompt不变）"""

        messages = [{"role": "system", "content": consultation_system_prompt}]

        if conversation_history:
            recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
            messages.extend(recent_history)

        messages.append({"role": "user", "content": user_message})

        try:
            ai_response = await self.chat_completion(
                messages=messages,
                temperature=0.5,
                max_tokens=1500
            )

            action_buttons = self._generate_consultation_buttons(user_message, ai_response)
            suggestions = self._extract_consultation_suggestions(ai_response)

            return {
                "response": ai_response,
                "suggestions": suggestions,
                "action_buttons": action_buttons,
                "confidence": self._calculate_confidence(user_message, ai_response)
            }

        except Exception as e:
            logger.error(f"智能咨询对话失败: {str(e)}")
            raise
    
    def _generate_consultation_buttons(self, user_message: str, ai_response: str) -> List[Dict[str, Any]]:
        action_buttons = []
        user_message_lower = user_message.lower()

        if any(keyword in user_message_lower for keyword in ["案件", "诉讼", "起诉", "官司"]):
            action_buttons.extend([
                {"id": "case_analysis_deep", "title": "深度案件分析", "type": "case_analysis", "route": "/analysis", "params": {"action": "case_deep"}, "description": "专业律师深度案件分析"},
                {"id": "litigation_strategy", "title": "诉讼策略", "type": "litigation_strategy", "route": "/analysis", "params": {"action": "strategy"}, "description": "制定专业诉讼策略"}
            ])
        elif any(keyword in user_message_lower for keyword in ["合同", "协议"]):
            action_buttons.extend([
                {"id": "contract_review_professional", "title": "专业合同审查", "type": "contract_review", "route": "/review", "params": {"action": "professional"}, "description": "资深律师合同审查"},
                {"id": "risk_assessment", "title": "风险评估", "type": "risk_assessment", "route": "/analysis", "params": {"action": "risk"}, "description": "专业法律风险评估"}
            ])
        elif any(keyword in user_message_lower for keyword in ["律师函", "催告", "通知"]):
            action_buttons.append({"id": "lawyer_letter_drafting", "title": "律师函起草", "type": "document_drafting", "route": "/contract", "params": {"action": "lawyer_letter"}, "description": "专业律师函起草服务"})
        elif any(keyword in user_message_lower for keyword in ["咨询", "建议", "怎么办"]):
            action_buttons.extend([
                {"id": "legal_research_professional", "title": "专业法律检索", "type": "legal_research", "route": "/analysis", "params": {"action": "research_professional"}, "description": "资深律师法律检索分析"},
                {"id": "follow_up_consultation", "title": "后续咨询", "type": "follow_up_consultation", "route": "/consultation", "params": {"action": "follow_up"}, "description": "继续专业法律咨询"}
            ])
        if not action_buttons:
            action_buttons.extend([
                {"id": "comprehensive_legal_analysis", "title": "综合法律分析", "type": "legal_analysis", "route": "/analysis", "params": {"action": "comprehensive"}, "description": "资深律师综合法律分析"},
                {"id": "document_review", "title": "文档审查", "type": "document_review", "route": "/review", "params": {"action": "document"}, "description": "专业法律文档审查"}
            ])
        return action_buttons[:2]

    def _extract_consultation_suggestions(self, ai_response: str) -> List[str]:
        consultation_suggestions = ["深度分析", "专业审查", "风险评估", "诉讼策略", "法律检索", "案件评估", "文书起草", "后续咨询"]
        suggestions = []
        consultation_keywords = {
            "深度分析": ["深入分析", "详细分析", "全面分析"],
            "专业审查": ["审查", "审核", "检查"],
            "风险评估": ["风险", "危险", "潜在问题"],
            "诉讼策略": ["诉讼", "起诉", "策略", "方案"],
            "法律检索": ["查询", "检索", "法规", "条文"],
            "案件评估": ["案件", "评估", "胜诉", "可能性"],
            "文书起草": ["起草", "写", "制作", "文书"],
            "后续咨询": ["继续咨询", "进一步", "后续", "下次"]
        }
        for suggestion, keywords in consultation_keywords.items():
            if any(keyword in ai_response.lower() for keyword in keywords):
                suggestions.append(suggestion)
        if not suggestions:
            suggestions = ["深度分析", "专业审查"]
        return suggestions[:3]

# 创建全局Deepseek服务实例
deepseek_service = DeepseekService()