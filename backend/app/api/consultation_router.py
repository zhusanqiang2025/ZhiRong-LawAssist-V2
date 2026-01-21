# backend/app/api/consultation_router.py
"""
智能咨询 API 路由
提供智能咨询文件上传和咨询服务
"""

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import os
import asyncio
import logging

router = APIRouter(tags=["Intelligent Consultation"])
logger = logging.getLogger(__name__)

# 模拟数据库存储
uploaded_files = {}  # 存储上传的文件信息：{file_id: {filename, file_path, content, metadata}}


class ConsultationRequest(BaseModel):
    question: str
    context: Dict[str, Any] = {}
    uploaded_files: Optional[List[str]] = None  # 已上传文件ID列表
    user_confirmed: Optional[bool] = False  # 用户是否已确认（用于第二阶段调用）
    selected_suggested_questions: Optional[List[str]] = None  # 用户选择的建议问题（第二阶段调用时传递）
    is_follow_up: Optional[bool] = False  # 已废弃，使用后端判断
    session_id: Optional[str] = None  # 新增：会话ID
    previous_specialist_output: Optional[Dict[str, Any]] = None  # 新增：上一轮专业律师输出
    reset_session: Optional[bool] = False  # 新增：前端请求重置会话


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_type: str
    content_preview: str  # 文件内容预览
    message: str


class ConsultationResponse(BaseModel):
    answer: str
    specialist_role: Optional[str] = None
    primary_type: Optional[str] = None
    confidence: Optional[float] = None
    relevant_laws: Optional[List[str]] = None
    need_confirmation: Optional[bool] = None
    response: Optional[str] = None  # 保持兼容性，与 answer 相同
    basic_summary: Optional[str] = None  # 案件基本情况总结
    direct_questions: Optional[List[str]] = None  # 直接提炼的问题
    suggested_questions: Optional[List[str]] = None  # 推测的建议问题（可选）
    recommended_approach: Optional[str] = None  # 建议的处理方式
    document_analysis: Optional[Dict[str, Any]] = None  # 文档深度分析结果
    final_report: Optional[bool] = None  # 标识是否为最终专业律师报告
    analysis: Optional[str] = None  # 问题分析
    advice: Optional[str] = None  # 专业建议
    risk_warning: Optional[str] = None  # 风险提醒
    action_steps: Optional[List[str]] = None  # 行动步骤
    session_id: Optional[str] = None  # 会话ID（用于多轮对话）


@router.post("/upload", response_model=FileUploadResponse)
async def upload_consultation_file(file: UploadFile = File(...)):
    """
    上传文件用于法律咨询
    支持的格式：.pdf, .docx, .doc, .txt
    """
    # 验证文件类型
    file_extension = file.filename.split(".")[-1].lower() if "." in file.filename else ""
    supported_formats = ["pdf", "docx", "doc", "txt"]

    if file_extension not in supported_formats:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式。支持的格式：{', '.join(supported_formats)}"
        )

    # 生成文件ID
    file_id = str(uuid.uuid4())

    # 创建上传目录
    upload_dir = "uploads/consultation"
    os.makedirs(upload_dir, exist_ok=True)

    # 保存文件
    file_location = f"{upload_dir}/{file_id}.{file_extension}"

    try:
        with open(file_location, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败：{str(e)}")

    # 使用统一文档服务提取内容
    try:
        from app.services.unified_document_service import get_unified_document_service
        doc_service = get_unified_document_service()

        # 处理文档
        result = doc_service.process_document(
            file_path=file_location,
            extract_content=True,
            extract_metadata=True
        )

        if result.status.value == "success":
            # 提取成功
            content_preview = result.content[:500] if len(result.content) > 500 else result.content
            if len(result.content) > 500:
                content_preview += "..."

            # 存储文件信息
            uploaded_files[file_id] = {
                "file_id": file_id,
                "filename": file.filename,
                "file_path": file_location,
                "file_type": file_extension,
                "content": result.content,
                "metadata": result.metadata,
                "uploaded_at": str(asyncio.get_event_loop().time())
            }

            # 构建成功消息
            method_info = f"使用 {result.processing_method}" if result.processing_method else ""
            char_count = len(result.content)
            message = f"文件上传成功，已提取 {char_count} 个字符"
            if method_info:
                message += f" ({method_info})"
            if result.from_cache:
                message += " [来自缓存]"

            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                file_type=file_extension,
                content_preview=content_preview,
                message=message
            )
        elif result.status.value == "partial":
            # 部分成功
            content_preview = result.content[:500] if result.content and len(result.content) > 500 else (result.content or "")
            if result.content and len(result.content) > 500:
                content_preview += "..."

            # 存储文件信息（即使部分成功也保存）
            uploaded_files[file_id] = {
                "file_id": file_id,
                "filename": file.filename,
                "file_path": file_location,
                "file_type": file_extension,
                "content": result.content or "",
                "metadata": result.metadata,
                "uploaded_at": str(asyncio.get_event_loop().time())
            }

            # 构建部分成功消息
            warnings_str = "; ".join(result.warnings) if result.warnings else ""
            message = f"文件上传成功，内容提取部分成功：{warnings_str}"

            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                file_type=file_extension,
                content_preview=content_preview,
                message=message
            )
        else:
            # 提取失败
            return FileUploadResponse(
                file_id=file_id,
                filename=file.filename,
                file_type=file_extension,
                content_preview="",
                message=f"文件上传成功，但内容提取失败：{result.error}"
            )

    except Exception as e:
        # 文档服务不可用，只保存文件
        uploaded_files[file_id] = {
            "file_id": file_id,
            "filename": file.filename,
            "file_path": file_location,
            "file_type": file_extension,
            "content": "",
            "metadata": {},
            "uploaded_at": str(asyncio.get_event_loop().time())
        }

        return FileUploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_type=file_extension,
            content_preview="",
            message=f"文件上传成功，但文档处理服务不可用"
        )


@router.get("/file/{file_id}")
async def get_consultation_file(file_id: str):
    """获取已上传文件的信息"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件未找到")

    file_info = uploaded_files[file_id]
    return {
        "file_id": file_info["file_id"],
        "filename": file_info["filename"],
        "file_type": file_info["file_type"],
        "content": file_info["content"],
        "metadata": file_info["metadata"]
    }


@router.delete("/file/{file_id}")
async def delete_consultation_file(file_id: str):
    """删除已上传的文件"""
    if file_id not in uploaded_files:
        raise HTTPException(status_code=404, detail="文件未找到")

    file_info = uploaded_files[file_id]

    # 删除物理文件
    try:
        if os.path.exists(file_info["file_path"]):
            os.remove(file_info["file_path"])
    except Exception as e:
        print(f"删除文件失败：{str(e)}")

    # 删除记录
    del uploaded_files[file_id]

    return {"message": "文件删除成功"}


@router.post("", response_model=ConsultationResponse)
async def legal_consultation(request: ConsultationRequest):
    """
    法律咨询API - 基于 LangGraph 的两阶段咨询流程（支持多轮对话）

    流程：
    1. 律师助理节点：使用 LLM 进行问题分类和意图识别
    2. 专业律师节点：根据分类结果，使用专业角色提示词生成法律建议

    多轮对话支持：
    - 后端自动管理会话状态（Redis）
    - 不依赖前端传递 is_follow_up 标志
    - 后续问题直接进入专业律师节点

    支持文件内容分析
    """

    # 【调试】打印请求参数
    logger.info(f"[API] 收到咨询请求: session_id={request.session_id}, question={request.question[:50]}...")
    logger.info(f"[API] 请求完整参数: {request.dict()}")
    logger.info(f"[API] selected_suggested_questions 类型: {type(request.selected_suggested_questions)}")
    logger.info(f"[API] selected_suggested_questions 值: {request.selected_suggested_questions}")
    if request.selected_suggested_questions:
        logger.info(f"[API] selected_suggested_questions 长度: {len(request.selected_suggested_questions)}")
        for i, q in enumerate(request.selected_suggested_questions):
            logger.info(f"[API]   问题 {i+1}: {q}")

    # 【关键修改】使用后端会话管理
    from app.services.consultation_session_service import consultation_session_service

    # 获取或创建会话
    session_id, is_follow_up, previous_output = await consultation_session_service.get_or_create_session(
        session_id=request.session_id,
        question=request.question,
        reset_session=request.reset_session or False
    )

    # 【关键修复】用户确认阶段不应被视为"多轮对话"
    # 当 user_confirmed=True 时，这是第一阶段咨询的延续（确认+选择补充问题）
    # 而非真正意义上的"多轮对话"（用户基于专业律师的建议提出新问题）
    saved_classification = None
    if request.user_confirmed:
        original_is_follow_up = is_follow_up
        is_follow_up = False  # 强制设置为 False

        # 【关键】从会话中恢复第一阶段的分类结果
        saved_classification = await consultation_session_service.get_classification(session_id)
        logger.info(f"[API] 用户确认阶段：从会话恢复 classification, saved_classification keys: {list(saved_classification.keys()) if saved_classification else None}")

        logger.info(f"[API] 用户确认阶段：强制设置 is_follow_up=False (原值={original_is_follow_up})")

    logger.info(f"[API] 会话管理: session_id={session_id}, is_follow_up={is_follow_up}, user_confirmed={request.user_confirmed}")

    # ==================== 文件预读功能 ====================
    # 为律师助理节点预读文件内容，提升分类准确性
    file_preview_text = ""
    if request.uploaded_files:
        try:
            file_contents = []
            for file_id in request.uploaded_files:
                if file_id in uploaded_files:
                    file_info = uploaded_files[file_id]
                    if file_info.get("content"):
                        file_contents.append(f"## 文件：{file_info['filename']}\n{file_info['content']}")

            if file_contents:
                file_preview_text = "\n\n".join(file_contents)
                logger.info(f"[API] 文件预读成功，共 {len(file_contents)} 个文件，{len(file_preview_text)} 字符")
            else:
                logger.warning(f"[API] 文件预读失败：未找到文件内容")

        except Exception as e:
            logger.error(f"[API] 文件预读异常：{str(e)}")

    # 收集已上传文件的信息（用于AI处理）
    file_contents = []
    file_metadata = []
    file_summaries = []  # 新增：文件摘要（用于返回给前端）

    if request.uploaded_files:
        for file_id in request.uploaded_files:
            if file_id in uploaded_files:
                file_info = uploaded_files[file_id]
                # 文件信息通过 context.uploaded_files 传递给文档分析节点
                # 不再将完整内容添加到 question 中，避免 LLM 复述
                if file_info.get("content"):
                    # 仅记录文件元数据和摘要
                    file_summaries.append(f"【文件：{file_info['filename']}】已成功上传并分析")
                    file_metadata.append({
                        "filename": file_info["filename"],
                        "file_type": file_info["file_type"]
                    })

    # 不再将完整文件内容添加到问题中，避免专业律师节点复述
    # 文件内容通过 context.uploaded_files 传递给文档分析节点处理
    enhanced_question = request.question

    # 构建用户可见的问题描述（不包含文件完整内容）
    user_visible_question = request.question
    if file_summaries:
        user_visible_question = f"{request.question}\n\n{', '.join(file_summaries)}"

    # 更新上下文
    enhanced_context = request.context.copy()
    # 始终传递文件ID列表（即使文件内容为空），以便文档分析节点可以获取文件
    if request.uploaded_files:
        enhanced_context["uploaded_files"] = request.uploaded_files
    if file_metadata:
        enhanced_context["has_file_content"] = True
    # 【新增】注入文件预读内容，供律师助理节点使用
    if file_preview_text:
        enhanced_context["file_preview_text"] = file_preview_text

    # 调用 LangGraph 法律咨询工作流（异步）
    try:
        from legal_consultation_graph import run_legal_consultation

        # 【关键修改】使用后端判断的 is_follow_up 和 previous_output
        consultation_result, final_report = await run_legal_consultation(
            question=enhanced_question,
            context=enhanced_context,
            conversation_history=None,
            user_confirmed=request.user_confirmed or False,
            selected_suggested_questions=request.selected_suggested_questions,
            is_follow_up=is_follow_up,  # 使用后端判断的结果
            session_id=session_id,  # 使用后端管理的 session_id
            previous_specialist_output=previous_output,  # 使用后端获取的上一轮输出
            saved_classification=saved_classification  # 【新增】传递恢复的分类结果
        )

        if consultation_result:
            # 从咨询结果中提取信息
            classification_result = consultation_result.classification_result

            # 判断是否为第一阶段（用户未确认）
            is_first_stage = not request.user_confirmed

            if is_first_stage:
                # ========== 第一阶段：返回律师助理分析结果 ==========

                # 即使 classification_result 为空，也要返回确认消息
                if classification_result:
                    primary_type = classification_result.get("primary_type", "法律咨询")
                    specialist_role = classification_result.get("specialist_role", "专业律师")
                    confidence = classification_result.get("confidence", 0.8)
                    basic_summary = classification_result.get("basic_summary", "")
                    direct_questions = classification_result.get("direct_questions", [])
                    suggested_questions = classification_result.get("suggested_questions", [])
                    recommended_approach = classification_result.get("recommended_approach", "")

                    # 构建简单的第一阶段回复（由前端展示详细结构化信息）
                    first_stage_answer = f"""根据您的问题，我识别出这属于 {primary_type} 领域，建议转交给该领域的专业律师为您提供更深入的解答。

是否同意转交专业律师进行深入分析？"""
                else:
                    # classification_result 为空时的兜底处理
                    logger.warning("[API] classification_result 为空，使用默认值")
                    primary_type = "法律咨询"
                    specialist_role = "专业律师"
                    confidence = 0.8
                    basic_summary = ""
                    direct_questions = []
                    suggested_questions = []
                    recommended_approach = ""

                    # 构建兜底的第一阶段回复
                    first_stage_answer = f"""根据您的问题，建议由专业律师为您提供更深入的法律分析和建议。

是否同意转交专业律师进行深入分析？"""

                return ConsultationResponse(
                    answer=first_stage_answer,
                    specialist_role=specialist_role,
                    primary_type=primary_type,
                    confidence=confidence,
                    relevant_laws=[],
                    need_confirmation=True,  # 标记需要确认
                    response=first_stage_answer,
                    basic_summary=basic_summary,
                    direct_questions=direct_questions,
                    suggested_questions=suggested_questions,
                    recommended_approach=recommended_approach,
                    session_id=session_id  # 返回会话ID
                )

            # ========== 第二阶段：返回完整专业律师报告 ==========

            # 【关键修改】如果是专业律师的最终回复，保存会话状态
            if final_report:
                await consultation_session_service.save_session(
                    session_id=session_id,
                    is_in_specialist_mode=True,
                    specialist_output={
                        "legal_analysis": consultation_result.analysis,
                        "legal_advice": consultation_result.advice,
                        "risk_warning": consultation_result.risk_warning,
                        "action_steps": consultation_result.action_steps
                    },
                    classification=classification_result,
                    question=request.question
                )
            logger.info(f"[API] 会话已保存: {session_id} (进入专业律师模式)")

            # 【调试】打印返回的 session_id
            logger.info(f"[API] 第二阶段响应: 将返回 session_id={session_id} 给前端")

            # 如果有分类结果，提取详细信息
            if classification_result:
                primary_type = classification_result.get("primary_type", "法律咨询")
                specialist_role = classification_result.get("specialist_role", "专业律师")
                confidence = classification_result.get("confidence", 0.8)
                urgency = classification_result.get("urgency", "medium")
                complexity = classification_result.get("complexity", "medium")
                relevant_laws = consultation_result.legal_basis.split("、") if consultation_result.legal_basis else []
            else:
                primary_type = "法律咨询"
                specialist_role = "专业律师"
                confidence = 0.8
                urgency = "medium"
                complexity = "medium"
                relevant_laws = []

            # 构建响应 - 使用用户可见的问题描述（不包含文件完整内容）
            display_question = user_visible_question if file_summaries else consultation_result.question

            # 使用工作流生成的最终报告作为回答（纯文本格式，已清理 Markdown 符号）
            if final_report:
                response_content = final_report
            else:
                # 兜底：手动构建纯文本响应
                response_content = f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                    法律咨询报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【问题描述】
{display_question}

【法律依据】
{consultation_result.legal_basis}

【分析】
{consultation_result.analysis}

【建议】
{consultation_result.advice}

【风险提醒】
{consultation_result.risk_warning}

【行动步骤】
"""
                for step in consultation_result.action_steps:
                    response_content += f"  • {step}\n"

                response_content += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"

            response_data = ConsultationResponse(
                answer=response_content,
                specialist_role=specialist_role,
                primary_type=primary_type,
                confidence=confidence,
                relevant_laws=relevant_laws,
                need_confirmation=False,  # 第二阶段：用户已确认，不需要再次确认
                response=response_content,  # 保持兼容性
                final_report=True,  # 标识为最终专业律师报告
                analysis=consultation_result.analysis,  # ConsultationOutput 使用 analysis 字段
                advice=consultation_result.advice,  # ConsultationOutput 使用 advice 字段
                risk_warning=consultation_result.risk_warning,
                action_steps=consultation_result.action_steps,
                session_id=session_id  # 返回会话ID给前端
            )

            logger.info(f"[API] 咨询完成: session_id={session_id}, is_follow_up={is_follow_up}")

            return response_data
        else:
            # 咨询失败，返回错误信息
            error_msg = final_report if isinstance(final_report, str) else "咨询失败，请稍后重试"
            raise HTTPException(status_code=500, detail=error_msg)

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"法律咨询失败：{str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"咨询失败：{str(e)}")


@router.post("/new-session")
async def create_new_session():
    """
    创建新会话（用户主动开启新对话）

    返回新的 session_id，前端使用新 session_id 发起咨询
    """
    import uuid
    new_session_id = f"session-{uuid.uuid4().hex[:16]}"

    logger.info(f"[API] 创建新会话: {new_session_id}")

    return {
        "session_id": new_session_id,
        "message": "已创建新会话"
    }


@router.post("/reset-session/{session_id}")
async def reset_session(session_id: str):
    """
    重置会话（删除现有会话状态）

    用户点击"开启新对话"时调用
    """
    from app.services.consultation_session_service import consultation_session_service

    success = await consultation_session_service.delete_session(session_id)

    if success:
        logger.info(f"[API] 会话已重置: {session_id}")
        return {"message": "会话已重置", "session_id": session_id}
    else:
        logger.warning(f"[API] 会话重置失败（会话可能不存在）: {session_id}")
        return {"message": "会话不存在或已过期", "session_id": session_id}


@router.post("/save-history")
async def save_consultation_history(request: dict):
    """
    保存对话到历史记录

    前端调用此API保存对话历史
    """
    from app.services.consultation_history_service import consultation_history_service
    from app.api.deps import get_current_user_optional

    try:
        # 尝试获取用户（可选）
        user_id = None
        try:
            from fastapi import Request
            from app.database import SessionLocal
            from app.models.user import User

            # 简化处理：如果没有token，使用默认用户
            user_id = 1  # TODO: 从JWT token中获取真实用户ID

        except Exception as e:
            logger.warning(f"[API] 无法获取用户信息，使用默认用户: {e}")
            user_id = 1

        session_id = request.get("session_id")
        messages = request.get("messages", [])
        title = request.get("title", "对话记录")
        specialist_type = request.get("specialist_type")
        classification = request.get("classification")

        if not session_id:
            raise HTTPException(status_code=400, detail="缺少session_id")

        success = await consultation_history_service.save_conversation(
            user_id=user_id,
            session_id=session_id,
            messages=messages,
            title=title,
            specialist_type=specialist_type,
            classification=classification
        )

        if success:
            logger.info(f"[API] 保存对话历史成功: {session_id}")
            return {"success": True, "message": "对话已保存到历史"}
        else:
            return {"success": False, "message": "保存失败"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] 保存对话历史异常: {e}")
        return {"success": False, "message": f"保存失败: {str(e)}"}
