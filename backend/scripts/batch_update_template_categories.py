# backend/scripts/batch_update_template_categories.py
"""
批量更新合同模板的分类信息和法律特征

功能：
1. 将所有模板对应到合同分类体系的最下层分类（三级或二级）
2. 从知识图谱自动加载7个法律特征字段
3. 支持干运行模式（dry_run）预览变更
4. 提供详细的统计报告和日志
"""
import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import json

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
    from app.models.contract_template import ContractTemplate
    _ = db.query(ContractTemplate).count()
    db.close()
except Exception as e:
    logger.warning(f"PostgreSQL 连接失败: {e}，使用 SQLite 作为后备")
    SQLITE_DB = project_root.parent / "data" / "app.db"
    SQLITE_DB.parent.mkdir(parents=True, exist_ok=True)
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    from sqlalchemy.orm import sessionmaker
    SessionLocal = sessionmaker(bind=sqlite_engine)
    logger.info(f"使用 SQLite 数据库: {SQLITE_DB}")

from app.models.contract_template import ContractTemplate

# 合同分类体系数据（与init_category_tree.py一致）
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


def load_knowledge_graph() -> Dict:
    """
    加载知识图谱数据

    Returns:
        {合同名称: {category, subcategory, legal_features}}
    """
    kg_data = {}

    # 知识图谱数据文件路径
    kg_file = project_root / "app" / "services" / "legal_features" / "knowledge_graph_data.json"

    if not kg_file.exists():
        logger.warning(f"知识图谱文件不存在: {kg_file}")
        return kg_data

    try:
        with open(kg_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for item in data.get('contract_types', []):
            name = item.get('name')
            if name:
                kg_data[name] = {
                    'category': item.get('category'),
                    'subcategory': item.get('subcategory'),
                    'aliases': item.get('aliases', []),
                    'legal_features': item.get('legal_features')
                }

        logger.info(f"从知识图谱加载了 {len(kg_data)} 个合同类型定义")
        return kg_data

    except Exception as e:
        logger.error(f"加载知识图谱失败: {e}")
        return kg_data


def build_category_tree_index() -> Dict:
    """
    构建分类树索引，用于快速查找

    Returns:
        {
            'by_level3': {三级分类名: (一级分类, 二级分类)},
            'by_level2': {二级分类名: 一级分类},
            'level3_list': [所有三级分类名列表],
            'level2_list': [所有二级分类名列表]
        }
    """
    index = {
        'by_level3': {},
        'by_level2': {},
        'level3_list': [],
        'level2_list': []
    }

    for level1, level2_dict in CONTRACT_CLASSIFICATION_TREE.items():
        for level2, level3_list in level2_dict.items():
            # 记录二级分类
            index['by_level2'][level2] = level1
            index['level2_list'].append(level2)

            # 记录三级分类
            for level3 in level3_list:
                index['by_level3'][level3] = (level1, level2)
                index['level3_list'].append(level3)

    logger.info(f"构建分类树索引: {len(index['level2_list'])} 个二级分类, {len(index['level3_list'])} 个三级分类")
    return index


def extract_keywords(text: str) -> List[str]:
    """
    从文本中提取关键词

    Args:
        text: 输入文本

    Returns:
        关键词列表
    """
    import re

    # 移除常见的后缀
    text = re.sub(r'[（(].*?[)）]', '', text)
    text = text.replace('合同', '').replace('协议', '').replace('书', '').strip()

    # 分词
    keywords = re.split(r'[,，、\s]+', text)

    # 返回非空关键词
    return [kw for kw in keywords if kw]


def calculate_similarity(template_name: str, kg_name: str, kg_info: Dict) -> float:
    """
    计算模板名称与知识图谱合同名称的相似度

    Args:
        template_name: 模板名称
        kg_name: 知识图谱合同名称
        kg_info: 知识图谱信息

    Returns:
        相似度分数 (0-1)
    """
    score = 0.0

    # 1. 精确匹配
    if template_name == kg_name:
        return 1.0

    # 2. 别名匹配
    aliases = kg_info.get('aliases', [])
    for alias in aliases:
        if template_name == alias:
            return 0.95

    # 3. 包含关系
    if kg_name in template_name or template_name in kg_name:
        score += 0.7

    # 4. 别名包含关系
    for alias in aliases:
        if alias in template_name or template_name in alias:
            score += 0.65
            break

    # 5. 关键词匹配
    template_keywords = set(extract_keywords(template_name))
    kg_keywords = set(extract_keywords(kg_name))

    if template_keywords and kg_keywords:
        intersection = template_keywords & kg_keywords
        union = template_keywords | kg_keywords

        if intersection:
            jaccard = len(intersection) / len(union)
            score += jaccard * 0.5

    return min(score, 1.0)


class TemplateCategoryMatcher:
    """模板分类匹配器"""

    def __init__(self, kg_data: Dict, category_index: Dict):
        """
        初始化匹配器

        Args:
            kg_data: 知识图谱数据
            category_index: 分类树索引
        """
        self.kg_data = kg_data
        self.category_index = category_index

    def match_template(self, template: ContractTemplate) -> Optional[Dict]:
        """
        为模板匹配最下层分类

        Args:
            template: 模板对象

        Returns:
            {
                'matched_level': 'tertiary' | 'secondary' | 'inferred',
                'category_path': [一级, 二级, 三级],
                'legal_features': dict,
                'similarity': float,
                'confidence': str
            }
            或 None（未匹配）
        """
        template_name = template.name

        # 优先级1: 精确三级分类匹配（知识图谱）
        for kg_name, kg_info in self.kg_data.items():
            if template_name == kg_name:
                return {
                    'matched_level': 'tertiary',
                    'category_path': [kg_info['category'], kg_info['subcategory'], kg_name],
                    'legal_features': kg_info['legal_features'],
                    'similarity': 1.0,
                    'confidence': '精确匹配'
                }

        # 优先级1.2: 别名匹配
        for kg_name, kg_info in self.kg_data.items():
            for alias in kg_info.get('aliases', []):
                if template_name == alias or alias in template_name:
                    return {
                        'matched_level': 'tertiary',
                        'category_path': [kg_info['category'], kg_info['subcategory'], kg_name],
                        'legal_features': kg_info['legal_features'],
                        'similarity': 0.95,
                        'confidence': '别名匹配'
                    }

        # 优先级2: 三级分类名称匹配（分类树）
        if template_name in self.category_index['by_level3']:
            level1, level2 = self.category_index['by_level3'][template_name]
            # 尝试从知识图谱获取法律特征
            kg_info = self.kg_data.get(template_name, {})
            return {
                'matched_level': 'tertiary',
                'category_path': [level1, level2, template_name],
                'legal_features': kg_info.get('legal_features'),
                'similarity': 1.0,
                'confidence': '分类树匹配'
            }

        # 优先级3: 二级分类匹配
        for level2 in self.category_index['level2_list']:
            if level2 in template_name or template.subcategory == level2:
                level1 = self.category_index['by_level2'][level2]
                # 尝试从知识图谱获取该二级分类下任意合同的特征作为参考
                kg_features = self._get_features_for_level2(level1, level2)
                return {
                    'matched_level': 'secondary',
                    'category_path': [level1, level2],
                    'legal_features': kg_features,
                    'similarity': 0.8,
                    'confidence': '二级分类匹配'
                }

        # 优先级4: 关键词推断匹配
        best_match = None
        best_score = 0.6  # 相似度阈值

        for kg_name, kg_info in self.kg_data.items():
            score = calculate_similarity(template_name, kg_name, kg_info)

            if score > best_score:
                best_score = score
                best_match = {
                    'matched_level': 'inferred',
                    'category_path': [kg_info['category'], kg_info['subcategory'], kg_name],
                    'legal_features': kg_info['legal_features'],
                    'similarity': score,
                    'confidence': '推断匹配'
                }

        return best_match

    def _get_features_for_level2(self, level1: str, level2: str) -> Optional[Dict]:
        """
        获取二级分类的参考法律特征

        Args:
            level1: 一级分类
            level2: 二级分类

        Returns:
            法律特征字典或None
        """
        # 查找该二级分类下第一个有知识图谱数据的合同类型
        for kg_name, kg_info in self.kg_data.items():
            if kg_info['category'] == level1 and kg_info['subcategory'] == level2:
                return kg_info['legal_features']
        return None


def batch_update_templates(dry_run: bool = True, limit: Optional[int] = None):
    """
    批量更新模板分类和法律特征

    Args:
        dry_run: 干运行模式，True时不实际更新数据库
        limit: 限制更新的模板数量（用于测试）
    """
    logger.info("=" * 60)
    logger.info("开始批量更新模板分类和法律特征")
    if dry_run:
        logger.info("【干运行模式】不会实际更新数据库")
    if limit:
        logger.info(f"【限制模式】只处理前 {limit} 个模板")
    logger.info("=" * 60)

    db = SessionLocal()
    try:
        # 阶段1: 数据准备
        logger.info("\n" + "=" * 60)
        logger.info("阶段1: 数据准备")
        logger.info("=" * 60)

        # 1.1 加载知识图谱
        kg_data = load_knowledge_graph()
        if not kg_data:
            logger.error("知识图谱为空，无法继续")
            return

        # 1.2 构建分类树索引
        category_index = build_category_tree_index()

        # 1.3 加载所有模板
        query = db.query(ContractTemplate)
        if limit:
            query = query.limit(limit)
        templates = query.all()

        logger.info(f"✓ 加载知识图谱: {len(kg_data)} 个合同类型")
        logger.info(f"✓ 构建分类树索引: {len(category_index['level2_list'])} 个二级分类, {len(category_index['level3_list'])} 个三级分类")
        logger.info(f"✓ 加载模板: {len(templates)} 个")

        # 阶段2: 分类映射
        logger.info("\n" + "=" * 60)
        logger.info("阶段2: 分类映射")
        logger.info("=" * 60)

        matcher = TemplateCategoryMatcher(kg_data, category_index)
        match_results = []

        for i, template in enumerate(templates, 1):
            result = matcher.match_template(template)
            match_results.append({
                'template': template,
                'match_result': result
            })

            if i % 20 == 0:
                logger.info(f"处理进度: {i}/{len(templates)} ({i*100//len(templates)}%)")

        logger.info(f"处理进度: [{('=' * 20)}] {len(templates)}/{len(templates)} (100%)")

        # 阶段3: 批量更新
        logger.info("\n" + "=" * 60)
        logger.info("阶段3: 批量更新")
        logger.info("=" * 60)

        stats = {
            'total': len(templates),
            'tertiary_matched': 0,
            'secondary_matched': 0,
            'inferred_matched': 0,
            'unmatched': 0,
            'updated': 0,
            'failed': 0
        }

        for item in match_results:
            template = item['template']
            result = item['match_result']

            if result is None:
                stats['unmatched'] += 1
                logger.warning(f"⊘ 未匹配: {template.name}")
                continue

            matched_level = result['matched_level']
            stats[f'{matched_level}_matched'] += 1

            category_path = result['category_path']
            legal_features = result.get('legal_features')

            # 保存原始分类（用于回滚）
            original_category = template.category
            original_subcategory = template.subcategory
            original_primary_type = template.primary_contract_type

            try:
                # 更新分类字段
                template.category = category_path[0]

                if matched_level in ['tertiary', 'inferred']:
                    if len(category_path) >= 3:
                        template.subcategory = category_path[-1]  # 最下层分类
                        template.primary_contract_type = category_path[1]  # 二级分类
                    else:
                        template.subcategory = category_path[-1]
                        template.primary_contract_type = category_path[-1]
                else:  # secondary
                    template.subcategory = category_path[1]
                    template.primary_contract_type = category_path[1]

                # 更新法律特征
                if legal_features:
                    template.transaction_nature = legal_features.get('transaction_nature')
                    template.contract_object = legal_features.get('contract_object')
                    template.stance = legal_features.get('stance')

                    # 合并对价类型和详情
                    consideration_type = legal_features.get('consideration_type', '')
                    consideration_detail = legal_features.get('consideration_detail', '')
                    if consideration_type or consideration_detail:
                        template.transaction_consideration = f"{consideration_type}，{consideration_detail}"

                    template.transaction_characteristics = legal_features.get('transaction_characteristics')
                    template.usage_scenario = legal_features.get('usage_scenario')

                # 更新元数据
                if not template.metadata_info:
                    template.metadata_info = {}

                # 保存原始分类用于回滚
                template.metadata_info['original_category'] = {
                    'category': original_category,
                    'subcategory': original_subcategory,
                    'primary_contract_type': original_primary_type
                }

                # 记录本次匹配信息
                template.metadata_info['category_mapping'] = {
                    'matched_level': matched_level,
                    'category_path': category_path,
                    'similarity': result.get('similarity'),
                    'confidence': result.get('confidence'),
                    'matched_at': datetime.now().isoformat()
                }

                if not dry_run:
                    db.commit()
                    db.refresh(template)

                stats['updated'] += 1

                logger.info(f"✓ {'[预览]' if dry_run else '[更新]'}: {template.name}")
                logger.info(f"  分类路径: {' > '.join(category_path)}")
                logger.info(f"  匹配级别: {matched_level}")
                logger.info(f"  置信度: {result.get('confidence')} ({result.get('similarity', 0):.2f})")

            except Exception as e:
                stats['failed'] += 1
                db.rollback()
                logger.error(f"✗ 更新失败: {template.name} - {e}")

        # 阶段4: 验证和报告
        logger.info("\n" + "=" * 60)
        logger.info("阶段4: 验证和报告")
        logger.info("=" * 60)

        # 4.1 统计报告
        logger.info("\n更新统计:")
        logger.info(f"  总模板数: {stats['total']}")
        logger.info(f"  三级分类匹配: {stats['tertiary_matched']} ({stats['tertiary_matched']*100//stats['total'] if stats['total'] > 0 else 0}%)")
        logger.info(f"  二级分类匹配: {stats['secondary_matched']} ({stats['secondary_matched']*100//stats['total'] if stats['total'] > 0 else 0}%)")
        logger.info(f"  推断匹配: {stats['inferred_matched']} ({stats['inferred_matched']*100//stats['total'] if stats['total'] > 0 else 0}%)")
        logger.info(f"  未匹配: {stats['unmatched']} ({stats['unmatched']*100//stats['total'] if stats['total'] > 0 else 0}%)")
        logger.info(f"  更新成功: {stats['updated']} ({stats['updated']*100//stats['total'] if stats['total'] > 0 else 0}%)")
        logger.info(f"  更新失败: {stats['failed']}")

        # 4.2 未匹配模板列表
        unmatched_templates = [
            item['template'].name for item in match_results
            if item['match_result'] is None
        ]
        if unmatched_templates:
            logger.info(f"\n未匹配的模板 ({len(unmatched_templates)}个):")
            for name in unmatched_templates[:10]:  # 只显示前10个
                logger.info(f"  - {name}")
            if len(unmatched_templates) > 10:
                logger.info(f"  ... 还有 {len(unmatched_templates) - 10} 个")

        # 4.3 生成详细日志文件
        log_file = project_root / "scripts" / f"update_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'dry_run': dry_run,
                    'limit': limit,
                    'stats': stats,
                    'unmatched_templates': unmatched_templates,
                    'matched_templates': [
                        {
                            'name': item['template'].name,
                            'matched_level': item['match_result']['matched_level'] if item['match_result'] else None,
                            'category_path': item['match_result']['category_path'] if item['match_result'] else None,
                            'confidence': item['match_result']['confidence'] if item['match_result'] else None,
                        }
                        for item in match_results if item['match_result']
                    ]
                }, f, ensure_ascii=False, indent=2)
            logger.info(f"\n详细日志已保存至: {log_file}")
        except Exception as e:
            logger.warning(f"保存详细日志失败: {e}")

        logger.info("\n" + "=" * 60)
        logger.info("批量更新完成")
        logger.info("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='批量更新合同模板的分类信息和法律特征')
    parser.add_argument('--dry-run', action='store_true', help='干运行模式，不实际更新数据库')
    parser.add_argument('--limit', type=int, help='限制处理的模板数量（用于测试）')

    args = parser.parse_args()

    try:
        # 默认使用干运行模式，除非明确指定 --no-dry-run
        if '--dry-run' not in sys.argv and '-n' not in sys.argv:
            logger.info("默认使用干运行模式，如需实际更新请添加 --dry-run 参数")
            args.dry_run = True

        batch_update_templates(dry_run=args.dry_run, limit=args.limit)
    except KeyboardInterrupt:
        logger.info("\n用户中断操作")
    except Exception as e:
        logger.error(f"批量更新失败: {e}", exc_info=True)
        sys.exit(1)
