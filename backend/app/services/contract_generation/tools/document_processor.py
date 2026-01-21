# backend/app/services/contract_generation/tools/document_processor.py
"""
文档智能处理 Tool

将现有的文档处理服务封装为 LangChain Tool，可以：
1. 作为独立功能被前端调用
2. 被 LangChain Agent 作为工具调用

复用服务：
- document_structurer: AI 结构化提取
- document_renderer: 模板渲染
- document_templates: 模板管理
"""
import logging
import os
import uuid
from typing import Optional, Dict, Any
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.services.document_structurer import get_structurer
from app.services.document_renderer import get_renderer
from app.services.document_templates import get_template_manager

logger = logging.getLogger(__name__)

UPLOAD_DIR = "storage/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


class DocumentProcessorInput(BaseModel):
    """文档处理输入参数"""
    content: str = Field(..., description="AI 生成的合同内容（Markdown 或纯文本格式）")
    doc_type: str = Field(default="contract", description="文档类型: contract/letter/judicial")
    filename: Optional[str] = Field(None, description="输出文件名（可选）")
    output_format: str = Field(default="docx", description="输出格式: docx/pdf")


class DocumentProcessorOutput(BaseModel):
    """文档处理输出结果"""
    success: bool
    filename: str
    docx_path: str
    pdf_path: Optional[str]
    preview_url: str
    download_docx_url: str
    download_pdf_url: Optional[str]
    message: str


class DocumentProcessorTool:
    """
    文档智能处理 Tool

    核心功能：
    1. AI 结构化提取 - 将 Markdown/纯文本转换为结构化数据
    2. 模板渲染 - 使用专业模板生成规范格式
    3. Word 生成 - 输出 .docx 文件
    4. PDF 转换 - 可选输出 .pdf 文件
    5. 预览配置 - 生成 OnlyOffice 预览配置
    """

    def __init__(self):
        self.structurer = get_structurer()
        self.renderer = get_renderer()
        self.template_manager = get_template_manager()

    def process(
        self,
        content: str,
        doc_type: str = "contract",
        filename: Optional[str] = None,
        output_format: str = "docx"
    ) -> DocumentProcessorOutput:
        """
        处理文档内容，生成 Word/PDF 文件

        Args:
            content: AI 生成的合同内容
            doc_type: 文档类型
            filename: 输出文件名
            output_format: 输出格式

        Returns:
            DocumentProcessorOutput 包含文件路径和预览配置
        """
        try:
            # 1. AI 结构化提取
            logger.info(f"[DocumentProcessor] 开始处理文档，类型: {doc_type}")
            structure = self.structurer.extract_structure(content, doc_type)

            if not structure or not structure.title:
                logger.warning("[DocumentProcessor] AI 结构化提取失败")
                return DocumentProcessorOutput(
                    success=False,
                    filename="",
                    docx_path="",
                    pdf_path=None,
                    preview_url="",
                    download_docx_url="",
                    download_pdf_url=None,
                    message="AI 结构化提取失败，请检查输入内容"
                )

            # 2. 生成文件名
            if not filename:
                # 清理文件名
                import re
                safe_title = re.sub(r'[<>:"/\\|?*]', '', structure.title)
                safe_title = safe_title.strip()
                if len(safe_title) > 50:
                    safe_title = safe_title[:50]
                filename = f"{safe_title}.{output_format}"

            base_filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
            docx_filename = f"{base_filename}.docx"
            docx_path = os.path.join(UPLOAD_DIR, docx_filename)

            # 3. 根据文档类型渲染
            if structure.doc_type == "letter" or doc_type == "letter":
                success = self.renderer.render_letter(structure, docx_path)
            else:
                success = self.renderer.render_contract(structure, docx_path)

            if not success:
                logger.error("[DocumentProcessor] 文档渲染失败")
                return DocumentProcessorOutput(
                    success=False,
                    filename=filename,
                    docx_path="",
                    pdf_path=None,
                    preview_url="",
                    download_docx_url="",
                    download_pdf_url=None,
                    message="文档渲染失败"
                )

            logger.info(f"[DocumentProcessor] 文档生成成功: {docx_path}")

            # 4. PDF 转换（如果需要）
            pdf_path = None
            if output_format == "pdf":
                try:
                    from app.services.converter import convert_to_pdf_via_onlyoffice
                    success, pdf_content = convert_to_pdf_via_onlyoffice(docx_filename)
                    if success:
                        pdf_path = docx_path.replace('.docx', '.pdf')
                        with open(pdf_path, 'wb') as f:
                            f.write(pdf_content)
                        logger.info(f"[DocumentProcessor] PDF 转换成功: {pdf_path}")
                except Exception as e:
                    logger.warning(f"[DocumentProcessor] PDF 转换失败: {str(e)}")

            # 5. 生成预览和下载 URL
            backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")
            file_url = f"{backend_url}/storage/uploads/{docx_filename}"

            return DocumentProcessorOutput(
                success=True,
                filename=filename,
                docx_path=docx_path,
                pdf_path=pdf_path,
                preview_url=f"/api/document/preview/by-filename/{docx_filename}",
                download_docx_url=f"/api/document/download/{docx_filename}",
                download_pdf_url=f"/api/document/download/{os.path.basename(pdf_path)}" if pdf_path else None,
                message=f"文档处理成功: {filename}"
            )

        except Exception as e:
            logger.error(f"[DocumentProcessor] 处理失败: {str(e)}", exc_info=True)
            return DocumentProcessorOutput(
                success=False,
                filename=filename or "",
                docx_path="",
                pdf_path=None,
                preview_url="",
                download_docx_url="",
                download_pdf_url=None,
                message=f"处理失败: {str(e)}"
            )

    def as_tool(self):
        """
        返回 LangChain Tool 格式，可被 Agent 调用
        """
        @tool(
            name="document_processor",
            description="""处理 AI 生成的合同内容，生成规范的 Word/PDF 文件。

            功能：
            1. AI 结构化提取 - 识别合同类型、条款结构
            2. 模板渲染 - 使用专业模板生成规范格式
            3. Word 生成 - 输出可直接使用的 .docx 文件
            4. PDF 转换 - 可选输出 .pdf 文件
            5. 预览配置 - 支持在线预览

            输入：AI 生成的合同内容（Markdown 或纯文本）
            输出：Word/PDF 文件路径、预览 URL、下载 URL

            适用场景：
            - 合同生成后需要转换为 Word 格式
            - 用户需要下载或预览生成的合同
            - 需要规范格式的法律文书
            """
        )
        def process_document(
            content: str,
            doc_type: str = "contract",
            filename: str = None,
            output_format: str = "docx"
        ) -> str:
            """
            处理文档并返回结果

            Args:
                content: AI 生成的合同内容
                doc_type: 文档类型 (contract/letter/judicial)
                filename: 输出文件名
                output_format: 输出格式 (docx/pdf)

            Returns:
                JSON 字符串，包含处理结果
            """
            result = self.process(content, doc_type, filename, output_format)
            return result.model_dump_json()

        return process_document


# 单例
_document_processor_tool: Optional[DocumentProcessorTool] = None


def get_document_processor_tool() -> DocumentProcessorTool:
    """获取文档处理器 Tool 单例"""
    global _document_processor_tool
    if _document_processor_tool is None:
        _document_processor_tool = DocumentProcessorTool()
    return _document_processor_tool
