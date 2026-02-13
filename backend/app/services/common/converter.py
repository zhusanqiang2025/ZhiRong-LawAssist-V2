import os
import subprocess
import logging
from typing import Tuple, Union, Optional

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.getcwd(), "storage", "uploads")


def convert_doc_to_docx(filename: str) -> Tuple[bool, Optional[str], str]:
    """
    将 .doc 文件转换为 .docx 格式

    参数:
        filename: 上传的文件名

    返回:
        (success, docx_filename, message)
        - success: 转换是否成功
        - docx_filename: 转换后的文件名（失败时为 None）
        - message: 状态消息
    """
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            return False, None, f"文件不存在: {file_path}"

        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext != 'doc':
            return False, None, f"不支持的文件格式: .{ext}，仅支持 .doc 转 .docx"

        # 生成 .docx 文件名
        base_name = filename.rsplit('.', 1)[0]
        docx_filename = f"{base_name}.docx"
        docx_path = os.path.join(UPLOAD_DIR, docx_filename)

        # 删除已存在的目标文件
        if os.path.exists(docx_path):
            try:
                os.remove(docx_path)
            except Exception:
                pass

        # 使用 LibreOffice 转换
        cmd = ["soffice", "--headless", "--convert-to", "docx", "--outdir", UPLOAD_DIR, file_path]
        logger.info("Running LibreOffice doc to docx conversion: %s", " ".join(cmd))

        result = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30  # 30秒超时
        )

        # 检查输出文件
        if os.path.exists(docx_path):
            logger.info(f"Successfully converted {filename} to {docx_filename}")
            return True, docx_filename, f"文件已转换为 .docx 格式"
        else:
            # LibreOffice 可能生成了不同名称的文件，尝试查找
            possible_files = [f for f in os.listdir(UPLOAD_DIR) if f.startswith(base_name) and f.endswith('.docx')]
            if possible_files:
                docx_filename = possible_files[0]
                logger.info(f"Found converted file: {docx_filename}")
                return True, docx_filename, f"文件已转换为 .docx 格式"
            else:
                return False, None, "转换失败，未找到输出文件"

    except subprocess.TimeoutExpired:
        logger.error("LibreOffice conversion timed out")
        return False, None, "转换超时，请稍后重试"
    except subprocess.CalledProcessError as e:
        logger.error("LibreOffice conversion failed: %s", e.stderr.decode() if isinstance(e.stderr, (bytes, bytearray)) else str(e))
        return False, None, f"转换失败: {str(e)}"
    except Exception as exc:
        logger.exception("Unexpected error in convert_doc_to_docx")
        return False, None, f"转换出错: {str(exc)}"


def convert_to_pdf_via_onlyoffice(filename: str) -> Tuple[bool, Union[bytes, str]]:
    """
    尝试将上传的文件转换为 PDF 并返回 (success, bytes_or_error).

    优先使用 LibreOffice (soffice CLI)。如果文件已经是 PDF，则直接返回其内容。
    返回:
      (True, pdf_bytes) 或 (False, error_message)
    """
    try:
        file_path = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(file_path):
            return False, f"file not found: {file_path}"

        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
        if ext == 'pdf':
            with open(file_path, 'rb') as f:
                return True, f.read()

        # 1) 尝试使用 soffice (LibreOffice)
        try:
            pdf_name = filename.rsplit('.', 1)[0] + '.pdf'
            pdf_full_path = os.path.join(UPLOAD_DIR, pdf_name)

            # 删除已存在的目标文件以避免冲突
            if os.path.exists(pdf_full_path):
                try:
                    os.remove(pdf_full_path)
                except Exception:
                    pass

            cmd = ["soffice", "--headless", "--convert-to", "pdf", "--outdir", UPLOAD_DIR, file_path]
            logger.info("Running LibreOffice conversion: %s", " ".join(cmd))
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            if os.path.exists(pdf_full_path):
                with open(pdf_full_path, 'rb') as f:
                    return True, f.read()
            else:
                logger.warning("soffice reported success but output not found: %s", pdf_full_path)
        except FileNotFoundError:
            logger.warning("soffice not found on PATH; skipping LibreOffice conversion")
        except subprocess.CalledProcessError as e:
            logger.error("soffice conversion failed: %s", e.stderr.decode() if isinstance(e.stderr, (bytes, bytearray)) else str(e))

        # 2) 尝试使用 pypandoc（如果安装并且支持）
        try:
            import pypandoc
            pdf_name = filename.rsplit('.', 1)[0] + '.pdf'
            pdf_full_path = os.path.join(UPLOAD_DIR, pdf_name)
            pypandoc.convert_file(file_path, 'pdf', outputfile=pdf_full_path)
            if os.path.exists(pdf_full_path):
                with open(pdf_full_path, 'rb') as f:
                    return True, f.read()
        except Exception as e:
            logger.warning("pypandoc conversion failed or not available: %s", str(e))

        return False, "conversion to PDF failed (requires soffice or pypandoc)"

    except Exception as exc:  # 保底
        logger.exception("Unexpected error in convert_to_pdf_via_onlyoffice")
        return False, str(exc)
