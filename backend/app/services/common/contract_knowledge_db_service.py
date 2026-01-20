"""
基于数据库的合同知识图谱服务

替代原有的基于JSON文件的 knowledge_graph_service
提供统一的知识图谱数据访问接口
"""
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.contract_knowledge import ContractKnowledgeType
import logging

logger = logging.getLogger(__name__)


class ContractKnowledgeDBService:
    """
    数据库版知识图谱服务

    从 PostgreSQL 数据库读取合同法律特征知识图谱
    支持按名称查询、关键词搜索、分类查询等
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_by_name(self, name: str) -> Optional[Dict]:
        """
        根据合同名称获取定义

        Args:
            name: 合同类型名称

        Returns:
            合同类型字典，如果未找到返回 None
        """
        db = None
        try:
            db = SessionLocal()
            record = db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.name == name,
                ContractKnowledgeType.is_active == True
            ).first()

            if not record:
                return None

            return self._to_dict(record)
        except Exception as e:
            logger.warning(f"[ContractKnowledgeDBService] 数据库查询失败: {e}")
            return None
        finally:
            if db:
                db.close()

    def get_by_id(self, id: int) -> Optional[Dict]:
        """
        根据ID获取定义

        Args:
            id: 合同类型ID

        Returns:
            合同类型字典，如果未找到返回 None
        """
        db = None
        try:
            db = SessionLocal()
            record = db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.id == id,
                ContractKnowledgeType.is_active == True
            ).first()

            if not record:
                return None

            return self._to_dict(record)
        except Exception as e:
            logger.warning(f"[ContractKnowledgeDBService] 数据库查询失败: {e}")
            return None
        finally:
            if db:
                db.close()

    def get_all(self) -> List[Dict]:
        """
        获取所有合同类型

        Returns:
            合同类型字典列表
        """
        db = None
        try:
            db = SessionLocal()
            records = db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.is_active == True
            ).order_by(ContractKnowledgeType.name).all()

            return [self._to_dict(r) for r in records]
        except Exception as e:
            logger.warning(f"[ContractKnowledgeDBService] 数据库查询失败: {e}")
            return []
        finally:
            if db:
                db.close()

    def search_by_keywords(self, query: str) -> List[Dict]:
        """
        关键词搜索合同类型

        Args:
            query: 搜索关键词

        Returns:
            匹配的合同类型字典列表（最多5个）
        """
        if not query or not query.strip():
            return []

        db = None
        try:
            db = SessionLocal()
            # 名称包含匹配
            records = db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.is_active == True,
                ContractKnowledgeType.name.contains(query.strip())
            ).all()

            results = [(self._to_dict(r), 10.0) for r in records]

            # 如果名称匹配少于5个，搜索别名
            if len(results) < 5:
                all_records = db.query(ContractKnowledgeType).filter(
                    ContractKnowledgeType.is_active == True
                ).all()

                for record in all_records:
                    if record.id not in [r.get('id') for r, _ in results]:
                        aliases = record.aliases or []
                        query_lower = query.strip().lower()
                        for alias in aliases:
                            if query_lower in alias.lower():
                                results.append((self._to_dict(record), 8.0))
                                if len(results) >= 5:
                                    break
                        if len(results) >= 5:
                            break

            # 按分数排序
            results.sort(key=lambda x: x[1], reverse=True)
            return [r for r, _ in results[:5]]
        except Exception as e:
            logger.warning(f"[ContractKnowledgeDBService] 数据库查询失败: {e}")
            return []
        finally:
            if db:
                db.close()

    def get_by_category(self, category: str, subcategory: Optional[str] = None) -> List[Dict]:
        """
        根据分类获取合同类型

        Args:
            category: 一级分类
            subcategory: 二级分类（可选）

        Returns:
            该分类下的合同类型列表
        """
        db = SessionLocal()
        try:
            query = db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.is_active == True,
                ContractKnowledgeType.category == category
            )

            if subcategory:
                query = query.filter(ContractKnowledgeType.subcategory == subcategory)

            records = query.order_by(ContractKnowledgeType.name).all()

            return [self._to_dict(r) for r in records]
        finally:
            db.close()

    def count(self) -> int:
        """
        获取合同类型总数

        Returns:
            活跃的合同类型数量
        """
        db = SessionLocal()
        try:
            return db.query(ContractKnowledgeType).filter(
                ContractKnowledgeType.is_active == True
            ).count()
        finally:
            db.close()

    def _to_dict(self, record: ContractKnowledgeType) -> Dict:
        """
        转换为字典格式

        兼容原有的JSON结构，确保现有代码无缝迁移
        """
        return {
            "id": record.id,
            "name": record.name,
            "aliases": record.aliases or [],
            "category": record.category or "",
            "subcategory": record.subcategory or "",
            "legal_features": {
                "transaction_nature": record.transaction_nature,
                "contract_object": record.contract_object,
                "stance": record.stance,
                "consideration_type": record.consideration_type,
                "consideration_detail": record.consideration_detail or "",
                "transaction_characteristics": record.transaction_characteristics or "",
                "usage_scenario": record.usage_scenario or "",
                "legal_basis": record.legal_basis or []
            },
            "recommended_template_ids": record.recommended_template_ids or []
        }


# 单例导出（保持与原 service 相同的导出方式）
contract_knowledge_db_service = ContractKnowledgeDBService()

# 为了兼容性，也导出一个别名为 kg_service
kg_service = contract_knowledge_db_service
