import os
import pdfplumber
import logging
# 尝试导入 OCR，如果环境不支持则降级
try:
    from rapidocr_pdf import PDFLayout
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)

class PdfService:
    @staticmethod
    def parse_pdf(file_path: str):
        """
        解析 PDF，返回 (文本内容, 布局坐标列表)
        支持自动识别扫描件并启用 OCR
        """
        content = ""
        layout_dets = []
        is_scanned = False

        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"PDF file not found: {file_path}")
            return "", []

        # 1. 尝试常规解析
        try:
            with pdfplumber.open(file_path) as pdf:
                # 抽查第一页判断是否为扫描件
                if len(pdf.pages) > 0:
                    try:
                        first_text = pdf.pages[0].extract_text() or ""
                        if len(first_text.strip()) < 50:
                            is_scanned = True
                    except Exception as e:
                        logger.warning(f"Error extracting text from first page: {e}")
                        is_scanned = True

                if not is_scanned:
                    for page_idx, page in enumerate(pdf.pages):
                        try:
                            text = page.extract_text()
                            if text:
                                content += text + "\n"

                            words = page.extract_words()
                            for w in words:
                                layout_dets.append({
                                    "text": w['text'],
                                    "bbox": [w['x0'], w['top'], w['x1'], w['bottom']],
                                    "page_id": page_idx
                                })
                        except Exception as e:
                            logger.warning(f"Error parsing page {page_idx}: {e}")
                            continue

                    if content.strip():
                        return content, layout_dets
        except Exception as e:
            logger.error(f"Error parsing PDF with pdfplumber: {e}")
            # 如果 pdfplumber 失败，继续尝试 OCR

        # 2. 扫描件处理 (OCR)
        if is_scanned and OCR_AVAILABLE:
            print("Detected scanned PDF, running OCR...")
            pdf_engine = PDFLayout(sub_model=False)
            ocr_res, _ = pdf_engine(file_path)
            
            for page_idx, page_data in ocr_res.items():
                for item in page_data:
                    text_content = item.get('text', '')
                    bbox = item.get('bbox', [])
                    if text_content:
                        content += text_content + "\n"
                        layout_dets.append({
                            "text": text_content,
                            "bbox": bbox,
                            "page_id": int(page_idx)
                        })
            return content, layout_dets
        
        return content, layout_dets