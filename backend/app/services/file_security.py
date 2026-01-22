# backend/app/services/file_security.py
"""
文件上传安全验证服务
"""
import os
import hashlib
import logging
from typing import List, Optional, Tuple
from pathlib import Path
from fastapi import UploadFile, HTTPException
from PIL import Image
import PyPDF2
import python_multipart

from ..core.config import settings
from ..core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# 尝试导入 python-magic（用于 MIME 类型检测）
# 如果不可用，将使用文件扩展名和文件头验证作为替代方案
try:
    import magic
    HAS_MAGIC = True
    logger.info("[FileSecurity] python-magic 可用，启用 MIME 类型检测")
except ImportError:
    HAS_MAGIC = False
    logger.warning("[FileSecurity] python-magic 不可用，将使用文件扩展名和文件头验证")

class FileSecurityValidator:
    """文件安全验证器"""

    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {
        # 文档类型
        "pdf", "doc", "docx", "txt", "rtf",
        "odt", "xls", "xlsx", "ppt", "pptx",
        "html", "htm", "md",

        # 图片类型
        "jpg", "jpeg", "png", "gif", "bmp", "webp",

        # 压缩文件
        "zip", "rar", "7z", "tar", "gz"
    }

    # 危险的文件扩展名（禁止上传）
    DANGEROUS_EXTENSIONS = {
        "exe", "bat", "cmd", "com", "pif", "scr", "vbs", "js", "jar",
        "app", "deb", "pkg", "dmg", "msi", "php", "asp", "aspx", "jsp",
        "sh", "ps1", "py", "pl", "rb", "lua", "sql", "bat", "cmd"
    }

    # 允许的 MIME 类型
    ALLOWED_MIME_TYPES = {
        # 应用程序
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
        "application/x-rar-compressed",
        "application/x-7z-compressed",
        "application/x-tar",
        "application/gzip",

        # 文本
        "text/plain",
        "text/html",
        "text/css",
        "text/javascript",
        "text/markdown",
        "text/rtf",
        "application/rtf",

        # 图片
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/bmp",
        "image/webp",

        # 其他
        "application/octet-stream"
    }

    # 最大文件大小（字节）- 默认 50MB
    MAX_FILE_SIZE = 50 * 1024 * 1024

    # 最大图片尺寸（像素）
    MAX_IMAGE_DIMENSIONS = (10000, 10000)

    # 最小图片尺寸（像素）
    MIN_IMAGE_DIMENSIONS = (1, 1)

    def __init__(self):
        """初始化文件安全验证器"""
        self.max_file_size = getattr(settings, 'MAX_UPLOAD_SIZE', self.MAX_FILE_SIZE)

    async def validate_file(self, file: UploadFile) -> Tuple[bool, Optional[str]]:
        """
        验证上传的文件

        Args:
            file: 上传的文件对象

        Returns:
            (是否通过验证, 错误信息)
        """
        try:
            # 1. 检查文件名
            if not file.filename:
                return False, "文件名不能为空"

            # 2. 检查文件大小
            if hasattr(file, 'size') and file.size:
                if file.size > self.max_file_size:
                    return False, f"文件大小超过限制 ({self.max_file_size // (1024*1024)}MB)"

            # 3. 检查文件扩展名
            ext_validation = self._validate_extension(file.filename)
            if not ext_validation[0]:
                return ext_validation

            # 4. 读取并验证文件内容
            file_content = await file.read()

            # 重置文件指针，以便后续使用
            await file.seek(0)

            # 5. 验证文件大小（基于实际内容）
            if len(file_content) > self.max_file_size:
                return False, f"文件大小超过限制 ({self.max_file_size // (1024*1024)}MB)"

            # 6. 验证 MIME 类型
            mime_validation = self._validate_mime_type(file_content)
            if not mime_validation[0]:
                return mime_validation

            # 7. 验证文件头（魔法数字）
            header_validation = self._validate_file_header(file_content, file.filename)
            if not header_validation[0]:
                return header_validation

            # 8. 特定文件类型的深度验证
            deep_validation = self._deep_validate_file(file_content, file.filename)
            if not deep_validation[0]:
                return deep_validation

            # 9. 扫描恶意内容
            malware_scan = self._scan_for_malware(file_content)
            if not malware_scan[0]:
                return malware_scan

            return True, None

        except Exception as e:
            logger.error(f"文件验证过程中发生错误: {e}")
            return False, "文件验证失败"

    def _validate_extension(self, filename: str) -> Tuple[bool, Optional[str]]:
        """验证文件扩展名"""
        ext = Path(filename).suffix.lower().lstrip('.')

        # 检查是否为危险扩展名
        if ext in self.DANGEROUS_EXTENSIONS:
            return False, f"不允许上传 {ext} 类型的文件"

        # 检查是否为允许的扩展名
        if ext not in self.ALLOWED_EXTENSIONS:
            allowed_str = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
            return False, f"只允许上传以下类型的文件: {allowed_str}"

        return True, None

    def _validate_mime_type(self, file_content: bytes) -> Tuple[bool, Optional[str]]:
        """验证 MIME 类型"""
        if not HAS_MAGIC:
            # python-magic 不可用，跳过 MIME 类型验证
            # 将依赖文件扩展名验证和文件头验证
            return True, None

        try:
            mime_type = magic.from_buffer(file_content, mime=True)

            if mime_type not in self.ALLOWED_MIME_TYPES:
                return False, f"不支持的文件类型: {mime_type}"

            return True, None

        except Exception as e:
            logger.error(f"MIME 类型检测失败: {e}")
            return False, "无法检测文件类型"

    def _validate_file_header(self, file_content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
        """验证文件头（魔法数字）"""
        try:
            ext = Path(filename).suffix.lower().lstrip('.')

            # 定义常见文件类型的魔法数字
            file_signatures = {
                'pdf': [b'%PDF'],
                'doc': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],
                'docx': [b'PK\x03\x04'],
                'xls': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],
                'xlsx': [b'PK\x03\x04'],
                'ppt': [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'],
                'pptx': [b'PK\x03\x04'],
                'zip': [b'PK\x03\x04', b'PK\x05\x06', b'PK\x07\x08'],
                'rar': [b'Rar!\x1a\x07\x00'],
                'jpg': [b'\xff\xd8\xff'],
                'jpeg': [b'\xff\xd8\xff'],
                'png': [b'\x89PNG\r\n\x1a\n'],
                'gif': [b'GIF87a', b'GIF89a'],
                'bmp': [b'BM'],
            }

            if ext in file_signatures:
                file_header = file_content[:16]  # 读取前16字节
                valid_signatures = file_signatures[ext]

                signature_match = any(
                    file_header.startswith(signature)
                    for signature in valid_signatures
                )

                if not signature_match:
                    return False, f"文件头与扩展名不匹配，可能不是真正的 {ext} 文件"

            return True, None

        except Exception as e:
            logger.error(f"文件头验证失败: {e}")
            return True, None  # 验证失败时不阻止上传，但记录日志

    def _deep_validate_file(self, file_content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
        """深度验证特定文件类型"""
        try:
            ext = Path(filename).suffix.lower().lstrip('.')

            if ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp']:
                return self._validate_image(file_content)
            elif ext == 'pdf':
                return self._validate_pdf(file_content)

            return True, None

        except Exception as e:
            logger.error(f"深度文件验证失败: {e}")
            return True, None

    def _validate_image(self, file_content: bytes) -> Tuple[bool, Optional[str]]:
        """验证图片文件"""
        try:
            # 使用 PIL 验证图片
            from io import BytesIO
            img = Image.open(BytesIO(file_content))

            # 检查图片尺寸
            width, height = img.size
            if width > self.MAX_IMAGE_DIMENSIONS[0] or height > self.MAX_IMAGE_DIMENSIONS[1]:
                return False, f"图片尺寸过大，最大允许 {self.MAX_IMAGE_DIMENSIONS[0]}x{self.MAX_IMAGE_DIMENSIONS[1]}"

            if width < self.MIN_IMAGE_DIMENSIONS[0] or height < self.MIN_IMAGE_DIMENSIONS[1]:
                return False, f"图片尺寸过小，最小允许 {self.MIN_IMAGE_DIMENSIONS[0]}x{self.MIN_IMAGE_DIMENSIONS[1]}"

            # 验证图片完整性
            img.verify()

            return True, None

        except Exception as e:
            logger.error(f"图片验证失败: {e}")
            return False, "图片文件损坏或格式不正确"

    def _validate_pdf(self, file_content: bytes) -> Tuple[bool, Optional[str]]:
        """验证 PDF 文件"""
        try:
            from io import BytesIO
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))

            # 检查 PDF 页面数
            if len(pdf_reader.pages) > 1000:  # 限制最大1000页
                return False, "PDF 页面数过多，最大允许 1000 页"

            # 检查是否加密
            if pdf_reader.is_encrypted:
                return False, "不支持加密的 PDF 文件"

            return True, None

        except Exception as e:
            logger.error(f"PDF 验证失败: {e}")
            return False, "PDF 文件损坏或格式不正确"

    def _scan_for_malware(self, file_content: bytes) -> Tuple[bool, Optional[str]]:
        """扫描恶意内容"""
        try:
            # 简单的恶意代码检测（基于关键词）
            suspicious_patterns = [
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'data:text/html',
                b'<?php',
                b'<%',
                b'eval(',
                b'exec(',
                b'system(',
                b'shell_exec(',
                b'passthru(',
                b'base64_decode',
            ]

            content_lower = file_content.lower()
            for pattern in suspicious_patterns:
                if pattern in content_lower:
                    logger.warning(f"发现可疑内容: {pattern.decode('utf-8', errors='ignore')}")
                    return False, "文件包含可疑或恶意内容"

            # 检查是否包含可执行文件的特征
            executable_signatures = [
                b'MZ\x90\x00',  # PE 文件
                b'\x7fELF',    # ELF 文件
                b'\xca\xfe\xba\xbe',  # Java class 文件
            ]

            for signature in executable_signatures:
                if signature in file_content:
                    return False, "文件包含可执行代码"

            return True, None

        except Exception as e:
            logger.error(f"恶意内容扫描失败: {e}")
            return True, None  # 扫描失败时不阻止上传

    def generate_safe_filename(self, original_filename: str, user_id: str = None) -> str:
        """生成安全的文件名"""
        try:
            # 获取文件扩展名
            ext = Path(original_filename).suffix.lower()
            if not ext:
                ext = '.bin'

            # 生成基于时间戳和用户ID的安全文件名
            import time
            import uuid

            timestamp = int(time.time())
            unique_id = str(uuid.uuid4())[:8]
            user_suffix = f"_{user_id}" if user_id else ""

            # 移除原始文件名中的特殊字符
            safe_name = "".join(
                c for c in Path(original_filename).stem
                if c.isalnum() or c in ('-', '_')
            )[:50]  # 限制长度

            if not safe_name:
                safe_name = "upload"

            return f"{safe_name}_{timestamp}_{unique_id}{user_suffix}{ext}"

        except Exception as e:
            logger.error(f"生成安全文件名失败: {e}")
            # 降级为简单的UUID文件名
            import uuid
            return f"upload_{uuid.uuid4().hex}{Path(original_filename).suffix}"

    def calculate_file_hash(self, file_content: bytes) -> str:
        """计算文件哈希值"""
        return hashlib.sha256(file_content).hexdigest()

# 全局文件安全验证器实例
file_security_validator = FileSecurityValidator()

async def validate_upload_file(file: UploadFile, user_id: str = None) -> Tuple[str, bytes]:
    """
    验证并处理上传文件

    Args:
        file: 上传的文件
        user_id: 用户ID

    Returns:
        (安全文件名, 文件内容)

    Raises:
        ValidationError: 文件验证失败
    """
    # 验证文件安全性
    is_valid, error_msg = await file_security_validator.validate_file(file)
    if not is_valid:
        raise ValidationError(error_msg)

    # 读取文件内容
    file_content = await file.read()
    await file.seek(0)  # 重置文件指针

    # 生成安全文件名
    safe_filename = file_security_validator.generate_safe_filename(
        file.filename, user_id
    )

    return safe_filename, file_content