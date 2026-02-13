#!/usr/bin/env python3
"""
处理 templates_source 目录中的模板文件

文件命名格式: 类别_子类别_合同名称.md
例如: 非典型合同_股权类协议_股权代持协议书.md
"""
import sys
import os
import json
import re
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接从模块文件导入
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

    CLAUSE_PATTERNS = {
        "保密条款": [r"保密.*条款", r"保密义务", r"保密约定", r"保密协议"],
        "违约责任": [r"违约.*责任", r"违约.*条款", r"违约金"],
        "争议解决": [r"争议.*解决", r"仲裁", r"诉讼.*管辖"],
        "终止解除": [r"合同.*终止", r"合同.*解除", r"终止.*条款"],
        "不可抗力": [r"不可抗力"],
        "通知条款": [r"通知.*条款", r"通知.*方式"],
        "适用法律": [r"适用.*法律", r"法律.*适用"],
        "生效条件": [r"生效.*条件", r"合同.*生效"],
        "变更修改": [r"合同.*变更", r"合同.*修改", r"补充协议"],
        "权利义务": [r"权利.*义务", r"甲方.*权利", r"乙方.*义务"],
        "付款条款": [r"付款.*方式", r"付款.*期限", r"结算.*方式", r"借款.*金额", r"转让.*价格"],
        "交付条款": [r"交付.*方式", r"交付.*时间", r"交付.*地点"],
        "质量条款": [r"质量.*标准", r"质量.*要求", r"验收.*标准"],
        "知识产权": [r"知识产权", r"专利.*权", r"著作权"],
        "保证陈述": [r"保证.*陈述", r"声明.*保证", r"陈述.*保证"],
        "赔偿条款": [r"赔偿.*条款", r"损害.*赔偿", r"赔偿.*责任"],
        "转让条款": [r"权利.*转让", r"合同.*转让", r"义务.*转让", r"股权.*转让"],
        "分包条款": [r"分包.*条款", r"转包"],
        "竞业限制": [r"竞业.*限制", r"竞业.*禁止"],
        "劳动保护": [r"劳动.*保护", r"安全.*生产", r"职业.*健康"],
        "保险条款": [r"保险.*条款", r"保险.*责任"],
        "担保条款": [r"担保", r"保证.*担保", r"担保物权"],
        "利息条款": [r"利息", r"利率", r"年化"],
        "股权条款": [r"股权", r"股份", r"股东", r"出资"],
    }

    def __init__(self):
        self.compiled_patterns = {}
        for clause_type, patterns in self.CLAUSE_PATTERNS.items():
            self.compiled_patterns[clause_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

    def extract_structure(self, markdown_content: str) -> Dict:
        """从Markdown内容中提取结构信息"""
        result = {
            "sections": self._extract_sections(markdown_content),
            "clauses": self._extract_clauses(markdown_content),
            "key_terms": self._extract_key_terms(markdown_content),
            "structure_summary": ""
        }
        result["structure_summary"] = self._generate_structure_summary(result)
        return result

    def _extract_sections(self, content: str) -> List[Dict]:
        """提取Markdown章节结构"""
        sections = []
        lines = content.split('\n')

        for line in lines:
            match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                if len(title) < 2:
                    continue
                sections.append({"level": level, "title": title})

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
        terms = {"主体": [], "标的": [], "期限": [], "金额": [], "股权": []}

        # 提取甲方/乙方/股东等主体
        party_patterns = [
            re.compile(r'甲方[：:]\s*([^，,。\n]+)'),
            re.compile(r'乙方[：:]\s*([^，,。\n]+)'),
            re.compile(r'委托方[：:]\s*([^，,。\n]+)'),
            re.compile(r'受托方[：:]\s*([^，,。\n]+)'),
            re.compile(r'转让方[：:]\s*([^，,。\n]+)'),
            re.compile(r'受让方[：:]\s*([^，,。\n]+)'),
            re.compile(r'股东[：:]\s*([^，,。\n]+)'),
            re.compile(r'合伙人[：:]\s*([^，,。\n]+)'),
        ]
        for pattern in party_patterns:
            matches = pattern.findall(content)
            terms["主体"].extend([m.strip() for m in matches if len(m.strip()) > 1])

        # 提取股权信息
        equity_patterns = [
            re.compile(r'(\d+[%％])'),
            re.compile(r'([\d,，]+\s*[股元美元])'),
            re.compile(r'(注册资本[：:][^，,。\n]+)'),
        ]
        for pattern in equity_patterns:
            matches = pattern.findall(content)
            terms["股权"].extend(matches)

        # 提取期限
        period_patterns = [
            re.compile(r'(\d+\s*[天月年])'),
            re.compile(r'(\d{4}年\d{1,2}月\d{1,2}日)'),
        ]
        for pattern in period_patterns:
            matches = pattern.findall(content)
            terms["期限"].extend(matches)

        # 提取金额
        money_patterns = [
            re.compile(r'([\d,，]+\.\d{2}\s*[元圆])'),
            re.compile(r'([人民币美元港元]\s*[\d,，]+\.?\d*)'),
            re.compile(r'(¥|\$|US\$)\s*[\d,，]+\.?\d*'),
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

        if structure["sections"]:
            top_sections = [s["title"] for s in structure["sections"][:5]]
            parts.append(f"包含 {len(structure['sections'])} 个章节")

        found_clauses = [k for k, v in structure["clauses"].items() if v]
        if found_clauses:
            parts.append(f"包含 {len(found_clauses)} 个标准条款")

        return "; ".join(parts)


# ==================== 模板-知识图谱匹配器 ====================

class TemplateKnowledgeMatcher:
    """将模板与知识图谱进行智能匹配"""

    def __init__(self):
        self.kg = get_contract_knowledge_graph()
        self.extractor = TemplateStructureExtractor()

    def match_template(self, template_name: str, category: str = None,
                       subcategory: str = None, markdown_content: str = None) -> Dict:
        """匹配模板到知识图谱"""
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

        # 2. 别名匹配
        for name, definition in self.kg._contract_types.items():
            if hasattr(definition, 'aliases'):
                for alias in definition.aliases:
                    if alias in template_name or template_name in alias:
                        result.update({
                            "matched": True,
                            "contract_type": definition.name,
                            "match_method": "alias_match",
                            "match_score": 0.75,
                            "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
                        })
                        return result

        # 3. 类别匹配
        if category:
            definitions = self.kg.get_by_category(category, subcategory)
            if definitions:
                # 如果只有一个结果，直接匹配
                if len(definitions) == 1:
                    definition = definitions[0]
                    result.update({
                        "matched": True,
                        "contract_type": definition.name,
                        "match_method": "category_single",
                        "match_score": 0.6,
                        "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
                    })
                    return result
                # 如果有多个结果，找别名最匹配的
                for definition in definitions:
                    if hasattr(definition, 'aliases'):
                        for alias in definition.aliases:
                            if alias in template_name or template_name in alias:
                                result.update({
                                    "matched": True,
                                    "contract_type": definition.name,
                                    "match_method": "category_alias_match",
                                    "match_score": 0.7,
                                    "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
                                })
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
                    "match_score": float(score),
                    "legal_features": definition.legal_features.to_dict() if definition.legal_features else None
                })
                return result

        return result

    def extract_template_structure(self, markdown_content: str) -> Dict:
        """提取模板结构"""
        return self.extractor.extract_structure(markdown_content)


# ==================== 文件名解析器 ====================

def parse_template_filename(filename: str) -> Dict:
    """
    解析模板文件名

    格式: 类别_子类别_合同名称.md
    例如: 非典型合同_股权类协议_股权代持协议书.md

    Returns:
        {
            "category": "类别",
            "subcategory": "子类别",
            "contract_name": "合同名称",
            "full_name": "完整名称"
        }
    """
    # 移除 .md 后缀
    name = filename.replace('.md', '')

    parts = name.split('_')

    result = {
        "category": None,
        "subcategory": None,
        "contract_name": None,
        "full_name": name
    }

    if len(parts) >= 3:
        result["category"] = parts[0]
        result["subcategory"] = parts[1]
        result["contract_name"] = '_'.join(parts[2:])
    elif len(parts) == 2:
        result["category"] = parts[0]
        result["contract_name"] = parts[1]
    else:
        result["contract_name"] = name

    return result


# ==================== 主处理函数 ====================

def process_templates_source():
    """处理 templates_source 目录中的所有模板"""
    print("=" * 60)
    print("处理 templates_source 目录中的模板")
    print("=" * 60)

    # 模板源目录
    source_dir = os.path.join(
        os.path.dirname(__file__),
        "templates_source"
    )

    if not os.path.exists(source_dir):
        print(f"\n[错误] 目录不存在: {source_dir}")
        return

    # 获取所有 .md 文件
    files = [f for f in os.listdir(source_dir) if f.endswith('.md')]

    if not files:
        print("\n[错误] 未找到任何 .md 文件")
        return

    print(f"\n找到 {len(files)} 个模板文件")

    # 初始化处理器
    matcher = TemplateKnowledgeMatcher()

    # 处理每个文件
    results = []
    matched_count = 0
    unmatched_files = []
    errors = []

    for i, filename in enumerate(files, 1):
        print(f"\n[{i}/{len(files)}] {filename}")

        try:
            # 解析文件名
            name_info = parse_template_filename(filename)
            print(f"  类别: {name_info['category']}")
            print(f"  子类别: {name_info['subcategory']}")
            print(f"  合同名: {name_info['contract_name']}")

            # 读取文件内容
            file_path = os.path.join(source_dir, filename)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                print(f"  [跳过] 文件为空")
                continue

            # 匹配知识图谱
            match_result = matcher.match_template(
                name_info['contract_name'],
                name_info['category'],
                name_info['subcategory'],
                content
            )

            # 提取结构
            structure = matcher.extract_template_structure(content)

            result = {
                "filename": filename,
                "name_info": name_info,
                "match_result": match_result,
                "extracted_structure": structure
            }
            results.append(result)

            # 打印结果
            if match_result["matched"]:
                matched_count += 1
                print(f"  [匹配] {match_result['contract_type']}")
                print(f"         方法: {match_result['match_method']}, 评分: {match_result['match_score']:.2f}")
            else:
                unmatched_files.append(filename)
                print(f"  [未匹配] 未找到匹配的知识图谱条目")

            print(f"  [结构] {structure['structure_summary']}")

        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
            print(f"  [错误] {str(e)}")

    # 保存结果
    print("\n" + "=" * 60)
    print("保存结果...")
    print("=" * 60)

    output_dir = os.path.join(os.path.dirname(__file__), "template_processing_output")
    os.makedirs(output_dir, exist_ok=True)

    # 保存详细结果
    results_file = os.path.join(output_dir, "templates_source_results.json")
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"详细结果: {results_file}")

    # 保存汇总
    summary = {
        "total_files": len(files),
        "matched_count": matched_count,
        "unmatched_count": len(unmatched_files),
        "match_rate": f"{matched_count/len(files)*100:.1f}%" if files else "0%",
        "unmatched_files": unmatched_files,
        "errors": errors
    }

    summary_file = os.path.join(output_dir, "templates_source_summary.json")
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"汇总报告: {summary_file}")

    # 保存未匹配文件列表供后续处理
    if unmatched_files:
        unmatched_file = os.path.join(output_dir, "unmatched_files.txt")
        with open(unmatched_file, 'w', encoding='utf-8') as f:
            for filename in unmatched_files:
                f.write(filename + '\n')
        print(f"未匹配文件: {unmatched_file}")

    # 打印统计
    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)
    print(f"总文件数: {len(files)}")
    print(f"成功匹配: {matched_count} ({summary['match_rate']})")
    print(f"未匹配: {len(unmatched_files)}")
    print(f"错误: {len(errors)}")

    if errors:
        print("\n错误详情:")
        for error in errors[:10]:
            print(f"  - {error}")

    # 打印匹配的合同类型统计
    if matched_count > 0:
        print("\n匹配的合同类型统计:")
        matched_types = {}
        for result in results:
            if result["match_result"]["matched"]:
                contract_type = result["match_result"]["contract_type"]
                matched_types[contract_type] = matched_types.get(contract_type, 0) + 1

        for contract_type, count in sorted(matched_types.items(), key=lambda x: -x[1]):
            print(f"  - {contract_type}: {count} 个")

    return results


if __name__ == "__main__":
    process_templates_source()
