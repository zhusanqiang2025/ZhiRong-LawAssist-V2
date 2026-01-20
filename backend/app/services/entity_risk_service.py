# backend/app/services/entity_risk_service.py
"""
主体风险查询服务

用于查询合同当事人（企业/个人）的风险信息
"""

import logging
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class EntityRiskService:
    """
    主体风险查询服务

    功能:
    - 查询企业工商信息
    - 查询失信记录
    - 查询诉讼记录
    - 查询经营异常

    注意:
    - 当前版本为模拟实现
    - 实际使用时应接入真实的第三方API (如: 天眼查、企查查、启信宝等)
    """

    def __init__(self, db: Session):
        self.db = db
        # TODO: 从配置文件读取API密钥和端点
        self.api_base_url = "https://api.example.com/entity-risk"

    async def query_entity_risk(
        self,
        entity_name: str,
        entity_type: str = "company"
    ) -> Dict[str, Any]:
        """
        查询主体风险信息

        Args:
            entity_name: 主体名称 (公司名/人名)
            entity_type: 主体类型 (company/individual)

        Returns:
            {
                "entity_name": "XX公司",
                "entity_type": "company",
                "risk_level": "High",  # High/Medium/Low/None
                "risk_items": [
                    {
                        "type": "失信记录",
                        "description": "被列入失信被执行人名单",
                        "detail": "..."
                    },
                    ...
                ]
            }
        """
        # 1️⃣ 尝试从缓存获取 (可选)
        cached = self._get_cached_risk(entity_name)
        if cached:
            logger.info(f"[EntityRiskService] 从缓存获取风险信息: {entity_name}")
            return cached

        # 2️⃣ 调用外部API查询
        # TODO: 实际使用时替换为真实的API调用
        risk_info = await self._query_from_api(entity_name, entity_type)

        # 3️⃣ 缓存结果 (可选)
        if risk_info:
            self._cache_risk(entity_name, risk_info)

        return risk_info

    async def query_multiple_entities(
        self,
        entities: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        批量查询多个主体的风险信息

        Args:
            entities: 主体列表
                [{"name": "XX公司", "type": "company"}, ...]

        Returns:
            {主体名称: 风险信息}
        """
        results = {}

        for entity in entities:
            name = entity.get("name")
            etype = entity.get("type", "company")
            if name:
                risk_info = await self.query_entity_risk(name, etype)
                results[name] = risk_info

        return results

    async def _query_from_api(
        self,
        entity_name: str,
        entity_type: str
    ) -> Dict[str, Any]:
        """
        从外部API查询风险信息

        ⚠️ 注意: 当前为模拟实现
        实际使用时应替换为真实的第三方API调用

        常用的第三方服务:
        - 天眼查: https://www.tianyancha.com/api
        - 企查查: https://www.qcc.com/api
        - 启信宝: https://www.qixin.com/api
        """
        # TODO: 实际API调用
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(
        #         f"{self.api_base_url}/query",
        #         params={"name": entity_name, "type": entity_type},
        #         timeout=30.0
        #     )
        #     result = response.json()
        #     return self._parse_risk_result(result)

        # ========== 模拟实现 ==========
        logger.info(f"[EntityRiskService] 模拟查询风险信息: {entity_name} ({entity_type})")

        # 模拟一些常见风险情况
        mock_risks = self._get_mock_risks(entity_name)

        return {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "risk_level": mock_risks.get("risk_level", "None"),
            "risk_items": mock_risks.get("risk_items", []),
            "query_time": None  # 实际使用时记录查询时间
        }

    def _get_mock_risks(self, entity_name: str) -> Dict[str, Any]:
        """
        获取模拟风险数据 (用于开发测试)

        实际使用时删除此方法
        """
        # 模拟高风险企业
        if "风险" in entity_name or "问题" in entity_name:
            return {
                "risk_level": "High",
                "risk_items": [
                    {
                        "type": "失信记录",
                        "description": "被列入失信被执行人名单",
                        "detail": f"{entity_name} 因未履行生效法律文书确定的义务，被法院列入失信被执行人名单"
                    },
                    {
                        "type": "经营异常",
                        "description": "被列入经营异常名录",
                        "detail": "通过登记的住所或者经营场所无法联系"
                    },
                    {
                        "type": "诉讼记录",
                        "description": "存在多起未结诉讼",
                        "detail": "作为被告的诉讼案件3起，总标的额约500万元"
                    }
                ]
            }

        # 模拟中等风险企业
        elif "有限" in entity_name:
            return {
                "risk_level": "Medium",
                "risk_items": [
                    {
                        "type": "行政处罚",
                        "description": "存在行政处罚记录",
                        "detail": "因税务违规被处以罚款"
                    }
                ]
            }

        # 模拟低风险企业
        else:
            return {
                "risk_level": "Low",
                "risk_items": [
                    {
                        "type": "一般提示",
                        "description": "企业正常经营",
                        "detail": "未发现重大风险信息"
                    }
                ]
            }

    def _parse_risk_result(self, raw_result: Dict) -> Dict[str, Any]:
        """
        解析外部API返回的风险信息

        Args:
            raw_result: API原始返回结果

        Returns:
            标准化的风险信息
        """
        # TODO: 根据实际使用的API格式进行解析
        # 这里提供一个通用解析框架

        risk_items = []

        # 解析失信记录
        if raw_result.get("dishonesty"):
            risk_items.append({
                "type": "失信记录",
                "description": "被列入失信被执行人名单",
                "detail": raw_result.get("dishonesty", "")
            })

        # 解析经营异常
        if raw_result.get("abnormal"):
            risk_items.append({
                "type": "经营异常",
                "description": "被列入经营异常名录",
                "detail": raw_result.get("abnormal", "")
            })

        # 解析诉讼记录
        if raw_result.get("litigation"):
            risk_items.append({
                "type": "诉讼记录",
                "description": f"存在{raw_result.get('litigation_count', 0)}起未结诉讼",
                "detail": raw_result.get("litigation", "")
            })

        # 计算风险等级
        risk_level = self._calculate_risk_level(risk_items)

        return {
            "entity_name": raw_result.get("name", ""),
            "entity_type": raw_result.get("type", "company"),
            "risk_level": risk_level,
            "risk_items": risk_items
        }

    def _calculate_risk_level(self, risk_items: List[Dict]) -> str:
        """
        根据风险项计算风险等级

        Args:
            risk_items: 风险项列表

        Returns:
            High/Medium/Low/None
        """
        if not risk_items:
            return "None"

        # 风险类型权重
        risk_weights = {
            "失信记录": 100,    # 最高风险
            "经营异常": 50,     # 高风险
            "诉讼记录": 30,     # 中等风险
            "行政处罚": 20,     # 中等风险
            "一般提示": 0,      # 无风险
        }

        # 计算总分
        total_score = 0
        for item in risk_items:
            item_type = item.get("type", "")
            for key, weight in risk_weights.items():
                if key in item_type:
                    total_score += weight
                    break

        # 阈值判断
        if total_score >= 100:
            return "High"
        elif total_score >= 30:
            return "Medium"
        elif total_score > 0:
            return "Low"
        else:
            return "None"

    def _get_cached_risk(self, entity_name: str) -> Optional[Dict]:
        """
        从缓存获取风险信息

        Args:
            entity_name: 主体名称

        Returns:
            缓存的风险信息 (如果存在且未过期)
        """
        # TODO: 实现缓存逻辑 (如: Redis)
        # 示例:
        # import redis
        # r = redis.Redis()
        # cached = r.get(f"entity_risk:{entity_name}")
        # if cached:
        #     import json
        #     return json.loads(cached)
        return None

    def _cache_risk(self, entity_name: str, risk_info: Dict):
        """
        缓存风险信息

        Args:
            entity_name: 主体名称
            risk_info: 风险信息
        """
        # TODO: 实现缓存逻辑
        # 示例:
        # import redis
        import json
        # r = redis.Redis()
        # r.setex(
        #     f"entity_risk:{entity_name}",
        #     3600,  # 缓存1小时
        #     json.dumps(risk_info, ensure_ascii=False)
        # )
        logger.info(f"[EntityRiskService] 缓存风险信息: {entity_name}")
