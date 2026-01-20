# document_preprocessor.py vs document_processor.py 功能对比

## 一、核心定位差异

### document_preprocessor.py - **格式转换中心**

**定位**: 将各种格式的合同文件**统一转换为 .docx 格式**

**核心功能**: 格式标准化，为后续处理做准备

### document_processor.py - **内容提取器**

**定位**: 从文件中**提取文本内容和结构信息**

**核心功能**: 内容解析，返回可读的文本和元数据

---

## 二、功能对比表

| 维度 | document_preprocessor.py | document_processor.py |
|------|--------------------------|------------------------|
| **主要目标** | 格式转换（→ .docx） | 内容提取（→ 文本） |
| **输入格式** | PDF, DOC, DOCX, TXT, RTF, ODT, 图片 | PDF, DOCX, 图片, TXT |
| **输出格式** | 统一输出 .docx 文件 | 返回文本内容和元数据（字典） |
| **外部服务** | ✅ MinerU PDF解析 | ❌ 仅使用本地库 |
| | ✅ OCR文字识别 | ❌ 无外部服务 |
| **后处理** | ✅ 清理页码、空格、换行 | ❌ 无后处理 |
| **AI增强** | ✅ AI辅助后处理 | ❌ 无AI功能 |
| **结构化输出** | ❌ 仅返回文件 | ✅ 返回章节、签名等结构 |

---

## 三、document_preprocessor.py 详细分析

### 3.1 核心类

```python
class DocumentPreprocessor:
    """
    合同文件预处理中心

    功能：
    1. 格式检测：自动识别文件格式
    2. 格式转换：统一转换为 .docx 格式
    3. 文档后处理：清理页码、多余空格、不正常换行等
    4. 质量检查：验证转换后的文件完整性
    5. 元数据提取：提取文档基本信息（页数、字数等）
    """
```

### 3.2 支持的格式

```python
# 输入格式（11种）
SUPPORTED_INPUT_FORMATS = {
    DocumentFormat.DOC,      # .doc (旧版Word)
    DocumentFormat.DOCX,     # .docx (新版Word)
    DocumentFormat.PDF,      # .pdf
    DocumentFormat.TXT,      # .txt
    DocumentFormat.RTF,      # .rtf
    DocumentFormat.ODT,      # .odt (OpenDocument)
    # 图片格式（6种）
    DocumentFormat.JPG, DocumentFormat.JPEG,
    DocumentFormat.PNG, DocumentFormat.BMP,
    DocumentFormat.TIFF, DocumentFormat.GIF,
}

# 输出格式（统一）
# 始终输出 .docx 格式
```

### 3.3 核心方法

#### 方法1: convert_to_docx()

```python
def convert_to_docx(
    self,
    file_path: str,
    output_filename: str = None,
    force: bool = False
) -> Tuple[ConversionResult, str, Optional[Dict]]:
    """
    将文件转换为 .docx 格式

    Args:
        file_path: 输入文件路径
        output_filename: 输出文件名（可选）
        force: 是否强制转换

    Returns:
        (转换结果, 输出文件路径, 元数据)
    """
```

**转换流程**:
```
1. 检测文件格式
2. 如果是 .docx → 可选后处理
3. 如果是其他格式 → 转换为 .docx
   - PDF → 使用 MinerU 或 PyMuPDF
   - 图片 → 使用 OCR
   - DOC/RTF/ODT → 使用 LibreOffice 或 antiword
4. 后处理（清理页码、空格等）
5. 可选AI后处理（智能修复格式）
6. 返回转换后的 .docx 文件路径
```

#### 方法2: 后处理功能

```python
# 后处理选项
ENABLE_POSTPROCESSING = True    # 是否启用后处理
REMOVE_PAGE_NUMBERS = True      # 删除页码
CLEAN_SPACES = True             # 清理多余空格
FIX_LINE_BREAKS = True          # 修复不正常换行
REMOVE_EMPTY_PARAGRAPHS = True  # 删除空段落

# 页码识别模式
PAGE_NUMBER_PATTERNS = [
    r'^\s*[\-—]*\s*\d+\s*[\-—]*\s*$',  # - 1 -
    r'^\s*第\s*\d+\s*[页页张张]\s*$',     # 第1页
    r'^\s*Page\s*\d+\s*$',              # Page 1
    r'^\s*\d+\s*/\s*\d+\s*$',           # 1/10
    # ... 更多模式
]
```

### 3.4 外部服务集成

#### MinerU PDF解析服务

```python
def _convert_pdf_via_mineru(self, file_path: str) -> Optional[str]:
    """
    使用 MinerU 服务解析 PDF

    MinerU 是高质量的PDF解析服务，支持：
    - 复杂布局识别
    - 表格识别
    - 多栏排版
    - 公式识别
    """
    if not self.mineru_url:
        return None

    # 调用 MinerU API
    # 返回 Markdown 或 DOCX 格式
```

#### OCR文字识别服务

```python
def _ocr_image(self, image_path: str) -> Optional[str]:
    """
    使用 OCR 服务识别图片中的文字

    支持：
    - 公网OCR服务（高精度）
    - 本地OCR（Tesseract，备用）
    """
    if self.ocr_url:
        # 调用公网OCR服务
        pass
    else:
        # 使用本地Tesseract OCR
        import pytesseract
        text = pytesseract.image_to_string(image_path, lang='chi_sim+eng')
```

### 3.5 使用场景

```python
# 场景1: 用户上传PDF合同
preprocessor = DocumentPreprocessor()
result, output_path, metadata = preprocessor.convert_to_docx(
    "user_upload.pdf"
)
# → 返回 "user_upload.docx"

# 场景2: 用户上传图片合同
result, output_path, metadata = preprocessor.convert_to_docx(
    "scan_001.jpg"
)
# → 返回 "scan_001.docx"

# 场景3: 批量处理
for file in files:
    result, docx_path, _ = preprocessor.convert_to_docx(file)
    # 保存到数据库或发送给下一模块
```

---

## 四、document_processor.py 详细分析

### 4.1 核心类

```python
class DocumentProcessor:
    """法律文档处理器类"""

    def __init__(self):
        self.supported_formats = {
            'pdf': ['application/pdf'],
            'docx': ['application/vnd.openxmlformats-...'],
            'image': ['image/jpeg', 'image/png', ...],
            'text': ['text/plain', ...]
        }
```

### 4.2 支持的格式

```python
# 输入格式（4大类）
supported_formats = {
    'pdf': PDF文件
    'docx': Word文档
    'image': 图片文件（需OCR）
    'text': 纯文本文件
}

# 输出格式
# 返回字典，包含：
{
    "status": "success" | "error",
    "data": {
        "content": "提取的文本内容",
        "metadata": {...},
        "structure": {...}
    }
}
```

### 4.3 核心方法

#### 方法1: extract_content()

```python
async def extract_content(self, file: UploadFile) -> Dict[str, Any]:
    """
    提取文件内容

    Args:
        file: 上传的文件（FastAPI UploadFile）

    Returns:
        包含提取内容和元数据的字典
    """
    file_type = self.detect_file_type(file)

    # 根据文件类型处理
    if file_type == 'pdf':
        return self._extract_pdf_content(file_content, filename)
    elif file_type == 'docx':
        return self._extract_docx_content(file_content, filename)
    elif file_type == 'image':
        return self._extract_image_content(file_content, filename)
    elif file_type == 'text':
        return self._extract_text_content(file_content, filename)
```

#### 方法2: PDF内容提取

```python
def _extract_pdf_content(self, file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    提取PDF文件内容

    使用 PyPDF2库：
    - 逐页提取文本
    - 保留页数信息
    - 检测章节（通过正则表达式）
    - 检测签名位置
    """
    pdf_reader = PdfReader(io.BytesIO(file_content))
    text_content = ""

    for page in pdf_reader.pages:
        text_content += page.extract_text() + "\n"

    return {
        "status": "success",
        "data": {
            "content": text_content.strip(),
            "metadata": {
                "title": filename,
                "pages": len(pdf_reader.pages),
                "format": "pdf"
            },
            "structure": {
                "chapters": self._extract_chapters(text_content),
                "tables": [],
                "signatures": self._detect_signatures(text_content)
            }
        }
    }
```

#### 方法3: 图片OCR提取

```python
def _extract_image_content(self, file_content: bytes, filename: str) -> Dict[str, Any]:
    """
    提取图片中的文字（OCR）

    使用 Tesseract OCR：
    - 支持中英文混合识别
    - 返回识别的文本内容
    """
    image = Image.open(io.BytesIO(file_content))

    # OCR识别
    text = pytesseract.image_to_string(image, lang='chi_sim+eng')

    return {
        "status": "success",
        "data": {
            "content": text,
            "metadata": {
                "title": filename,
                "format": "image"
            }
        }
    }
```

### 4.4 结构化提取

```python
# 章节提取
def _extract_chapters(self, text: str) -> List[Dict]:
    """
    提取章节结构

    通过正则表达式识别章节标题：
    - 第X章、第X节
    - 一、二、三、
    - 1.1、1.2、1.3
    """
    pattern = r'(第[一二三四五六七八九十\d]+章|第[一二三四五六七八九十\d]+节)'
    chapters = []
    for match in re.finditer(pattern, text):
        chapters.append({
            "title": match.group(),
            "position": match.start()
        })
    return chapters

# 签名检测
def _detect_signatures(self, text: str) -> List[Dict]:
    """
    检测签名位置

    识别签名模式：
    - 甲方签字：
    - 乙方签字：
    - 法定代表人：
    """
    pattern = r'(甲方|乙方|丙方|法定代表人|委托代理人)[:：]\s*[(\（](\s*签字|盖章|签名)\s*[)\）]'
    signatures = []
    for match in re.finditer(pattern, text):
        signatures.append({
            "party": match.group(1),
            "position": match.start()
        })
    return signatures
```

### 4.5 使用场景

```python
# 场景1: 快速提取PDF文本
processor = DocumentProcessor()
result = await processor.extract_content(uploaded_file)
text = result["data"]["content"]
# → 返回PDF中的纯文本

# 场景2: 获取文档元数据
metadata = result["data"]["metadata"]
page_count = metadata["pages"]
format_type = metadata["format"]

# 场景3: 获取文档结构
structure = result["data"]["structure"]
chapters = structure["chapters"]
signatures = structure["signatures"]
```

---

## 五、工作流程对比

### document_preprocessor.py 工作流程

```
输入文件 (PDF/DOC/图片/TXT)
    ↓
格式检测
    ↓
┌─────────────────────────────────┐
│ 是否需要转换？                    │
│ - .docx → 可选后处理              │
│ - 其他格式 → 转换为 .docx         │
└─────────────────────────────────┘
    ↓
格式转换
    ├─ PDF → MinerU/PyMuPDF → .docx
    ├─ 图片 → OCR → .docx
    └─ DOC/RTF/ODT → LibreOffice → .docx
    ↓
后处理
    ├─ 清理页码
    ├─ 清理多余空格
    ├─ 修复不正常换行
    └─ 删除空段落
    ↓
可选AI后处理
    ├─ 智能格式修复
    ├─ 段落合并
    └─ 标题识别
    ↓
输出: .docx 文件（保存到磁盘）
```

### document_processor.py 工作流程

```
输入文件 (UploadFile)
    ↓
文件类型检测
    ├─ PDF
    ├─ DOCX
    ├─ 图片
    └─ TXT
    ↓
内容提取
    ├─ PDF → PyPDF2 → 文本
    ├─ DOCX → python-docx → 文本
    ├─ 图片 → Tesseract OCR → 文本
    └─ TXT → 直接读取 → 文本
    ↓
结构化分析
    ├─ 章节提取
    ├─ 签名检测
    └─ 表格识别（可选）
    ↓
输出: 字典 {
    status: "success",
    data: {
        content: "文本内容",
        metadata: {...},
        structure: {...}
    }
}
```

---

## 六、使用场景对比

### document_preprocessor.py 适用场景

✅ **需要标准化格式时**
- 用户上传各种格式的合同，需要统一处理
- 后续模块要求输入必须是 .docx 格式
- 需要高质量的文档（使用MinerU和公网OCR）

✅ **需要文档清理时**
- 清除扫描件的页码
- 修复OCR后的格式问题
- 删除多余空格和空段落

✅ **批量文件处理时**
- 批量转换历史合同
- 统一存储格式
- 为AI处理做准备

### document_processor.py 适用场景

✅ **需要快速查看内容时**
- 用户上传文件，立即预览文本
- 不需要保存文件，只需要读取内容
- 快速提取关键信息

✅ **需要结构化信息时**
- 提取章节结构
- 检测签名位置
- 分析文档元数据

✅ **实时处理时**
- 在线预览
- 实时搜索
- 内容摘要

---

## 七、协作关系

```
用户上传文件
    ↓
┌─────────────────────────────────────┐
│ document_processor.py                │
│ (快速提取内容，用于预览)             │
└─────────────────────────────────────┘
    ↓
显示文本预览
    ↓
用户确认需要保存
    ↓
┌─────────────────────────────────────┐
│ document_preprocessor.py            │
│ (格式转换，生成标准.docx文件)        │
└─────────────────────────────────────┘
    ↓
保存 .docx 文件到数据库
```

---

## 八、性能对比

| 指标 | document_preprocessor.py | document_processor.py |
|------|--------------------------|------------------------|
| **处理速度** | 较慢（需要转换和后处理） | 快速（仅提取内容） |
| **准确性** | 高（使用外部服务） | 中（使用本地库） |
| **资源消耗** | 高（调用外部API） | 低（本地处理） |
| **适用场景** | 长期存储、AI处理 | 快速预览、内容搜索 |
| **成本** | 可能产生API费用 | 免费 |

---

## 九、代码位置

| 文件 | 路径 | 主要方法 |
|------|------|---------|
| **document_preprocessor.py** | `backend/app/services/document_preprocessor.py` | `convert_to_docx()` |
| **document_processor.py** | `backend/app/services/document_processor.py` | `extract_content()` |

---

## 十、总结

### document_preprocessor.py - **格式转换专家**

- **专长**: 将各种格式转换为 .docx
- **输出**: 文件（保存到磁盘）
- **特点**:
  - 支持外部服务（MinerU、OCR）
  - 强大的后处理功能
  - AI辅助格式修复
- **用途**: 文件标准化、长期存储

### document_processor.py - **内容提取专家**

- **专长**: 从文件中提取文本和结构
- **输出**: 字典（内存数据）
- **特点**:
  - 支持多种格式
  - 结构化分析（章节、签名）
  - 快速轻量
- **用途**: 快速预览、内容搜索、信息提取

### 协作使用

```
document_processor.py → 快速查看内容
         ↓
document_preprocessor.py → 标准化格式并保存
```

两个模块互补，分别处理不同阶段的需求！
