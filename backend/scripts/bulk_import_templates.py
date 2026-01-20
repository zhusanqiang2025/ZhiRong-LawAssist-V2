# backend/scripts/bulk_import_templates.py
"""
合同模板批量导入脚本

功能：
1. 递归扫描指定目录下的所有合同文件（支持 .docx, .doc, .pdf）
2. 根据文件夹名称自动推断合同分类
3. 批量创建数据库记录
4. 将文件复制到应用存储目录

使用方法：
    cd backend
    python scripts/bulk_import_templates.py --source "D:\合同管理\合同模板" --owner-email zhusanqiang@az028.cn

配置：
- 可通过 CATEGORY_MAPPING 自定义文件夹名称到分类的映射
- 可通过 DEFAULT_CATEGORY 设置默认分类
"""
import os
import sys
import shutil
import uuid
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal, engine
from app.models.contract_template import ContractTemplate
from app.models.user import User
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== 配置区域 ====================

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {'.docx', '.doc', '.pdf'}

# 模板文件存储目录（相对于项目根目录）
TEMPLATE_STORAGE_DIR = "storage/templates"

# 默认所有者邮箱
DEFAULT_OWNER_EMAIL = "zhusanqiang@az028.cn"

# 默认分类（当无法从文件夹名称推断时使用）
DEFAULT_CATEGORY = "其他"
DEFAULT_SUBCATEGORY = None

# 默认模板配置
DEFAULT_IS_PUBLIC = True  # 是否公开
DEFAULT_LANGUAGE = "zh-CN"
DEFAULT_JURISDICTION = "中国大陆"

# 文件夹名称到分类的映射（可自定义）
# 格式: "文件夹名称": ("分类", "子分类")
# 如果文件夹名称不在映射中，将使用文件夹名称作为分类
CATEGORY_MAPPING: Dict[str, tuple] = {
    # 劳动人事类
    "劳动合同": ("劳动人事", "劳动合同"),
    "劳务合同": ("劳动人事", "劳务合同"),
    "员工手册": ("劳动人事", "员工手册"),
    "保密协议": ("劳动人事", "保密协议"),
    "竞业限制": ("劳动人事", "竞业限制"),

    # 买卖类
    "货物买卖": ("买卖合同", "货物买卖"),
    "设备买卖": ("买卖合同", "设备买卖"),
    "房屋买卖": ("买卖合同", "房屋买卖"),
    "车辆买卖": ("买卖合同", "车辆买卖"),

    # 租赁类
    "房屋租赁": ("租赁合同", "房屋租赁"),
    "办公室租赁": ("租赁合同", "办公室租赁"),
    "车辆租赁": ("租赁合同", "车辆租赁"),
    "设备租赁": ("租赁合同", "设备租赁"),

    # 服务类
    "服务合同": ("服务合同", None),
    "技术服务": ("服务合同", "技术服务"),
    "咨询服务": ("服务合同", "咨询服务"),
    "维护服务": ("服务合同", "维护服务"),

    # 建设工程
    "建设工程": ("建设工程", None),
    "施工合同": ("建设工程", "施工合同"),
    "监理合同": ("建设工程", "监理合同"),

    # 知识产权
    "知识产权": ("知识产权", None),
    "著作权": ("知识产权", "著作权"),
    "商标授权": ("知识产权", "商标授权"),

    # 其他
    "合伙协议": ("其他", "合伙协议"),
    "股东协议": ("公司治理", "股东协议"),
    "借款合同": ("金融借贷", "借款合同"),
}

# 常见关键词（用于自动提取）
COMMON_KEYWORDS = [
    "合同", "协议", "模板", "范本", "样本", "格式"
]

# ==================== 工具函数 ====================

def get_file_extension(file_path: Path) -> str:
    """获取文件扩展名（小写，带点号）"""
    return file_path.suffix.lower()

def is_supported_file(file_path: Path) -> bool:
    """检查文件是否为支持的格式"""
    return get_file_extension(file_path) in SUPPORTED_EXTENSIONS

def get_category_from_folder(folder_name: str) -> tuple:
    """
    从文件夹名称推断分类

    返回: (category, subcategory)
    """
    folder_name = folder_name.strip()

    # 查找精确匹配
    if folder_name in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[folder_name]

    # 模糊匹配（包含关键词）
    for key, value in CATEGORY_MAPPING.items():
        if key in folder_name or folder_name in key:
            return value

    # 未找到匹配，使用文件夹名称作为分类
    return (folder_name, None)

def extract_keywords_from_filename(filename: str) -> List[str]:
    """
    从文件名提取关键词

    例如: "办公室租赁合同模板.docx" -> ["办公室", "租赁", "合同"]
    """
    # 移除扩展名
    name = Path(filename).stem

    # 移除常见后缀
    for suffix in ["模板", "范本", "样本", "格式", "正式版", "修订版"]:
        name = name.replace(suffix, "")

    keywords = []

    # 按常见分隔符分割
    for sep in ["_", "-", " ", "、", "，"]:
        if sep in name:
            parts = name.split(sep)
            keywords.extend(parts)
            break
    else:
        # 没有分隔符，尝试提取词语
        # 简单的按2-3字符分割（针对中文）
        i = 0
        while i < len(name):
            for length in [4, 3, 2]:
                if i + length <= len(name):
                    word = name[i:i+length]
                    if word not in keywords:
                        keywords.append(word)
                    i += length
                    break
            else:
                i += 1

    # 过滤常见词和短词
    filtered = [k for k in keywords if len(k) >= 2 and k not in COMMON_KEYWORDS]

    return filtered[:5]  # 最多返回5个关键词

def generate_description(filename: str, category: str, subcategory: Optional[str]) -> str:
    """生成模板描述"""
    desc = f"{category}合同模板"
    if subcategory:
        desc = f"{subcategory}{desc}"
    return desc

# ==================== 导入逻辑 ====================

class TemplateBulkImporter:
    """批量导入器"""

    def __init__(
        self,
        source_dir: str,
        owner_email: str = DEFAULT_OWNER_EMAIL,
        is_public: bool = DEFAULT_IS_PUBLIC,
        dry_run: bool = False
    ):
        self.source_dir = Path(source_dir)
        self.owner_email = owner_email
        self.is_public = is_public
        self.dry_run = dry_run

        # 确保目标目录存在
        self.storage_dir = project_root / TEMPLATE_STORAGE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # 统计信息
        self.stats = {
            "total_files": 0,
            "imported": 0,
            "skipped": 0,
            "failed": 0,
            "errors": []
        }

    def _get_owner(self, db: Session) -> User:
        """获取所有者用户"""
        user = db.query(User).filter(User.email == self.owner_email).first()
        if not user:
            raise ValueError(f"用户不存在: {self.owner_email}")
        return user

    def _file_exists_in_db(self, db: Session, file_name: str, owner_id: int) -> bool:
        """检查文件是否已存在于数据库中"""
        existing = db.query(ContractTemplate).filter(
            ContractTemplate.file_name == file_name,
            ContractTemplate.owner_id == owner_id
        ).first()
        return existing is not None

    def _scan_directory(self, directory: Path, relative_path: str = "") -> List[Dict]:
        """
        递归扫描目录，返回所有待导入文件的信息

        返回: [
            {
                "file_path": Path,
                "relative_path": str,  # 相对于源目录的路径
                "category": str,
                "subcategory": str,
                "filename": str
            },
            ...
        ]
        """
        files_info = []

        for item in directory.iterdir():
            if item.is_file() and is_supported_file(item):
                # 确定分类
                if relative_path:
                    # 使用父文件夹名称作为分类
                    folder_name = relative_path.split(os.sep)[0]
                    category, subcategory = get_category_from_folder(folder_name)
                else:
                    category, subcategory = DEFAULT_CATEGORY, DEFAULT_SUBCATEGORY

                files_info.append({
                    "file_path": item,
                    "relative_path": relative_path,
                    "category": category,
                    "subcategory": subcategory,
                    "filename": item.name
                })

            elif item.is_dir():
                # 递归处理子目录
                subdir_path = os.path.join(relative_path, item.name) if relative_path else item.name
                files_info.extend(self._scan_directory(item, subdir_path))

        return files_info

    def _import_file(self, db: Session, file_info: Dict, owner: User) -> bool:
        """导入单个文件"""
        try:
            file_path = file_info["file_path"]
            filename = file_info["filename"]

            # 检查是否已存在
            if self._file_exists_in_db(db, filename, owner.id):
                logger.info(f"跳过（已存在）: {filename}")
                self.stats["skipped"] += 1
                return False

            # 生成唯一文件名
            file_ext = get_file_extension(file_path)
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            dest_path = self.storage_dir / unique_filename

            # 复制文件
            if not self.dry_run:
                shutil.copy2(file_path, dest_path)

            # 提取关键词
            keywords = extract_keywords_from_filename(filename)

            # 创建数据库记录
            if not self.dry_run:
                template = ContractTemplate(
                    name=Path(filename).stem,  # 文件名（不含扩展名）
                    category=file_info["category"],
                    subcategory=file_info["subcategory"],
                    description=generate_description(
                        filename,
                        file_info["category"],
                        file_info["subcategory"]
                    ),
                    file_url=str(dest_path),
                    file_name=filename,
                    file_size=file_path.stat().st_size,
                    file_type=file_ext[1:],  # 去掉点号
                    is_public=self.is_public,
                    owner_id=owner.id,
                    keywords=keywords if keywords else None,
                    status="active",
                    language=DEFAULT_LANGUAGE,
                    jurisdiction=DEFAULT_JURISDICTION
                )

                db.add(template)
                db.commit()
                db.refresh(template)

                logger.info(f"已导入: {filename} -> {template.id}")
            else:
                logger.info(f"[DRY RUN] 将导入: {filename}")

            self.stats["imported"] += 1
            return True

        except Exception as e:
            logger.error(f"导入失败 {filename}: {e}")
            self.stats["failed"] += 1
            self.stats["errors"].append({
                "file": filename,
                "error": str(e)
            })
            return False

    def run(self):
        """执行批量导入"""
        logger.info("=" * 60)
        logger.info("合同模板批量导入工具")
        logger.info("=" * 60)
        logger.info(f"源目录: {self.source_dir}")
        logger.info(f"目标目录: {self.storage_dir}")
        logger.info(f"所有者: {self.owner_email}")
        logger.info(f"公开状态: {self.is_public}")
        logger.info(f"模拟运行: {self.dry_run}")
        logger.info("=" * 60)

        # 检查源目录
        if not self.source_dir.exists():
            logger.error(f"源目录不存在: {self.source_dir}")
            return

        # 扫描文件
        logger.info("正在扫描文件...")
        files_info = self._scan_directory(self.source_dir)
        self.stats["total_files"] = len(files_info)

        if not files_info:
            logger.warning("未找到任何支持的文件")
            return

        logger.info(f"找到 {len(files_info)} 个文件")
        logger.info("")

        # 显示分类统计
        category_count = {}
        for fi in files_info:
            cat = f"{fi['category']}/{fi['subcategory'] or '无'}"
            category_count[cat] = category_count.get(cat, 0) + 1

        logger.info("分类统计:")
        for cat, count in sorted(category_count.items()):
            logger.info(f"  {cat}: {count} 个")
        logger.info("")

        # 确认
        if not self.dry_run:
            response = input("是否继续？(y/n): ")
            if response.lower() != 'y':
                logger.info("已取消")
                return

        # 执行导入
        db = SessionLocal()
        try:
            owner = self._get_owner(db)

            for i, file_info in enumerate(files_info, 1):
                logger.info(f"[{i}/{len(files_info)}] ", end="")
                self._import_file(db, file_info, owner)

            logger.info("")
            logger.info("=" * 60)
            logger.info("导入完成")
            logger.info("=" * 60)
            logger.info(f"总文件数: {self.stats['total_files']}")
            logger.info(f"成功导入: {self.stats['imported']}")
            logger.info(f"已存在跳过: {self.stats['skipped']}")
            logger.info(f"导入失败: {self.stats['failed']}")

            if self.stats["errors"]:
                logger.info("")
                logger.info("失败详情:")
                for err in self.stats["errors"]:
                    logger.info(f"  - {err['file']}: {err['error']}")

        except Exception as e:
            logger.error(f"导入过程出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            db.close()


# ==================== 命令行入口 ====================

def main():
    parser = argparse.ArgumentParser(description="合同模板批量导入工具")
    parser.add_argument(
        "--source",
        type=str,
        required=True,
        help="源目录路径（包含合同模板文件的目录）"
    )
    parser.add_argument(
        "--owner-email",
        type=str,
        default=DEFAULT_OWNER_EMAIL,
        help=f"模板所有者邮箱（默认: {DEFAULT_OWNER_EMAIL}）"
    )
    parser.add_argument(
        "--private",
        action="store_true",
        help="导入为私有模板（默认为公开）"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，不实际导入（用于预览）"
    )

    args = parser.parse_args()

    importer = TemplateBulkImporter(
        source_dir=args.source,
        owner_email=args.owner_email,
        is_public=not args.private,
        dry_run=args.dry_run
    )

    importer.run()


if __name__ == "__main__":
    main()
