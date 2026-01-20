# backend/app/utils/json_helper.py
import re
import json
import logging

logger = logging.getLogger(__name__)

def clean_json_output(text: str) -> str:
    """
    清洗 LLM 返回的 JSON 文本，处理常见的格式问题。
    功能：
    1. 移除 Markdown 代码块标记 (```json ... ```)
    2. 提取第一个完整的 JSON 对象或数组
    3. 移除末尾多余的逗号 (常见于 LLM 错误)
    
    Args:
        text: LLM 原始返回文本
    Returns:
        str: 清洗后的纯净 JSON 字符串
    Raises:
        ValueError: 如果无法提取出有效的 JSON 结构
    """
    if not text:
        raise ValueError("输入文本为空")

    # 1. 移除 Markdown 代码块标记
    # 匹配 ```json 或 ```python 等开头，以及 ``` 结尾
    text = re.sub(r'^```(json|python)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
    
    # 去除首尾空白
    text = text.strip()
    if not text:
        raise ValueError("去除代码块标记后文本为空")

    # 2. 移除 LLM 常见的对话前缀/后缀 (例如 "Here is the json: { ... }")
    # 这是一个简单的启发式：找到第一个 { 或 [，然后截断
    start_index = -1
    for i, char in enumerate(text):
        if char in ['{', '[']:
            start_index = i
            break
    
    if start_index == -1:
        raise ValueError("未找到 JSON 开始标记 { 或 [")
    
    text = text[start_index:]

    # 3. 提取完整的 JSON 对象或数组 (使用栈匹配括号)
    # 这样可以去除 JSON 后面 LLM 多写的废话
    stack = []
    is_in_string = False
    escape_char = False
    end_index = -1
    
    # 确定结束标记
    start_char = text[0]
    end_char = '}' if start_char == '{' else ']'

    for i, char in enumerate(text):
        if escape_char:
            escape_char = False
            continue
        
        if char == '\\':
            escape_char = True
            continue
        
        if char == '"' and not escape_char:
            is_in_string = not is_in_string
            continue
        
        if not is_in_string:
            if char == start_char:
                stack.append(char)
            elif char == end_char:
                if stack:
                    stack.pop()
                    if not stack:
                        end_index = i + 1
                        break
    
    if end_index > 0:
        text = text[:end_index]

    # 4. 移除末尾逗号 (例如 {"a":1,} -> {"a":1})
    # 只能在对象或数组内部移除，不能在字符串内部移除
    # 简单策略：从后往前找非空白字符，如果是逗号，且前一个字符是 } 或 ]，则删除
    temp_text = text.rstrip()
    if len(temp_text) > 0 and temp_text[-1] == ',':
        # 简单检查前一个非空白字符是否是闭合符号
        prev_content = temp_text[:-1].rstrip()
        if len(prev_content) > 0 and prev_content[-1] in ['}', ']']:
            text = prev_content

    return text

def safe_parse_json(text: str) -> dict:
    """
    安全的 JSON 解析，包含自动清洗逻辑
    
    Args:
        text: LLM 原始返回文本
    Returns:
        dict: 解析后的字典
    Raises:
        json.JSONDecodeError: 解析失败
    """
    try:
        cleaned = clean_json_output(text)
        return json.loads(cleaned)
    except ValueError as e:
        logger.error(f"JSON 清洗失败: {e}, 原始内容: {text[:200]}...")
        raise json.JSONDecodeError(f"清洗失败: {e}", text, 0)
    except json.JSONDecodeError as e:
        # 即使清洗后也可能解析失败，抛出原始错误
        logger.error(f"JSON 解析失败: {e}, 清洗后内容: {text[:200]}...")
        raise