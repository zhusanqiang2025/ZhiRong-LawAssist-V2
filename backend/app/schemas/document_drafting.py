# backend/app/schemas/document_drafting.py
"""
文书起草相关的 Pydantic Schema 定义
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class AnalyzeRequest(BaseModel):
    """需求分析请求"""
    user_input: str = Field(..., description="用户输入的文书需求描述")
    uploaded_files: Optional[List[str]] = Field(default=[], description="已上传的文件路径列表")
    reference_content: Optional[str] = Field(default="", description="参考资料内容")


class AnalyzeResponse(BaseModel):
    """需求分析响应"""
    document_type: str = Field(..., description="识别的文书类型")
    document_name: str = Field(..., description="文书名称")
    extracted_info: Dict[str, Any] = Field(..., description="提取的关键信息")
    clarification_questions: List[str] = Field(default=[], description="需要澄清的问题列表")


class GenerateRequest(BaseModel):
    """文书生成请求"""
    user_input: str = Field(..., description="用户输入的文书需求描述")
    uploaded_files: Optional[List[str]] = Field(default=[], description="已上传的文件路径列表")
    document_type: Optional[str] = Field(default=None, description="指定的文书类型")
    clarification_answers: Optional[Dict[str, Any]] = Field(default={}, description="澄清问题的答案")


class GenerateResponse(BaseModel):
    """文书生成响应"""
    session_id: str = Field(..., description="会话ID")
    generated_documents: List[Dict[str, Any]] = Field(..., description="生成的文书列表")
    status: str = Field(..., description="生成状态：success/failed")
    message: str = Field(..., description="状态消息")


class TemplateInfo(BaseModel):
    """文书模板信息"""
    id: str = Field(..., description="文书类型标识")
    name: str = Field(..., description="文书名称")
    description: str = Field(..., description="文书描述")
    category: str = Field(..., description="文书分类：letter/judicial")


class UploadFileResponse(BaseModel):
    """文件上传响应"""
    file_path: str = Field(..., description="文件保存路径")
    filename: str = Field(..., description="原始文件名")
    message: str = Field(..., description="上传结果消息")
