# backend/app/services/unified_document_service.py
"""
统一文档处理服务

这是应用中所有文档处理的统一入口，整合了：
- DocumentPreprocessor：核心预处理功能
- MinerU：高质量PDF解析
- OCR：扫描文档识别
- AI后处理：智能清理和格式化

目标：确保所有模块都通过这个统一接口处理文档，避免代码重复。
"""

import asyncio
import hashlib
import logging
import os
import re
from typing import Dict, Any, Optional, List, Tuple, Callable, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DocumentProcessingStatus(str, Enum):
    """文档处理状态"""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"  # 部分成功（如表格提取失败但文本成功）


@dataclass
class DocumentProcessingResult:
    """文档处理结果"""
    # 处理状态
    status: DocumentProcessingStatus

    # 提取的文本内容
    content: str

    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 错误信息（如果失败）
    error: Optional[str] = None

    # 警告信息（部分成功时）
    warnings: List[str] = field(default_factory=list)

    # 处理方法（用于调试）
    processing_method: Optional[str] = None  # "mineru", "python-docx", "xml", "ocr", etc.

    # 是否来自缓存
    from_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "status": self.status.value,
            "content": self.content,
            "metadata": self.metadata,
            "error": self.error,
            "warnings": self.warnings,
            "processing_method": self.processing_method,
            "from_cache": self.from_cache
        }


@dataclass
class StructuredDocumentResult(DocumentProcessingResult):
    """
    结构化文档输出

    扩展的文档处理结果，包含文档的结构化信息：
    - 段落：文档中的段落列表
    - 表格：文档中的表格列表
    - 标题：文档中的标题层级
    - 签名：文档中的签名信息
    """
    # 结构化元素
    paragraphs: List[Dict[str, Any]] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    headings: List[Dict[str, Any]] = field(default_factory=list)
    signatures: List[str] = field(default_factory=list)
    parties: List[str] = field(default_factory=list)  # 当事人信息

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        base_dict = super().to_dict()
        base_dict.update({
            "paragraphs": self.paragraphs,
            "tables": self.tables,
            "headings": self.headings,
            "signatures": self.signatures,
            "parties": self.parties
        })
        return base_dict


class UnifiedDocumentService:
    """
    统一文档处理服务

    这是应用中所有文档处理的唯一入口点。

    职责：
    1. 提供统一的文档处理接口
    2. 自动选择最佳的处理方法（MinerU > 本地库 > 降级方案）
    3. 处理各种格式的文档（PDF、DOCX、DOC、TXT、图片等）
    4. 返回结构化的处理结果
    5. 支持缓存以提高重复文档的处理效率

    使用示例：
    ```python
    from app.services.common.unified_document_service import get_unified_document_service

    service = get_unified_document_service()
    result = service.process_document("/path/to/file.docx")

    if result.status == DocumentProcessingStatus.SUCCESS:
        print(result.content)
        print(result.metadata)
    ```
    """

    def __init__(self, enable_cache: bool = True):
        # 延迟初始化 DocumentPreprocessor
        self._preprocessor = None
        # 延迟初始化 CacheService
        self._cache_service = None
        self._enable_cache = enable_cache

    def _get_preprocessor(self):
        """获取 DocumentPreprocessor 实例"""
        if self._preprocessor is None:
            from .document_preprocessor import get_preprocessor
            self._preprocessor = get_preprocessor()
        return self._preprocessor

    def _get_cache_service(self):
        """获取缓存服务实例"""
        if self._cache_service is None and self._enable_cache:
            try:
                from .document_cache_service import get_document_cache_service
                self._cache_service = get_document_cache_service()
            except Exception as e:
                logger.warning(f"缓存服务初始化失败: {str(e)}")
                self._enable_cache = False
        return self._cache_service

    def process_document(
        self,
        file_path: str,
        extract_content: bool = True,
        extract_metadata: bool = True,
        target_format: Optional[str] = None,
        use_cache: bool = True
    ) -> DocumentProcessingResult:
        """
        统一的文档处理入口

        Args:
            file_path: 文件路径
            extract_content: 是否提取文本内容
            extract_metadata: 是否提取元数据
            target_format: 目标格式（如需要转换）
            use_cache: 是否使用缓存

        Returns:
            DocumentProcessingResult: 处理结果
        """
        if not file_path:
            return DocumentProcessingResult(
                status=DocumentProcessingStatus.FAILED,
                content="",
                error="文件路径为空"
            )

        # 检查缓存
        if use_cache and self._enable_cache:
            cache_service = self._get_cache_service()
            if cache_service:
                file_hash = self.get_file_hash(file_path)
                cached_result = cache_service.get_cached_result(file_hash)
                if cached_result:
                    logger.info(f"[UnifiedDocumentService] 使用缓存结果: {file_path}")
                    return DocumentProcessingResult(
                        status=DocumentProcessingStatus(cached_result["status"]),
                        content=cached_result["content"],
                        metadata=cached_result.get("metadata", {}),
                        error=cached_result.get("error"),
                        warnings=cached_result.get("warnings", []),
                        processing_method=cached_result.get("processing_method"),
                        from_cache=True
                    )

        preprocessor = self._get_preprocessor()

        # 验证文件
        is_valid, error_msg = preprocessor.validate_file(file_path)
        if not is_valid:
            return DocumentProcessingResult(
                status=DocumentProcessingStatus.FAILED,
                content="",
                error=error_msg
            )

        # 检测文件格式
        file_format = preprocessor.detect_format(file_path)

        try:
            content = ""
            metadata = {}
            warnings = []
            processing_method = None

            # 提取文本内容
            if extract_content:
                try:
                    content = preprocessor.extract_text(file_path)
                    if not content:
                        warnings.append("文本提取为空")
                except Exception as e:
                    logger.error(f"文本提取失败: {str(e)}")
                    warnings.append(f"文本提取失败: {str(e)}")

            # 提取元数据
            if extract_metadata:
                try:
                    metadata = preprocessor._extract_metadata(file_path)
                except Exception as e:
                    logger.warning(f"元数据提取失败: {str(e)}")
                    warnings.append(f"元数据提取失败: {str(e)}")

            # 确定处理状态
            result = None
            if not content and not metadata:
                result = DocumentProcessingResult(
                    status=DocumentProcessingStatus.FAILED,
                    content="",
                    error="文档处理失败：未能提取任何内容"
                )
            elif warnings:
                result = DocumentProcessingResult(
                    status=DocumentProcessingStatus.PARTIAL,
                    content=content,
                    metadata=metadata,
                    warnings=warnings
                )
            else:
                result = DocumentProcessingResult(
                    status=DocumentProcessingStatus.SUCCESS,
                    content=content,
                    metadata=metadata
                )

            # 缓存成功的处理结果
            if result.status != DocumentProcessingStatus.FAILED and use_cache and self._enable_cache:
                cache_service = self._get_cache_service()
                if cache_service:
                    file_hash = self.get_file_hash(file_path)
                    cache_service.cache_result(file_hash, result)

            return result

        except Exception as e:
            logger.error(f"文档处理异常: {str(e)}", exc_info=True)
            return DocumentProcessingResult(
                status=DocumentProcessingStatus.FAILED,
                content="",
                error=f"文档处理异常: {str(e)}"
            )

    def extract_text(self, file_path: str) -> Tuple[bool, str, Optional[str]]:
        """
        提取文档文本（兼容旧接口）

        Args:
            file_path: 文件路径

        Returns:
            (是否成功, 文本内容, 错误信息)
        """
        result = self.process_document(file_path, extract_content=True, extract_metadata=False)

        if result.status == DocumentProcessingStatus.SUCCESS:
            return True, result.content, None
        elif result.status == DocumentProcessingStatus.PARTIAL and result.content:
            return True, result.content, "; ".join(result.warnings)
        else:
            return False, "", result.error

    def convert_to_markdown(self, file_path: str) -> str:
        """
        将文档转换为 Markdown 格式（兼容旧接口）

        Args:
            file_path: 文件路径

        Returns:
            Markdown 文本
        """
        result = self.process_document(file_path, extract_content=True)
        return result.content

    def batch_process(
        self,
        file_paths: List[str],
        extract_content: bool = True,
        extract_metadata: bool = False
    ) -> List[DocumentProcessingResult]:
        """
        批量处理文档

        Args:
            file_paths: 文件路径列表
            extract_content: 是否提取文本内容
            extract_metadata: 是否提取元数据

        Returns:
            处理结果列表
        """
        results = []

        for file_path in file_paths:
            result = self.process_document(
                file_path,
                extract_content=extract_content,
                extract_metadata=extract_metadata
            )
            results.append(result)

        return results

    def process_document_structured(
        self,
        file_path: str,
        extract_structure: bool = True
    ) -> StructuredDocumentResult:
        """
        处理文档并返回结构化结果

        这个方法扩展了标准的 process_document 方法，额外提取：
        - 段落：文档中的段落列表（包含文本、位置、类型）
        - 表格：文档中的表格列表（包含行列数据）
        - 标题：文档中的标题层级（H1, H2, H3）
        - 签名：文档中的签名信息
        - 当事人：文档中的当事人信息

        Args:
            file_path: 文件路径
            extract_structure: 是否提取结构化信息

        Returns:
            StructuredDocumentResult: 包含结构化信息的处理结果
        """
        # 首先进行标准处理
        base_result = self.process_document(
            file_path,
            extract_content=True,
            extract_metadata=True
        )

        # 创建结构化结果
        result = StructuredDocumentResult(
            status=base_result.status,
            content=base_result.content,
            metadata=base_result.metadata,
            error=base_result.error,
            warnings=base_result.warnings,
            processing_method=base_result.processing_method,
            from_cache=base_result.from_cache
        )

        if not extract_structure or result.status != DocumentProcessingStatus.SUCCESS:
            return result

        # 提取结构化信息
        try:
            result.paragraphs = self._extract_paragraphs(result.content)
            result.headings = self._extract_headings(result.content)
            result.tables = self._extract_tables(result.content)
            result.signatures = self._extract_signatures(result.content)
            result.parties = self._extract_parties(result.content)

            # 更新元数据
            result.metadata.update({
                "paragraph_count": len(result.paragraphs),
                "heading_count": len(result.headings),
                "table_count": len(result.tables),
                "signature_count": len(result.signatures),
                "party_count": len(result.parties)
            })

        except Exception as e:
            logger.warning(f"结构化提取失败: {str(e)}")
            result.warnings.append(f"结构化提取失败: {str(e)}")

        return result

    def _extract_paragraphs(self, content: str) -> List[Dict[str, Any]]:
        """从文档内容中提取段落"""
        paragraphs = []

        # 按双换行符分割段落
        raw_paragraphs = re.split(r'\n\s*\n', content.strip())

        for idx, para in enumerate(raw_paragraphs):
            para = para.strip()
            if not para:
                continue

            # 判断段落类型
            para_type = "normal"
            if re.match(r'^第[一二三四五六七八九十百千]+[条章节]', para):
                para_type = "article"
            elif re.match(r'^[一二三四五六七八九十百千]+[、.]', para):
                para_type = "list_item"
            elif len(para) < 50 and para.endswith('：'):
                para_type = "subtitle"

            paragraphs.append({
                "index": idx,
                "text": para,
                "type": para_type,
                "length": len(para),
                "word_count": len(para.split())
            })

        return paragraphs

    def _extract_headings(self, content: str) -> List[Dict[str, Any]]:
        """从文档内容中提取标题层级"""
        headings = []

        # 匹配常见的标题模式
        patterns = [
            (r'^(第[一二三四五六七八九十百千]+[章节篇])\s*(.*)', 1, 'chapter'),
            (r'^([一二三四五六七八九十百千]+、)\s*(.*)', 2, 'section'),
            (r'^(\d+\.)\s*(.+)', 3, 'numbered'),
            (r'^(【(.*)】)', 1, 'bracket'),
        ]

        for pattern, level, heading_type in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                title = match.group(2) if match.lastindex >= 2 else match.group(1)
                headings.append({
                    "level": level,
                    "type": heading_type,
                    "title": title.strip(),
                    "position": match.start()
                })

        # 按位置排序
        headings.sort(key=lambda x: x["position"])

        return headings

    def _extract_tables(self, content: str) -> List[Dict[str, Any]]:
        """从文档内容中提取表格（简化版）"""
        tables = []

        # 查找 Markdown 表格格式
        table_pattern = r'\|.+?\|[\r\n]+\|[-:\s|]+\|[\r\n]+((?:\|.+?\|[\r\n]*)+)'
        matches = re.finditer(table_pattern, content, re.MULTILINE)

        for idx, match in enumerate(matches):
            table_text = match.group(0)
            lines = [line.strip() for line in table_text.split('\n') if line.strip()]

            if len(lines) < 2:
                continue

            # 解析表头
            headers = [h.strip() for h in lines[0].split('|') if h.strip()]

            # 解析数据行（跳过分隔行）
            rows = []
            for line in lines[2:]:  # 跳过表头和分隔行
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if cells:
                    rows.append(cells)

            tables.append({
                "index": idx,
                "headers": headers,
                "row_count": len(rows),
                "col_count": len(headers),
                "rows": rows[:10]  # 限制返回的行数
            })

        return tables

    def _extract_signatures(self, content: str) -> List[str]:
        """从文档内容中提取签名信息"""
        signatures = []

        # 常见签名模式
        patterns = [
            r'(甲方[：:]\s*.*?(?:签字|盖章|授权代表)?[：:].*?(?=\n|$))',
            r'(乙方[：:]\s*.*?(?:签字|盖章|授权代表)?[：:].*?(?=\n|$))',
            r'(法定代表人[：:].*?(?=\n|$))',
            r'(委托代理人[：:].*?(?=\n|$))',
            r'(签字[：:].*?(?=\n|$))',
            r'(盖章[：:].*?(?=\n|$))',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            signatures.extend(matches)

        # 去重并返回
        return list(set(signatures))

    def _extract_parties(self, content: str) -> List[str]:
        """从文档内容中提取当事人信息"""
        parties = []

        # 当事人模式
        patterns = [
            r'甲方[：:]\s*([^、\n]{2,20})',
            r'乙方[：:]\s*([^、\n]{2,20})',
            r'申请人[：:]\s*([^、\n]{2,20})',
            r'被申请人[：:]\s*([^、\n]{2,20})',
            r'原告[：:]\s*([^、\n]{2,20})',
            r'被告[：:]\s*([^、\n]{2,20})',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, content)
            parties.extend(matches)

        # 去重并返回
        return list(set(parties))

    async def process_document_async(
        self,
        file_path: str,
        extract_content: bool = True,
        extract_metadata: bool = True,
        target_format: Optional[str] = None
    ) -> DocumentProcessingResult:
        """
        异步处理文档

        Args:
            file_path: 文件路径
            extract_content: 是否提取文本内容
            extract_metadata: 是否提取元数据
            target_format: 目标格式（如需要转换）

        Returns:
            DocumentProcessingResult: 处理结果
        """
        # 在线程池中执行同步操作
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self.process_document(
                file_path,
                extract_content=extract_content,
                extract_metadata=extract_metadata,
                target_format=target_format
            )
        )
        return result

    async def batch_process_async(
        self,
        file_paths: List[str],
        extract_content: bool = True,
        extract_metadata: bool = False,
        max_concurrent: int = 3
    ) -> List[DocumentProcessingResult]:
        """
        异步批量处理文档

        Args:
            file_paths: 文件路径列表
            extract_content: 是否提取文本内容
            extract_metadata: 是否提取元数据
            max_concurrent: 最大并发数

        Returns:
            处理结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_with_semaphore(file_path: str) -> DocumentProcessingResult:
            async with semaphore:
                return await self.process_document_async(
                    file_path,
                    extract_content=extract_content,
                    extract_metadata=extract_metadata
                )

        tasks = [process_with_semaphore(fp) for fp in file_paths]
        return await asyncio.gather(*tasks)

    def get_file_hash(self, file_path: str) -> str:
        """
        计算文件的哈希值（用于缓存）

        Args:
            file_path: 文件路径

        Returns:
            文件的 MD5 哈希值
        """
        md5_hash = hashlib.md5()

        try:
            with open(file_path, 'rb') as f:
                # 分块读取文件以处理大文件
                for chunk in iter(lambda: f.read(4096), b""):
                    md5_hash.update(chunk)

            # 包含文件大小和修改时间以增加哈希的唯一性
            file_stat = os.stat(file_path)
            hash_input = f"{md5_hash.hexdigest()}_{file_stat.st_size}_{file_stat.st_mtime}"

            return hashlib.md5(hash_input.encode()).hexdigest()

        except Exception as e:
            logger.error(f"计算文件哈希失败: {str(e)}")
            return ""

    def validate_document(self, file_path: str) -> Tuple[bool, str]:
        """
        验证文档有效性

        Args:
            file_path: 文件路径

        Returns:
            (是否有效, 错误信息)
        """
        preprocessor = self._get_preprocessor()
        return preprocessor.validate_file(file_path)

    def detect_format(self, file_path: str) -> str:
        """
        检测文档格式

        Args:
            file_path: 文件路径

        Returns:
            文档格式（如 "docx", "pdf"）
        """
        preprocessor = self._get_preprocessor()
        return preprocessor.detect_format(file_path).value

    def is_available(self) -> bool:
        """
        检查服务是否可用

        Returns:
            是否可用
        """
        try:
            preprocessor = self._get_preprocessor()
            return preprocessor is not None
        except Exception:
            return False


# ==================== 单例模式 ====================

_unified_document_service_instance: Optional[UnifiedDocumentService] = None


def get_unified_document_service() -> UnifiedDocumentService:
    """
    获取统一文档服务单例

    Returns:
        UnifiedDocumentService 实例
    """
    global _unified_document_service_instance

    if _unified_document_service_instance is None:
        _unified_document_service_instance = UnifiedDocumentService()
        logger.info("[UnifiedDocumentService] 统一文档服务初始化完成")

    return _unified_document_service_instance


# ==================== 兼容旧接口的便捷函数 ====================

def extract_text_from_document(file_path: str) -> Tuple[bool, str, Optional[str]]:
    """
    从文档提取文本（便捷函数，兼容旧接口）

    Args:
        file_path: 文件路径

    Returns:
        (是否成功, 文本内容, 错误信息)
    """
    service = get_unified_document_service()
    return service.extract_text(file_path)


def convert_document_to_markdown(file_path: str) -> str:
    """
    将文档转换为 Markdown（便捷函数，兼容旧接口）

    Args:
        file_path: 文件路径

    Returns:
        Markdown 文本
    """
    service = get_unified_document_service()
    return service.convert_to_markdown(file_path)


def validate_document_file(file_path: str) -> Tuple[bool, str]:
    """
    验证文档文件（便捷函数）

    Args:
        file_path: 文件路径

    Returns:
        (是否有效, 错误信息)
    """
    service = get_unified_document_service()
    return service.validate_document(file_path)
