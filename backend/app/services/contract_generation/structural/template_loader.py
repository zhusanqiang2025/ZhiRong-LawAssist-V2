# backend/app/services/contract_generation/structural/template_loader.py
"""
模板加载器
用于从数据库或文件系统加载合同模板
"""
import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from app.models.contract_template import ContractTemplate

logger = logging.getLogger(__name__)


class TemplateLoader:
    """模板加载器"""

    def __init__(self, db: Session):
        self.db = db

    def load_template_by_id(self, template_id: str) -> Optional[ContractTemplate]:
        """通过 ID 加载模板"""
        return (
            self.db.query(ContractTemplate)
            .filter(ContractTemplate.id == template_id)
            .first()
        )

    def load_by_id(self, template_id: str) -> Optional[ContractTemplate]:
        """
        Alias for load_template_by_id (backward compatibility)
        用于兼容 workflow.py 的调用
        """
        return self.load_template_by_id(template_id)

    def load_template_content(self, template: ContractTemplate) -> str:
        """加载模板内容"""
        if not template.file_url:
            raise ValueError("模板文件路径为空")

        # 获取模板文件的完整路径
        template_path = Path("/app") / template.file_url

        if not template_path.exists():
            raise FileNotFoundError(f"模板文件不存在: {template_path}")

        # 读取文件内容
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()

    def load_template_content_by_id(self, template_id: str) -> tuple[ContractTemplate, str]:
        """通过 ID 加载模板及其内容"""
        template = self.load_template_by_id(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        content = self.load_template_content(template)
        return template, content


def get_template_loader(db: Session) -> TemplateLoader:
    """获取模板加载器实例"""
    return TemplateLoader(db)
