# backend/app/api/consultation_router.py
"""
智能咨询 API 路由
提供智能咨询文件上传和咨询服务
"""

from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import uuid
import os
import asyncio
import logging
from app.api.deps import get_current_user_optional

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
    # P0-4: 动态人设字段
    persona_definition: Optional[Dict[str, Any]] = None  # 专家人设定义
    strategic_focus: Optional[Dict[str, Any]] = None  # 战略分析重点
    # P1-2/P1-3: RAG 检索状态和结果
    rag_triggered: Optional[bool] = None  # 是否触发了RAG检索
    rag_sources: Optional[List[str]] = None  # RAG来源列表
    # 【新增】UI 行为控制字段
    ui_action: Optional[str] = None  # "show_confirmation" | "chat_only" | "async_processing" | None
    # 【新增】Celery任务ID（用于轮询）
    task_id: Optional[str] = None


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


@router.get("/session/{session_id}/validate")
async def validate_session_endpoint(session_id: str):
    """
    验证会话是否有效

    返回会话的有效性和状态信息
    """
    from app.services.consultation.session_service import consultation_session_service

    try:
        is_valid = await consultation_session_service.validate_session(session_id)

        session_data = None
        if is_valid:
            session_data = await consultation_session_service.get_session(session_id)

        return {
            "valid": is_valid,
            "session_id": session_id,
            "status": session_data.get("status") if session_data else None,
            "current_phase": session_data.get("current_phase") if session_data else None,
            "is_in_specialist_mode": session_data.get("is_in_specialist_mode") if session_data else None,
            "updated_at": session_data.get("updated_at") if session_data else None
        }

    except Exception as e:
        logger.error(f"[API] 验证会话失败: {e}")
        return {"valid": False}


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
    from app.services.consultation.session_service import consultation_session_service

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

    # 【修改】改为Celery异步任务模式，与HTTP请求解耦
    try:
        from app.tasks.consultation_tasks import task_run_consultation

        # 1. 立即初始化会话（保存用户输入）
        from app.services.consultation.session_service import consultation_session_service
        await consultation_session_service.initialize_session(session_id, request.question, user_id=1)

        # 【加固】路由逻辑粘性化：检查会话状态中的 user_decision
        # 【修复】只在会话已存在且已进入专家模式时才启用路由粘性化
        # 这样可以区分"用户确认阶段"和"真正的后续追问"
        is_sticky_route = False
        try:
            session_data = await consultation_session_service.get_session(session_id)
            if session_data:
                user_decision = session_data.get('user_decision')
                is_in_specialist_mode = session_data.get('is_in_specialist_mode')
                current_phase = session_data.get('current_phase')

                # 【新增】严格条件：必须同时满足以下条件才启用路由粘性化
                # 1. 用户已确认
                # 2. 已进入专家模式
                # 3. 会话处于活跃状态
                # 4. 问题在短时间内（防止重启后误判）

                if (user_decision == 'confirmed' and
                    is_in_specialist_mode and
                    current_phase in ['specialist', 'completed'] and
                    request.reset_session == False):

                    # 【新增】时间窗口检查
                    updated_at = session_data.get('updated_at')
                    if updated_at:
                        from datetime import datetime, timedelta
                        try:
                            updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                            # 30分钟内才启用路由粘性化
                            if datetime.now() - updated_time <= timedelta(minutes=30):
                                is_sticky_route = True
                                logger.info(f"[API] 路由粘性化：30分钟内专家模式，保持专家对话")
                        except Exception as e:
                            logger.warning(f"[API] 时间解析失败，不启用路由粘性化: {e}")

            # 如果启用路由粘性化
            if is_sticky_route:
                logger.info(f"[API] 路由粘性化启用：检测到近期专家模式，保持专家对话")
                request.user_confirmed = True

                # 【修复】重置输出缓存：清空 specialist_output，避免追问时返回相同内容
                # 将 current_phase 设为 'specialist'，清空 specialist_output 字段
                # 严禁修改 messages 历史
                logger.info(f"[API] 重置输出缓存：清空 specialist_output，设置 current_phase=specialist")
                await consultation_session_service.update_session(
                    session_id=session_id,
                    current_phase="specialist",
                    specialist_output=None,  # 清空上一轮输出
                    is_in_specialist_mode=True   # 保持专家模式
                )
        except Exception as e:
            logger.error(f"[API] 路由粘性化检查失败: {e}")
            # 继续执行，不阻止请求处理

        # 【修复】如果用户已确认，立即设置会话为专业律师阶段
        # 这样前端轮询时就不会误认为还在 waiting_confirmation
        if request.user_confirmed:
            logger.info(f"[API] 用户确认阶段：立即设置 current_phase=specialist")
            await consultation_session_service.update_session(
                session_id=session_id,
                current_phase="specialist",
                user_decision="confirmed"
            )

        # 2. 启动Celery后台任务
        task = task_run_consultation.delay(
            session_id=session_id,
            question=request.question,
            context=enhanced_context,
            user_id=1,
            user_confirmed=request.user_confirmed or False,
            selected_suggested_questions=request.selected_suggested_questions,
            previous_specialist_output=previous_output,
            saved_classification=saved_classification
        )

        logger.info(f"[API] Celery任务已启动: task_id={task.id}")

        # 3. 返回异步响应（前端通过轮询获取结果）
        return ConsultationResponse(
            answer="正在分析您的问题，请稍候...",
            session_id=session_id,
            response="正在分析您的问题，请稍候...",
            need_confirmation=False,
            ui_action="async_processing",
            task_id=task.id  # 返回task_id供前端轮询
        )

    except Exception as e:
        logger.error(f"[API] 启动Celery任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动咨询任务失败: {str(e)}")


@router.get("/task-status/{session_id}")
async def get_task_status(session_id: str):
    """
    获取异步任务状态

    返回任务的当前状态和结果（如果已完成）
    """
    try:
        from app.services.consultation.session_service import consultation_session_service

        # 获取会话数据
        session_data = await consultation_session_service.get_session(session_id)

        if not session_data:
            raise HTTPException(status_code=404, detail="会话会不存在")

        # 提取会话状态信息
        current_phase = session_data.get("current_phase", "initial")
        status = session_data.get("status", "processing")
        classification = session_data.get("classification")
        specialist_output = session_data.get("specialist_output")
        last_question = session_data.get("last_question", "")
        user_decision = session_data.get("user_decision")

        # 【新增】调试日志
        logger.info(f"[API] 任务状态查询: session_id={session_id}")
        logger.info(f"[API] - current_phase={current_phase}, user_decision={user_decision}, status={status}")
        logger.info(f"[API] - classification存在={bool(classification)}")
        if classification:
            logger.info(f"[API] - primary_type={classification.get('primary_type')}")
            logger.info(f"[API] - specialist_role={classification.get('specialist_role')}")
            logger.info(f"[API] - persona_definition存在={bool(classification.get('persona_definition'))}")
            logger.info(f"[API] - strategic_focus存在={bool(classification.get('strategic_focus'))}")

        # 根据当前阶段返回不同状态
        if current_phase == "initial" or status == "running":
            # 任务仍在处理中
            return {
                "status": "processing",
                "current_phase": current_phase,
                "session_id": session_id
            }
        elif current_phase == "waiting_confirmation" and user_decision != "cancelled":
            # 助理节点完成，等待用户确认
            return {
                "status": "waiting_confirmation",
                "current_phase": current_phase,
                "session_id": session_id,
                "primary_type": classification.get('primary_type', '未知领域') if classification else '未知领域',
                "specialist_role": classification.get('specialist_role', '专业律师') if classification else '专业律师',
                "suggested_questions": classification.get('suggested_questions', []) if classification else [],
                "direct_questions": classification.get('direct_questions', []) if classification else [],
                "basic_summary": classification.get('basic_summary', '') if classification else '',
                "recommended_approach": classification.get('recommended_approach', '') if classification else '',
                # 【新增】人设和战略信息
                "persona_definition": classification.get('persona_definition', {}) if classification else {},
                "strategic_focus": classification.get('strategic_focus', {}) if classification else {}
            }
        elif current_phase in ["specialist", "completed"] and specialist_output:
            # 任务完成，返回完整结果
            return {
                "status": "completed",
                "current_phase": current_phase,
                "result": {
                    "response": specialist_output.get('legal_analysis', ''),
                    "answer": specialist_output.get('legal_advice', ''),
                    "final_report": True,
                    "confidence": specialist_output.get('confidence', 0.95),
                    "suggestions": [
                        "相关法规查询", 
                        "风险评估", 
                        "文书起草"
                    ],
                    "action_buttons": [
                        {"key": "risk_analysis", "label": "风险评估"},
                        {"key": "contract_review", "label": "合同审查"}
                    ],
                    "analysis": specialist_output.get('legal_analysis', ''),
                    "advice": specialist_output.get('legal_advice', ''),
                    "risk_warning": specialist_output.get('risk_warning', ''),
                    "action_steps": specialist_output.get('action_steps', [])
                },
                "session_id": session_id
            }
        elif current_phase == "assistant" and user_decision == "cancelled":
            # 用户已取消转交专家
            return {
                "status": "cancelled",
                "current_phase": current_phase,
                "session_id": session_id,
                "message": "用户已取消转交专家律师"
            }
        else:
            # 未知状态
            return {
                "status": "unknown",
                "current_phase": current_phase,
                "session_id": session_id
            }
            
    except Exception as e:
        logger.error(f"[API] 获取任务状态失败: {e}")
        raise HTTPException(status_code=500, detail="获取任务状态失败")


@router.post("/{session_id}/continue", response_model=ConsultationResponse)
async def continue_consultation_session(
    session_id: str,
    request: ConsultationRequest,
    current_user = Depends(get_current_user_optional)
):
    """
    继续历史会话（页面关闭后恢复对话）

    批准条件：前端可实现轮询恢复机制（页面关闭后可继续对话）
    """
    from app.services.consultation.session_service import consultation_session_service
    from app.tasks.consultation_tasks import task_run_consultation

    user_id = current_user.id if current_user else 1

    # 1. 验证会话存在
    session_data = await consultation_session_service.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 获取之前的输出（用于多轮对话）
    previous_output = await consultation_session_service.get_specialist_output(session_id)
    saved_classification = await consultation_session_service.get_classification(session_id)

    logger.info(f"[API] 继续会话: {session_id}, previous_output_exists={bool(previous_output)}")

    # 3. 启动新的Celery任务（带上下文）
    try:
        task = task_run_consultation.delay(
            session_id=session_id,
            question=request.question,
            context=request.context or {},
            user_id=user_id,
            user_confirmed=True,  # 继续会话时，直接进入专业律师模式
            selected_suggested_questions=None,
            previous_specialist_output=previous_output,
            saved_classification=saved_classification
        )

        logger.info(f"[API] 继续会话任务已启动: task_id={task.id}")

        return ConsultationResponse(
            answer="正在继续分析您的问题...",
            session_id=session_id,
            response="正在继续分析您的问题...",
            need_confirmation=False,
            ui_action="async_processing",
            task_id=task.id
        )

    except Exception as e:
        logger.error(f"[API] 启动继续会话任务失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


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
    from app.services.consultation.session_service import consultation_session_service

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


# ==================== 【新增】会话决策管理 API ====================

class ConsultationDecisionRequest(BaseModel):
    """用户决策请求模型"""
    action: str  # "confirm" | "cancel"
    selected_suggested_questions: Optional[List[str]] = None  # 用户选择的建议问题
    custom_question: Optional[str] = None  # 用户自定义问题


@router.post("/{session_id}/decision")
async def handle_consultation_decision(
    session_id: str,
    request: ConsultationDecisionRequest,
    current_user = Depends(get_current_user_optional)
):
    """
    处理用户对律师助理分析结果的决策（确认转交专家律师 / 取消转交）

    场景A（确认）：
    - 用户点击"转交专家律师"
    - 启动专业律师任务
    - 更新会话状态为 specialist
    - 返回新任务ID供前端轮询

    场景B（取消）：
    - 用户点击"取消"
    - 标记会话为 cancelled
    - 保存到历史记录
    - 返回取消状态

    批准条件：会话生命周期管理优化
    """
    user_id = current_user.id if current_user else 1

    from app.services.consultation.session_service import consultation_session_service
    from app.tasks.consultation_tasks import task_run_consultation

    logger.info(f"[API] 收到用户决策: session_id={session_id}, action={request.action}")

    # 1. 验证会话存在且状态正确
    session_data = await consultation_session_service.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="会话不存在")

    current_phase = session_data.get("current_phase", "initial")

    # 验证会话处于等待确认状态
    if current_phase != "waiting_confirmation":
        logger.warning(f"[API] 会话阶段错误: {current_phase}, 期望: waiting_confirmation")
        raise HTTPException(
            status_code=400,
            detail=f"当前会话阶段不允许此操作。当前阶段: {current_phase}"
        )

    # 2. 根据用户决策处理
    if request.action == "confirm":
        # ========== 场景A：用户确认转交专家律师 ==========

        # 2.1 获取分类结果（从第一阶段任务）
        classification = await consultation_session_service.get_classification(session_id)
        if not classification:
            raise HTTPException(status_code=404, detail="未找到分类结果")

        # 2.2 获取用户原始问题
        last_question = session_data.get("last_question")
        if not last_question:
            raise HTTPException(status_code=404, detail="未找到原始问题")

        # 2.3 合并用户选择的问题
        selected_questions = request.selected_suggested_questions or []
        if request.custom_question:
            selected_questions.append(request.custom_question)

        logger.info(f"[API] 用户确认转交专家，补充问题: {len(selected_questions)} 个")

        # 2.4 更新会话状态（从 waiting_confirmation → specialist）
        await consultation_session_service.update_session(
            session_id=session_id,
            current_phase="specialist",
            user_decision="confirmed",
            status="running"
        )

        # 2.5 启动专业律师 Celery 任务
        try:
            task = task_run_consultation.delay(
                session_id=session_id,
                question=last_question,
                context={},
                user_id=user_id,
                user_confirmed=True,  # 程序确认
                selected_suggested_questions=selected_questions if selected_questions else None,
                previous_specialist_output=None,
                saved_classification=classification
            )

            logger.info(f"[API] 专业律师任务已启动: task_id={task.id}")

            return {
                "success": True,
                "session_id": session_id,
                "action": "confirm",
                "next_phase": "specialist",
                "new_task_id": task.id,
                "status": "processing",
                "message": "已转交专业律师进行分析"
            }

        except Exception as e:
            logger.error(f"[API] 启动专业律师任务失败: {e}")
            raise HTTPException(status_code=500, detail=f"启动专家分析失败: {str(e)}")

    elif request.action == "cancel":
        # ========== 场景B：用户取消转交 ==========

        logger.info(f"[API] 用户取消转交专家，会话将归档")

        # 3.1 更新会话状态为 cancelled
        await consultation_session_service.update_session(
            session_id=session_id,
            current_phase="assistant",
            user_decision="cancelled",
            status="archived"  # 归档（保留历史记录）
        )

        # 3.2 保存到历史记录（如果尚未保存）
        classification = await consultation_session_service.get_classification(session_id)
        last_question = session_data.get("last_question")

        if classification and last_question:
            # 构建简短的历史记录消息
            message_content = f"【问题】\n{last_question}\n\n【分析结果】\n属于【{classification.get('primary_type', '未知领域')}】领域"
            if classification.get('specialist_role'):
                message_content += f"，建议由【{classification.get('specialist_role')}】处理"

            # 注意：这里只是记录，不会触发实际转交
            # 会话状态已标记为 archived 和 cancelled

            logger.info(f"[API] 会话已归档: {session_id}")

        return {
            "success": True,
            "session_id": session_id,
            "action": "cancel",
            "status": "cancelled",
            "saved_to_history": True,
            "message": "已取消转交，您可以继续提问或开启新对话"
        }

    else:
        raise HTTPException(status_code=400, detail=f"不支持的决策操作: {request.action}")
