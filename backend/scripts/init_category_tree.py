# backend/scripts/init_category_tree.py
"""
初始化合同分类树到数据库

功能：
1. 根据前端使用的10个一级分类体系初始化数据库
2. 创建三级分类层级结构（一级 -> 二级 -> 三级）
3. 与知识图谱的分类体系对齐
"""
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from sqlalchemy import create_engine

# 尝试使用配置的数据库 URL，如果失败则使用 SQLite
SessionLocal = None
try:
    from app.database import SessionLocal as DBSessionLocal, engine
    SessionLocal = DBSessionLocal
    logger.info("使用 PostgreSQL 数据库")
    # 测试连接
    db = SessionLocal()
    from app.models.category import Category
    _ = db.query(Category).count()
    db.close()
except Exception as e:
    logger.warning(f"PostgreSQL 连接失败: {e}，使用 SQLite 作为后备")
    SQLITE_DB = project_root.parent / "data" / "app.db"
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=sqlite_engine)
    logger.info(f"使用 SQLite 数据库: {SQLITE_DB}")

from app.models.category import Category

# 合同分类体系数据（与前端TemplateContractFeaturesEditor.tsx一致）
CONTRACT_CLASSIFICATION_TREE = {
    "民法典典型合同": {
        "买卖合同": [
            "动产买卖合同",
            "不动产买卖合同",
        ],
        "借款合同": [
            "个人借款合同",
            "企业借款合同",
            "委托贷款合同",
        ],
        "租赁合同": [
            "住宅租赁合同",
            "商业租赁合同",
            "融资租赁合同",
        ],
        "承揽合同": [
            "加工承揽合同",
            "定作合同",
        ],
        "建设工程合同": [
            "建设工程施工合同",
            "工程总承包合同",
            "分包合同",
            "勘察设计合同",
        ],
        "运输合同": [
            "公路货物运输合同",
            "多式联运合同",
            "物流服务合同",
        ],
        "技术合同": [
            "技术开发合同",
            "技术转让合同",
            "技术咨询合同",
            "技术服务合同",
        ],
        "委托合同": [
            "委托代理合同",
            "委托管理合同",
            "授权委托书",
        ],
        "物业服务合同": [
            "前期物业服务合同",
            "物业管理服务合同",
        ],
        "行纪与中介": [
            "行纪合同",
            "中介合同",
            "居间合同",
        ],
        "赠与合同": [
            "公益赠与合同",
            "一般赠与合同",
        ],
    },
    "非典型商事合同": {
        "股权与投资": [
            "股权转让协议",
            "增资扩股协议",
            "股权回购协议",
            "股东协议",
            "投资合作协议",
            "股权代持协议",
            "并购重组协议",
        ],
        "合伙与联营": [
            "普通合伙协议",
            "有限合伙协议",
            "项目联营协议",
            "联合体投标协议",
        ],
        "特许与加盟": [
            "特许经营合同",
            "品牌加盟合同",
            "代理经销合同",
        ],
        "知识产权商业化": [
            "商标授权许可协议",
            "专利实施许可协议",
            "IP衍生品开发协议",
        ],
    },
    "劳动与人力资源": {
        "标准劳动关系": [
            "劳动合同(固定期限)",
            "劳动合同(无固定期限)",
            "聘用协议",
        ],
        "灵活用工": [
            "劳务派遣协议",
            "非全日制用工协议",
            "实习协议",
            "返聘协议",
        ],
        "附属协议": [
            "保密协议(劳动版)",
            "竞业限制协议",
            "培训服务协议",
            "员工期权激励协议",
        ],
    },
    "行业特定合同": {
        "互联网与软件": [
            "软件开发合同",
            "SaaS服务协议",
            "数据处理协议(DPA)",
            "平台用户协议",
            "隐私政策",
        ],
        "供应链与制造": [
            "OEM/ODM代工协议",
            "长期供货框架协议",
            "质量保证协议(QA)",
            "设备采购合同",
        ],
        "文娱与传媒": [
            "演艺经纪合同",
            "影视投资制作合同",
            "著作权转让协议",
            "MCN签约协议",
        ],
    },
    "争议解决与法律程序": {
        "和解与调解": [
            "庭外和解协议",
            "民事调解协议",
            "赔偿谅解协议",
            "交通事故赔偿协议",
            "劳动争议和解书",
        ],
        "债权债务处理": [
            "还款计划书",
            "债务重组协议",
            "以物抵债协议",
            "债权转让通知书",
            "催款函",
        ],
    },
    "婚姻家事与私人财富": {
        "婚姻家庭": [
            "婚前财产协议",
            "婚内财产协议",
            "离婚协议书",
            "分居协议",
            "抚养权变更协议",
        ],
        "财富传承": [
            "遗赠扶养协议",
            "分家析产协议",
            "意定监护协议",
            "家族信托契约",
        ],
    },
    "公司治理与合规": {
        "公司组织文件": [
            "公司章程",
            "股东会议事规则",
            "董事会议事规则",
            "监事会议事规则",
            "发起人协议",
        ],
        "控制权与投票": [
            "一致行动人协议",
            "投票权委托协议",
            "代持股协议",
        ],
    },
    "政务与公共服务": {
        "政府采购与合作": [
            "政府采购合同",
            "PPP项目合同",
            "特许经营权协议",
            "国有土地使用权出让合同",
        ],
    },
    "跨境与国际合同": {
        "国际贸易": [
            "国际货物买卖合同",
            "国际独家代理协议",
            "国际分销协议",
        ],
    },
    "通用框架与兜底协议": {
        "意向与框架": [
            "合作备忘录(MOU)",
            "合作意向书(LOI)",
            "战略合作框架协议",
        ],
        "单方声明与承诺": [
            "承诺书",
            "免责声明",
            "授权委托书(通用)",
            "催告函",
        ],
        "通用交易底座": [
            "保密协议(通用NDA)",
            "通用服务协议(标准版)",
            "通用采购协议",
            "简单欠条",
            "收据",
        ],
    },
}


def get_or_create_category(
    db: Session,
    name: str,
    parent_id: int = None,
    code: str = None,
    meta_info: dict = None
) -> Category:
    """
    获取或创建分类

    Args:
        db: 数据库会话
        name: 分类名称
        parent_id: 父分类ID
        code: 分类编码
        meta_info: 元数据

    Returns:
        Category对象
    """
    # 尝试获取已存在的分类
    category = db.query(Category).filter(
        Category.name == name,
        Category.parent_id == parent_id
    ).first()

    if category:
        return category

    # 创建新分类
    category = Category(
        name=name,
        parent_id=parent_id,
        code=code,
        meta_info=meta_info or {},
        is_active=True,
        sort_order=0
    )
    db.add(category)
    db.commit()
    db.refresh(category)

    return category


def init_category_tree():
    """初始化合同分类树"""
    logger.info("=" * 60)
    logger.info("开始初始化合同分类树")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 清空现有分类数据（可选，根据需求决定）
        # db.query(Category).delete()
        # db.commit()
        # logger.info("已清空现有分类数据")

        # 统计信息
        stats = {
            "level1": 0,
            "level2": 0,
            "level3": 0,
            "total": 0
        }

        # 遍历分类树
        for level1_name, level2_data in CONTRACT_CLASSIFICATION_TREE.items():
            logger.info(f"\n处理一级分类: {level1_name}")

            # 创建一级分类
            level1_cat = get_or_create_category(
                db,
                name=level1_name,
                code=None,  # 可以根据需要设置编码
                meta_info={"level": "primary"}
            )
            stats["level1"] += 1
            logger.info(f"  ✓ 创建/获取一级分类: {level1_name} (ID: {level1_cat.id})")

            # 遍历二级分类
            for level2_name, level3_list in level2_data.items():
                logger.info(f"  处理二级分类: {level2_name}")

                # 创建二级分类
                level2_cat = get_or_create_category(
                    db,
                    name=level2_name,
                    parent_id=level1_cat.id,
                    code=None,
                    meta_info={"level": "secondary"}
                )
                stats["level2"] += 1
                logger.info(f"    ✓ 创建/获取二级分类: {level2_name} (ID: {level2_cat.id})")

                # 遍历三级分类
                for level3_name in level3_list:
                    # 创建三级分类
                    level3_cat = get_or_create_category(
                        db,
                        name=level3_name,
                        parent_id=level2_cat.id,
                        code=None,
                        meta_info={"level": "tertiary"}
                    )
                    stats["level3"] += 1

            logger.info(f"  完成二级分类: {level2_name}")

        stats["total"] = stats["level1"] + stats["level2"] + stats["level3"]

        # 输出统计
        logger.info("\n" + "=" * 60)
        logger.info("初始化完成")
        logger.info("=" * 60)
        logger.info(f"一级分类: {stats['level1']}个")
        logger.info(f"二级分类: {stats['level2']}个")
        logger.info(f"三级分类: {stats['level3']}个")
        logger.info(f"总计: {stats['total']}个分类")

        # 验证结果
        logger.info("\n" + "=" * 60)
        logger.info("验证结果")
        logger.info("=" * 60)

        all_categories = db.query(Category).all()
        logger.info(f"数据库中的分类总数: {len(all_categories)}")

        # 显示分类树结构
        level1_categories = db.query(Category).filter(Category.parent_id == None).all()
        for l1 in level1_categories:
            logger.info(f"\n{l1.name} (ID: {l1.id})")
            level2_categories = db.query(Category).filter(Category.parent_id == l1.id).all()
            for l2 in level2_categories:
                logger.info(f"  └─ {l2.name} (ID: {l2.id})")
                level3_categories = db.query(Category).filter(Category.parent_id == l2.id).all()
                for l3 in level3_categories:
                    logger.info(f"      └─ {l3.name} (ID: {l3.id})")

    finally:
        db.close()


if __name__ == "__main__":
    try:
        init_category_tree()
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        sys.exit(1)
