#!/usr/bin/env python3
"""
独立版本的模板处理脚本
不依赖数据库，直接扫描storage目录中的模板文件进行处理
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

    # 常见条款模式
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
        "付款条款": [r"付款.*方式", r"付款.*期限", r"结算.*方式", r"借款.*金额"],
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
        "担保条款": [r"担保", r"保证.*担保"],
        "利息条款": [r"利息", r"利率", r"年化"],
    }

    def __init__(self):
        """初始化提取器"""
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
        terms = {"主体": [], "标的": [], "期限": [], "金额": []}

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
            re.compile(r'(¥|\$|US\$)\s*[\d,，]+\.?\d*'),
            re.compile(r'借款.*人民币[【\[].*[\]】]'),
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
            parts.append(f"包含 {len(structure['sections'])} 个章节: {', '.join(top_sections)}")

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

        # 3. 别名匹配
        for name, definition in self.kg._contract_types.items():
            if hasattr(definition, 'aliases'):
                for alias in definition.aliases:
                    if alias in template_name or template_name in alias:
                        result.update({
                            "matched": True,
                            "contract_type": definition.name,
                            "match_method": "alias_match",
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


# ==================== 文件扫描器 ====================

class TemplateFileScanner:
    """扫描storage目录中的模板文件"""

    def __init__(self, base_dir: str = None):
        """初始化扫描器

        Args:
            base_dir: 项目根目录，默认为脚本所在目录
        """
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        self.base_dir = base_dir
        self.matcher = TemplateKnowledgeMatcher()

        # 可能的模板存储路径
        self.storage_paths = [
            os.path.join(base_dir, "storage", "templates"),
            os.path.join(base_dir, "..", "storage", "templates"),
            os.path.join(os.path.dirname(base_dir), "storage", "templates"),
        ]

    def find_template_files(self) -> List[Dict]:
        """扫描所有模板文件

        Returns:
            [
                {
                    "file_path": "完整路径",
                    "relative_path": "相对路径",
                    "filename": "文件名",
                    "size": 文件大小,
                    "name_hint": "从文件名推测的模板名称"
                },
                ...
            ]
        """
        templates = []

        for storage_path in self.storage_paths:
            if not os.path.exists(storage_path):
                continue

            # 扫描markdown目录
            markdown_path = os.path.join(storage_path, "markdown")
            if os.path.exists(markdown_path):
                templates.extend(self._scan_directory(markdown_path))

            # 扫描根目录
            templates.extend(self._scan_directory(storage_path))

        return templates

    def _scan_directory(self, directory: str) -> List[Dict]:
        """扫描单个目录"""
        templates = []

        try:
            for filename in os.listdir(directory):
                if not filename.endswith('.md'):
                    continue

                file_path = os.path.join(directory, filename)
                if not os.path.isfile(file_path):
                    continue

                # 跳过空文件
                if os.path.getsize(file_path) == 0:
                    continue

                # 推测模板名称
                name_hint = self._extract_name_from_filename(filename)

                templates.append({
                    "file_path": file_path,
                    "relative_path": os.path.relpath(file_path, self.base_dir),
                    "filename": filename,
                    "size": os.path.getsize(file_path),
                    "name_hint": name_hint
                })
        except Exception as e:
            print(f"[Warning] 扫描目录失败 {directory}: {e}")

        return templates

    def _extract_name_from_filename(self, filename: str) -> str:
        """从文件名推测模板名称"""
        # 移除.md后缀
        name = filename.replace('.md', '')

        # 移除UUID前缀 (格式: xxx-name.md 或 xxx_name.md)
        # 匹配32位十六进制字符
        name = re.sub(r'^[a-f0-9]{32}[-_]?', '', name)
        name = re.sub(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}[-_]?', '', name)

        # 移除常见的文件前缀
        name = re.sub(r'^[\d_]+[-_]?', '', name)

        return name.strip()


# ==================== 主处理函数 ====================

def process_standalone_templates():
    """独立处理模板文件（不依赖数据库）"""
    print("=" * 60)
    print("独立模板处理脚本")
    print("=" * 60)

    # 扫描模板文件
    print("\n[1/3] 扫描模板文件...")
    scanner = TemplateFileScanner()
    templates = scanner.find_template_files()

    if not templates:
        print("[错误] 未找到任何模板文件")
        print(f"搜索路径: {scanner.storage_paths}")
        return

    print(f"找到 {len(templates)} 个模板文件")

    # 处理每个模板
    print("\n[2/3] 处理模板...")

    results = []
    matched_count = 0
    extracted_count = 0
    errors = []

    for i, template_info in enumerate(templates, 1):
        file_path = template_info["file_path"]
        name_hint = template_info["name_hint"]

        print(f"\n[{i}/{len(templates)}] {name_hint or template_info['filename']}")

        try:
            # 读取内容
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                print(f"  [跳过] 文件为空")
                continue

            # 匹配知识图谱
            match_result = scanner.matcher.match_template(name_hint, None, None, content)

            # 提取结构
            structure = scanner.matcher.extract_template_structure(content)

            result = {
                "template_info": template_info,
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
                print(f"  [未匹配] 未找到匹配的知识图谱条目")

            extracted_count += 1
            print(f"  [结构] {len(structure['sections'])} 个章节, {sum(structure['clauses'].values())} 个条款")

        except Exception as e:
            errors.append(f"{template_info['filename']}: {str(e)}")
            print(f"  [错误] {str(e)}")

    # 保存结果
    print("\n[3/3] 保存结果...")

    output_file = os.path.join(
        os.path.dirname(__file__),
        "template_processing_results.json"
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_file}")

    # 生成汇总报告
    summary = {
        "total_templates": len(templates),
        "matched_templates": matched_count,
        "extracted_templates": extracted_count,
        "match_rate": f"{matched_count/len(templates)*100:.1f}%" if templates else "0%",
        "errors": errors
    }

    summary_file = os.path.join(
        os.path.dirname(__file__),
        "template_processing_summary.json"
    )

    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"汇总报告已保存到: {summary_file}")

    # 打印统计
    print("\n" + "=" * 60)
    print("处理完成")
    print("=" * 60)
    print(f"总模板数: {len(templates)}")
    print(f"成功匹配: {matched_count} ({summary['match_rate']})")
    print(f"结构提取: {extracted_count}")
    print(f"错误: {len(errors)}")

    if errors:
        print("\n错误详情:")
        for error in errors:
            print(f"  - {error}")

    # 打印匹配的合同类型列表
    if matched_count > 0:
        print("\n匹配的合同类型:")
        matched_types = {}
        for result in results:
            if result["match_result"]["matched"]:
                contract_type = result["match_result"]["contract_type"]
                matched_types[contract_type] = matched_types.get(contract_type, 0) + 1

        for contract_type, count in sorted(matched_types.items()):
            print(f"  - {contract_type}: {count} 个模板")

    return results


# ==================== 测试函数 ====================

def test_structure_extractor():
    """测试结构提取器"""
    print("=" * 60)
    print("测试结构提取器")
    print("=" * 60)

    # 示例内容
    sample_content = """# 借款协议

甲方（出借方）：XXX
乙方（借款方）：XXX

第一条 借款金额及利息
1.1 甲方向乙方提供借款人民币100万元整。

第二条 违约责任
2.1 乙方未按期还款的，应支付违约金。

第三条 争议解决
3.1 本协议争议向甲方所在地法院诉讼解决。
"""

    extractor = TemplateStructureExtractor()
    structure = extractor.extract_structure(sample_content)

    print("\n提取的结构:")
    print(json.dumps(structure, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="独立模板处理脚本")
    parser.add_argument("--mode", choices=["process", "test"], default="process",
                       help="运行模式: process=处理模板, test=测试提取器")
    parser.add_argument("--storage", help="自定义storage目录路径")

    args = parser.parse_args()

    if args.mode == "process":
        if args.storage:
            scanner = TemplateFileScanner()
            scanner.storage_paths = [args.storage]
            # ...处理逻辑
        else:
            process_standalone_templates()
    elif args.mode == "test":
        test_structure_extractor()
