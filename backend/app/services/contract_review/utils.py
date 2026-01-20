# backend/app/services/contract_review/utils.py
"""
文本分块工具

用于对长合同文本进行智能分块处理
"""

import logging
import re
from typing import List, Tuple, Dict, Union

logger = logging.getLogger(__name__)


# ================= Parties 数据解析工具 =================

def parse_parties_from_metadata(
    metadata: Dict,
    return_format: str = "names"
) -> Union[List[str], List[Dict], str]:
    """
    ⭐ 统一工具函数：从元数据中解析当事人信息

    支持多种输入格式：
    - 字符串: "甲方：雇主; 乙方：贵州省秦佳琪家政服务有限公司"
    - 列表: [{"role": "甲方", "name": "雇主"}, {"role": "乙方", "name": "XX公司"}]
    - 列表(字符串): ["雇主", "XX公司"]

    Args:
        metadata: 合同元数据字典
        return_format: 返回格式
            - "names": 返回当事人名称列表 ["雇主", "XX公司"]
            - "dicts": 返回当事人字典列表 [{"role": "甲方", "name": "雇主", "type": "individual"}, ...]
            - "string": 返回原始字符串格式

    Returns:
        根据return_format返回相应的数据结构
    """
    if not metadata:
        return [] if return_format != "string" else ""

    parties = metadata.get("parties", [])

    # 空值处理
    if not parties:
        return [] if return_format != "string" else ""

    # ========== 格式1: 字符串解析 ==========
    if isinstance(parties, str):
        if return_format == "string":
            return parties

        # 解析字符串: "甲方：雇主; 乙方：XX公司" 或 "甲方: 雇主; 乙方: XX公司"
        party_parts = parties.replace("；", ";").split(";")

        parsed_dicts = []
        for party in party_parts:
            party = party.strip()
            if not party:
                continue

            # 解析 "甲方：雇主" 格式
            role = ""
            name = party

            if "：" in party:
                role, name = party.split("：", 1)
            elif ":" in party:
                role, name = party.split(":", 1)

            role = role.strip()
            name = name.strip()

            if not name:
                continue

            # 判断主体类型
            etype = _detect_entity_type(name)

            parsed_dicts.append({
                "role": role or "未知",
                "name": name,
                "type": etype
            })

        if return_format == "dicts":
            return parsed_dicts
        elif return_format == "names":
            return [p["name"] for p in parsed_dicts]

    # ========== 格式2: 列表解析 ==========
    elif isinstance(parties, list):
        if return_format == "string":
            # 转换为字符串格式
            return "; ".join([
                f"{p.get('role', '未知')}：{p.get('name', '未命名')}"
                if isinstance(p, dict) else str(p)
                for p in parties
            ])

        # 检查列表元素类型
        if all(isinstance(p, dict) for p in parties):
            # 列表是字典格式
            if return_format == "dicts":
                return parties
            elif return_format == "names":
                return [p.get("name", "") for p in parties if p.get("name")]
        else:
            # 列表是字符串格式
            if return_format == "names":
                return [str(p) for p in parties if p]
            elif return_format == "dicts":
                # 转换为字典格式
                return [{
                    "role": "未知",
                    "name": str(p),
                    "type": _detect_entity_type(str(p))
                } for p in parties if p]

    # 默认返回空列表
    return [] if return_format != "string" else ""


def _detect_entity_type(name: str) -> str:
    """
    检测主体类型

    Args:
        name: 主体名称

    Returns:
        "company" | "individual" | "unknown"
    """
    if not name:
        return "unknown"

    # 公司关键词
    company_keywords = [
        "公司", "有限", "集团", "企业", "厂", "店",
        "银行", "保险", "证券", "基金", "投资",
        "科技", "网络", "信息", "咨询", "服务"
    ]

    if any(keyword in name for keyword in company_keywords):
        return "company"

    return "individual"


def extract_party_names(metadata: Dict) -> List[str]:
    """
    便捷函数：提取当事人名称列表

    Args:
        metadata: 合同元数据

    Returns:
        当事人名称列表
    """
    return parse_parties_from_metadata(metadata, return_format="names")


def format_parties_string(parties: Union[str, List]) -> str:
    """
    便捷函数：格式化当事人为字符串

    Args:
        parties: 当事人数据 (字符串或列表)

    Returns:
        格式化后的字符串
    """
    if isinstance(parties, str):
        return parties

    if isinstance(parties, list):
        return "; ".join([
            f"{p.get('role', '未知')}：{p.get('name', '未命名')}"
            if isinstance(p, dict) else str(p)
            for p in parties
        ])

    return str(parties)


# ================= 文本分块工具 =================

def chunk_contract_text(
    text: str,
    max_chunk_size: int = 4000,
    overlap: int = 200,
    split_by_section: bool = True
) -> List[Tuple[str, Tuple[int, int]]]:
    """
    对合同文本进行分块处理

    Args:
        text: 合同全文
        max_chunk_size: 每块最大字符数 (默认4000)
        overlap: 块之间的重叠字符数 (默认200)
        split_by_section: 是否按条款分割 (优先级高于固定大小)

    Returns:
        [(chunk_text, (start_pos, end_pos)), ...]  # 分块文本及其在原文的位置
    """
    if not text:
        return []

    text_length = len(text)

    # 如果文本小于最大块大小,直接返回
    if text_length <= max_chunk_size:
        return [(text, (0, text_length))]

    logger.info(f"开始分块处理 - 文本长度: {text_length}, 最大块大小: {max_chunk_size}")

    chunks = []

    # 策略1: 按条款分割 (优先)
    if split_by_section:
        chunks = _split_by_sections(text, max_chunk_size, overlap)
        logger.info(f"按条款分割完成 - 分块数量: {len(chunks)}")

    # 策略2: 按固定大小分割 (备用)
    if not chunks:
        chunks = _split_by_size(text, max_chunk_size, overlap)
        logger.info(f"按固定大小分割完成 - 分块数量: {len(chunks)}")

    return chunks


def _split_by_sections(text: str, max_size: int, overlap: int) -> List[Tuple[str, Tuple[int, int]]]:
    """
    按条款分割合同文本

    条款识别规则:
    - 第X条 / 第x条
    - X. / x.
    - Article X / Section X

    Args:
        text: 合同文本
        max_size: 每块最大字符数
        overlap: 块之间重叠字符数

    Returns:
        [(chunk_text, (start_pos, end_pos)), ...]
    """
    # 识别条款标题的正则表达式
    section_pattern = r'(第[一二三四五六七八九十百千\d]+条|Art\.\s*\d+|Section\s*\d+|\d+\.)'

    # 查找所有条款位置
    matches = list(re.finditer(section_pattern, text))

    if len(matches) < 2:  # 条款太少,改用固定大小分割
        logger.info("条款数量不足2个,改用固定大小分割")
        return []

    chunks = []
    current_start = 0
    current_text = ""

    for i, match in enumerate(matches):
        section_pos = match.start()

        # 如果当前块已超过最大大小,保存并开始新块
        if len(current_text) > 0 and section_pos - current_start > max_size:
            # 保存当前块
            chunks.append((current_text, (current_start, section_pos)))
            logger.debug(f"保存分块 #{len(chunks)}: 位置 {current_start}-{section_pos}, 长度 {len(current_text)}")

            # 开始新块 (保留overlap)
            current_start = section_pos - overlap if overlap > 0 else section_pos
            current_text = text[current_start:section_pos]
        else:
            # 累积文本
            current_text = text[current_start:section_pos]

    # 添加最后一块
    if current_text:
        end_pos = len(text)
        chunks.append((current_text, (current_start, end_pos)))
        logger.debug(f"保存最后分块: 位置 {current_start}-{end_pos}, 长度 {len(current_text)}")

    return chunks


def _split_by_size(text: str, max_size: int, overlap: int) -> List[Tuple[str, Tuple[int, int]]]:
    """
    按固定大小分割合同文本

    Args:
        text: 合同文本
        max_size: 每块最大字符数
        overlap: 块之间重叠字符数

    Returns:
        [(chunk_text, (start_pos, end_pos)), ...]
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + max_size, text_length)

        # 尝试在句子边界分割
        if end < text_length:
            # 查找最近的句号
            last_period = text.rfind('。', start, end)
            if last_period > start + max_size // 2:
                end = last_period + 1  # 包含句号
            else:
                # 如果没有合适的句号,查找逗号
                last_comma = text.rfind('，', start, end)
                if last_comma > start + max_size // 2:
                    end = last_comma + 1  # 包含逗号

        chunk_text = text[start:end]
        chunks.append((chunk_text, (start, end)))
        logger.debug(f"固定大小分块: 位置 {start}-{end}, 长度 {len(chunk_text)}")

        # 移动起始位置 (保留overlap)
        start = end - overlap if overlap > 0 else end

    return chunks


def extract_section_keywords(chunk_text: str) -> str:
    """
    从文本块中提取关键词

    用于生成分块描述,帮助理解每块的内容

    Args:
        chunk_text: 文本块内容

    Returns:
        关键词描述 (例如: "第1条-第5条, 关于合同标的")
    """
    # 提取条款编号
    section_matches = re.findall(r'第[一二三四五六七八九十百千\d]+条', chunk_text)

    keywords = []

    if section_matches:
        # 取第一个和最后一个条款编号
        first_section = section_matches[0]
        last_section = section_matches[-1] if len(section_matches) > 1 else first_section
        keywords.append(f"{first_section}-{last_section}")

    # 提取常见关键词
    common_keywords = [
        "当事人", "标的", "价款", "履行", "违约",
        "保密", "知识产权", "争议解决", "管辖", "生效"
    ]

    for keyword in common_keywords:
        if keyword in chunk_text:
            keywords.append(keyword)
            if len(keywords) >= 5:  # 最多返回5个关键词
                break

    return ", ".join(keywords) if keywords else "未知内容"


def validate_chunks(chunks: List[Tuple[str, Tuple[int, int]]], original_length: int) -> bool:
    """
    验证分块结果的完整性

    检查:
    1. 分块数量合理
    2. 分块之间没有大的空隙
    3. 分块总长度接近原文长度

    Args:
        chunks: 分块列表
        original_length: 原始文本长度

    Returns:
        是否验证通过
    """
    if not chunks:
        logger.error("分块验证失败: 分块列表为空")
        return False

    # 检查分块数量
    if len(chunks) > 100:
        logger.warning(f"分块数量过多: {len(chunks)}, 可能存在分块错误")

    # 检查分块连续性
    total_gap = 0
    for i in range(len(chunks) - 1):
        current_end = chunks[i][1][1]
        next_start = chunks[i + 1][1][0]
        gap = next_start - current_end

        if gap < 0:
            logger.error(f"分块验证失败: 分块{i}和{i+1}存在重叠 (gap={gap})")
            return False

        total_gap += gap

    # 检查总长度
    total_chunk_length = sum(len(chunk[0]) for chunk in chunks)
    coverage = total_chunk_length / original_length if original_length > 0 else 0

    if coverage < 0.8:
        logger.warning(f"分块覆盖率过低: {coverage:.2%}, 原文长度: {original_length}, 分块总长度: {total_chunk_length}")
    elif coverage > 1.5:
        logger.warning(f"分块覆盖率高: {coverage:.2%}, 可能存在过多重叠")

    logger.info(f"分块验证通过 - 分块数: {len(chunks)}, 覆盖率: {coverage:.2%}, 总间隙: {total_gap}")
    return True
