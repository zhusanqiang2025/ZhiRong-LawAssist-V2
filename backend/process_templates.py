#!/usr/bin/env python3
"""
合同模板处理脚本

功能：
1. 将数据库中的模板与知识图谱匹配
2. 从模板Markdown文件中提取结构信息（目录、条款）
3. 为模板关联完整的知识图谱法律特征
4. 生成结构化数据供AI合同生成使用
"""
import sys
import os
import json
import re
from typing import Dict, List, Tuple, Optional
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接从模块文件导入，绕过数据库依赖
import importlib.util

# 加载 contract_knowledge_graph 模块
spec = importlib.util.spec_from_file_location(
    "contract_knowledge_graph",
    os.path.join(os.path.dirname(__file__), "app", "services", "legal_features", "contract_knowledge_graph.py")
)
ckg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ckg_module)

get_contract_knowledge_graph = ckg_module.get_contract_knowledge_graph


# ==================== 模板结构提取器 ====================

class TemplateStructureExtractor:
    """从Markdown模板中提取结构信息"""

    # 常见条款模式（基于中文合同模板）
    CLAUSE_PATTERNS = {
        "保密条款": [r"保密.*条款", r"保密义务", r"保密约定"],
        "违约责任": [r"违约.*责任", r"违约.*条款", r"违约金"],
        "争议解决": [r"争议.*解决", r"仲裁", r"诉讼.*管辖"],
        "终止解除": [r"合同.*终止", r"合同.*解除", r"终止.*条款"],
        "不可抗力": [r"不可抗力"],
        "通知条款": [r"通知.*条款", r"通知.*方式"],
        "适用法律": [r"适用.*法律", r"法律.*适用"],
        "生效条件": [r"生效.*条件", r"合同.*生效"],
        "变更修改": [r"合同.*变更", r"合同.*修改", r"补充协议"],
        "权利义务": [r"权利.*义务", r"甲方.*权利", r"乙方.*义务"],
        "付款条款": [r"付款.*方式", r"付款.*期限", r"结算.*方式"],
        "交付条款": [r"交付.*方式", r"交付.*时间", r"交付.*地点"],
        "质量条款": [r"质量.*标准", r"质量.*要求", r"验收.*标准"],
        "知识产权": [r"知识产权", r"专利.*权", r"著作权"],
        "保证陈述": [r"保证.*陈述", r"声明.*保证", r"陈述.*保证"],
        "赔偿条款": [r"赔偿.*条款", r"损害.*赔偿", r"赔偿.*责任"],
        "转让条款": [r"权利.*转让", r"合同.*转让", r"义务.*转让"],
        "分包条款": [r"分包.*条款", r"转包"],
        "竞业限制": [r"竞业.*限制", r"竞业.*禁止"],
        "劳动保护": [r"劳动.*保护", r"安全.*生产", r"职业.*健康"],
        "保险条款": [r"保险.*条款", r"保险.*责任"],
    }

    def __init__(self):
        """初始化提取器"""
        # 编译正则表达式
        self.compiled_patterns = {}
        for clause_type, patterns in self.CLAUSE_PATTERNS.items():
            self.compiled_patterns[clause_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

    def extract_structure(self, markdown_content: str) -> Dict:
        """
        从Markdown内容中提取结构信息

        返回:
        {
            "sections": [{"level": 1, "title": "...", "content_snippet": "..."}],
            "clauses": {"保密条款": True, "违约责任": True, ...},
            "key_terms": {"主体": [], "标的": [], "期限": [], "金额": []},
            "structure_summary": "..."
        }
        """
        result = {
            "sections": self._extract_sections(markdown_content),
            "clauses": self._extract_clauses(markdown_content),
            "key_terms": self._extract_key_terms(markdown_content),
            "structure_summary": ""
        }

        # 生成结构摘要
        result["structure_summary"] = self._generate_structure_summary(result)

        return result

    def _extract_sections(self, content: str) -> List[Dict]:
        """提取Markdown章节结构"""
        sections = []
        lines = content.split('\n')

        for line in lines:
            # 匹配Markdown标题 (# ## ### 等)
            match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                # 跳过过短的标题
                if len(title) < 2:
                    continue

                sections.append({
                    "level": level,
                    "title": title
                })

        return sections

    def _extract_clauses(self, content: str) -> Dict[str, bool]:
        """提取是否包含特定条款"""
        found_clauses = {}

        for clause_type, patterns in self.compiled_patterns.items():
            found = False
            for pattern in patterns:
                if pattern.search(content):
                    found = True
                    break
            found_clauses[clause_type] = found

        return found_clauses

    def _extract_key_terms(self, content: str) -> Dict[str, List[str]]:
        """提取关键术语"""
        terms = {
            "主体": [],
            "标的": [],
            "期限": [],
            "金额": [],
        }

        lines = content.split('\n')

        # 提取甲方/乙方
        party_patterns = [
            re.compile(r'甲方[：:]\s*([^，,。\n]+)'),
            re.compile(r'乙方[：:]\s*([^，,。\n]+)'),
            re.compile(r'委托方[：:]\s*([^，,。\n]+)'),
            re.compile(r'受托方[：:]\s*([^，,。\n]+)')
        ]
        for pattern in party_patterns:
            matches = pattern.findall(content)
            terms["主体"].extend([m.strip() for m in matches if len(m.strip()) > 1])

        # 提取期限
        period_patterns = [
            re.compile(r'(\d+\s*[天月年])'),
            re.compile(r'(\d{4}年\d{1,2}月\d{1,2}日)'),
            re.compile(r'(自.*之日起.*之.*日)'),
        ]
        for pattern in period_patterns:
            matches = pattern.findall(content)
            terms["期限"].extend(matches)

        # 提取金额
        money_patterns = [
            re.compile(r'([\d,，]+\.\d{2}\s*[元圆])'),
            re.compile(r'([人民币美元港元]\s*[\d,，]+\.?\d*)'),
            re.compile(r'(¥\$US\$)\s*[\d,，]+\.?\d*'),
        ]
        for pattern in money_patterns:
            matches = pattern.findall(content)
            terms["金额"].extend(matches)

        # 去重并限制数量
        for key in terms:
            terms[key] = list(set(terms[key]))[:10]

        return terms

    def _generate_structure_summary(self, structure: Dict) -> str:
        """生成结构摘要"""
        parts = []

        # 章节信息
        if structure["sections"]:
            top_sections = [s["title"] for s in structure["sections"][:5]]
            parts.append(f"包含 {len(structure['sections'])} 个章节: {', '.join(top_sections)}")

        # 条款信息
        found_clauses = [k for k, v in structure["clauses"].items() if v]
        if found_clauses:
            parts.append(f"包含 {len(found_clauses)} 个标准条款: {', '.join(found_clauses[:8])}")

        return "; ".join(parts)


# ==================== 模板-知识图谱匹配器 ====================

class TemplateKnowledgeMatcher:
    """将模板与知识图谱进行智能匹配"""

    def __init__(self):
        self.kg = get_contract_knowledge_graph()
        self.extractor = TemplateStructureExtractor()

    def match_template(self, template_name: str, category: str = None,
                       subcategory: str = None, markdown_content: str = None) -> Optional[Dict]:
        """
        匹配模板到知识图谱

        返回匹配结果:
        {
            "matched": True/False,
            "contract_type": "匹配的合同类型",
            "match_method": "name/category/fuzzy",
            "match_score": 0.0-1.0,
            "legal_features": {...},
            "extracted_structure": {...}
        }
        """
        result = {
            "matched": False,
            "contract_type": None,
            "match_method": None,
            "match_score": 0.0,
            "legal_features": None,
            "extracted_structure": None
        }

        # 1. 精确名称匹配
        definition = self.kg.get_by_name(template_name)
        if definition:
            result.update({
                "matched": True,
                "contract_type": definition.name,
                "match_method": "name_exact",
                "match_score": 1.0,
                "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
            })
            return result

        # 2. 类别匹配
        if category:
            definitions = self.kg.get_by_category(category, subcategory)
            if definitions and len(definitions) == 1:
                definition = definitions[0]
                result.update({
                    "matched": True,
                    "contract_type": definition.name,
                    "match_method": "category_single",
                    "match_score": 0.8,
                    "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
                })
                return result

        # 3. 模糊匹配（如果有内容）
        if markdown_content:
            fuzzy_result = self._fuzzy_match(template_name, category, markdown_content)
            if fuzzy_result:
                result.update(fuzzy_result)
                return result

        # 4. 关键词搜索匹配
        if template_name:
            search_results = self.kg.search_by_keywords(template_name)
            if search_results:
                definition, score = search_results[0]
                result.update({
                    "matched": True,
                    "contract_type": definition.name,
                    "match_method": "keyword_search",
                    "match_score": score,
                    "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
                })
                return result

        return result

    def _fuzzy_match(self, template_name: str, category: str,
                     content: str) -> Optional[Dict]:
        """基于内容进行模糊匹配"""
        # 提取结构
        structure = self.extractor.extract_structure(content)

        # 尝试从章节标题中推断合同类型
        section_titles = [s["title"] for s in structure["sections"]]

        # 遍历知识图谱，查找匹配项
        for name, definition in self.kg._contract_types.items():
            # 检查别名匹配
            if hasattr(definition, 'aliases'):
                for alias in definition.aliases:
                    if alias in template_name or template_name in alias:
                        return {
                            "matched": True,
                            "contract_type": definition.name,
                            "match_method": "alias_match",
                            "match_score": 0.7,
                            "legal_features": definition.legal_features.to_dict() if definition.legal_features else None,
                            "extracted_structure": structure
                        }

        return None

    def extract_template_structure(self, markdown_content: str) -> Dict:
        """提取模板结构"""
        return self.extractor.extract_structure(markdown_content)


# ==================== 批处理脚本主函数 ====================

def process_templates_from_db():
    """
    从数据库读取模板并处理

    注意：此函数需要数据库连接，如果数据库不可用，
    可以使用 process_templates_from_list() 处理手动列表
    """
    print("=" * 60)
    print("从数据库处理合同模板")
    print("=" * 60)

    try:
        from app.database import SessionLocal
        from app.models.contract_template import ContractTemplate

        db = SessionLocal()
        matcher = TemplateKnowledgeMatcher()

        try:
            # 获取所有模板
            templates = db.query(ContractTemplate).filter(
                ContractTemplate.status == "active"
            ).all()

            print(f"\n找到 {len(templates)} 个活跃模板")

            # 统计
            updated_count = 0
            matched_count = 0
            extracted_count = 0
            errors = []

            for template in templates:
                try:
                    print(f"\n处理模板: {template.name}")

                    # 读取Markdown内容
                    markdown_content = ""
                    if template.file_url and os.path.exists(template.file_url):
                        with open(template.file_url, 'r', encoding='utf-8') as f:
                            markdown_content = f.read()

                    # 匹配知识图谱
                    match_result = matcher.match_template(
                        template.name,
                        template.category,
                        template.subcategory,
                        markdown_content
                    )

                    # 提取结构
                    structure = None
                    if markdown_content:
                        structure = matcher.extract_template_structure(markdown_content)
                        extracted_count += 1

                    # 更新模板的 metadata_info
                    if not template.metadata_info:
                        template.metadata_info = {}

                    # 保存匹配结果
                    if match_result["matched"]:
                        matched_count += 1
                        template.metadata_info["knowledge_graph_match"] = {
                            "contract_type": match_result["contract_type"],
                            "match_method": match_result["match_method"],
                            "match_score": match_result["match_score"],
                            "legal_features": match_result["legal_features"]
                        }

                        # 如果V2字段为空，使用知识图谱填充
                        if not template.transaction_nature and match_result["legal_features"]:
                            template.transaction_nature = match_result["legal_features"].get("transaction_nature")
                        if not template.contract_object and match_result["legal_features"]:
                            template.contract_object = match_result["legal_features"].get("contract_object")
                        if not template.complexity and match_result["legal_features"]:
                            template.complexity = match_result["legal_features"].get("complexity")
                        if not template.stance and match_result["legal_features"]:
                            template.stance = match_result["legal_features"].get("stance")

                        print(f"  [匹配] {match_result['contract_type']} ({match_result['match_method']}, 评分={match_result['match_score']:.2f})")

                    # 保存结构信息
                    if structure:
                        template.metadata_info["extracted_structure"] = structure
                        print(f"  [结构] 提取了 {len(structure['sections'])} 个章节, {sum(structure['clauses'].values())} 个条款")

                    # 更新使用场景（从知识图谱）
                    if match_result["legal_features"] and match_result["legal_features"].get("usage_scenario"):
                        if not template.usage_scenario:
                            template.usage_scenario = match_result["legal_features"]["usage_scenario"]

                    # 更新推荐模板列表（反向链接）
                    if match_result["matched"]:
                        # 将此模板ID添加到知识图谱的推荐列表中
                        kg = get_contract_knowledge_graph()
                        contract_type = match_result["contract_type"]
                        if contract_type in kg._contract_types:
                            ct_def = kg._contract_types[contract_type]
                            if hasattr(ct_def, 'recommended_template_ids'):
                                if template.id not in ct_def.recommended_template_ids:
                                    ct_def.recommended_template_ids.append(template.id)

                    updated_count += 1
                    db.commit()

                except Exception as e:
                    errors.append(f"{template.name}: {str(e)}")
                    print(f"  [错误] {str(e)}")
                    db.rollback()

            # 保存知识图谱更新
            print(f"\n保存知识图谱更新...")
            kg = get_contract_knowledge_graph()
            kg.save_to_file()
            print(f"[OK] 知识图谱已更新")

            # 打印统计
            print("\n" + "=" * 60)
            print("处理完成")
            print("=" * 60)
            print(f"总模板数: {len(templates)}")
            print(f"成功匹配: {matched_count}")
            print(f"结构提取: {extracted_count}")
            print(f"更新成功: {updated_count}")
            print(f"错误: {len(errors)}")

            if errors:
                print("\n错误详情:")
                for error in errors[:10]:
                    print(f"  - {error}")

        finally:
            db.close()

    except ImportError as e:
        print(f"\n[错误] 数据库模块不可用: {e}")
        print("提示: 请确保数据库已配置，或使用 process_templates_from_list() 处理手动列表")
    except Exception as e:
        print(f"\n[错误] 处理失败: {e}")
        import traceback
        traceback.print_exc()


def process_templates_from_list(template_list: List[Dict]):
    """
    处理手动提供的模板列表

    Args:
        template_list: [
            {
                "name": "模板名称",
                "file_path": "文件路径",
                "category": "分类（可选）",
                "subcategory": "子分类（可选）"
            },
            ...
        ]
    """
    print("=" * 60)
    print("处理手动提供的模板列表")
    print("=" * 60)

    matcher = TemplateKnowledgeMatcher()

    processed = 0
    matched = 0
    extracted = 0
    results = []

    for template_info in template_list:
        name = template_info["name"]
        file_path = template_info["file_path"]
        category = template_info.get("category")
        subcategory = template_info.get("subcategory")

        print(f"\n处理: {name}")

        # 读取内容
        if not os.path.exists(file_path):
            print(f"  [跳过] 文件不存在: {file_path}")
            continue

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"  [错误] 读取文件失败: {e}")
            continue

        # 匹配知识图谱
        match_result = matcher.match_template(name, category, subcategory, content)

        # 提取结构
        structure = matcher.extract_template_structure(content)

        result = {
            "name": name,
            "file_path": file_path,
            "category": category,
            "subcategory": subcategory,
            "match_result": match_result,
            "extracted_structure": structure
        }
        results.append(result)

        processed += 1
        if match_result["matched"]:
            matched += 1
        extracted += 1

        # 打印结果
        if match_result["matched"]:
            print(f"  [匹配] {match_result['contract_type']} ({match_result['match_method']}, 评分={match_result['match_score']:.2f})")
        else:
            print(f"  [未匹配] 未找到匹配的知识图谱条目")

        print(f"  [结构] {len(structure['sections'])} 个章节, {sum(structure['clauses'].values())} 个条款")

    # 保存结果
    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)
    print(f"处理: {processed}")
    print(f"匹配: {matched}")
    print(f"提取: {extracted}")

    # 输出JSON结果
    output_file = os.path.join(os.path.dirname(__file__), "template_processing_results.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_file}")

    return results


# ==================== 测试函数 ====================

def test_matcher():
    """测试匹配器功能"""
    print("=" * 60)
    print("测试模板-知识图谱匹配器")
    print("=" * 60)

    matcher = TemplateKnowledgeMatcher()

    # 测试用例
    test_cases = [
        {"name": "不动产买卖合同", "category": "民法典典型合同"},
        {"name": "房屋买卖协议", "category": None},
        {"name": "劳动合同", "category": "劳动与人力资源"},
        {"name": "软件开发服务合同", "category": None},
    ]

    for test in test_cases:
        print(f"\n测试: {test['name']} ({test.get('category', 'N/A')})")
        result = matcher.match_template(test["name"], test.get("category"))
        if result["matched"]:
            print(f"  [OK] 匹配到: {result['contract_type']}")
            print(f"       方法: {result['match_method']}, 评分: {result['match_score']:.2f}")
        else:
            print(f"  [未匹配]")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="处理合同模板")
    parser.add_argument("--mode", choices=["db", "test"], default="db",
                       help="运行模式: db=从数据库处理, test=测试匹配器")
    parser.add_argument("--list", help="模板列表JSON文件路径")

    args = parser.parse_args()

    if args.mode == "db":
        process_templates_from_db()
    elif args.mode == "test":
        test_matcher()
