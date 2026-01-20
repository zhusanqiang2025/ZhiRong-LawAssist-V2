"""
JSON 输出处理模块

解决 LLM JSON 输出不稳定的问题：
1. 多策略解析：JSON模式 -> 文本解析 -> 修复器
2. 自动修复常见 JSON 格式错误
3. 重试机制
"""

import json
import logging
import re
from typing import Any, Dict, Optional, TypeVar, Generic
from pydantic import BaseModel
from langchain_core.runnables import Runnable

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


class JSONOutputParser:
    """
    智能JSON输出解析器

    支持多种解析策略，自动处理LLM输出不稳定问题
    """

    def __init__(
        self,
        pydantic_model: type[T],
        enable_json_mode: bool = True,
        max_retries: int = 2
    ):
        """
        Args:
            pydantic_model: 目标Pydantic模型
            enable_json_mode: 是否启用JSON模式（如果模型支持）
            max_retries: 最大重试次数
        """
        self.pydantic_model = pydantic_model
        self.enable_json_mode = enable_json_mode
        self.max_retries = max_retries

    def parse(
        self,
        llm_output: str,
        fallback_to_text: bool = True
    ) -> Optional[T]:
        """
        解析LLM输出

        Args:
            llm_output: LLM原始输出
            fallback_to_text: 是否在JSON解析失败时回退到文本提取

        Returns:
            解析后的Pydantic对象，失败返回None
        """
        # 策略1: 直接JSON解析
        result = self._try_direct_json(llm_output)
        if result:
            return result

        # 策略2: 提取JSON块（去除markdown标记等）
        result = self._try_extract_json(llm_output)
        if result:
            return result

        # 策略3: 修复常见JSON错误后解析
        result = self._try_repair_json(llm_output)
        if result:
            return result

        # 策略4: 文本提取（如果启用）
        if fallback_to_text:
            result = self._try_text_extraction(llm_output)
            if result:
                return result

        logger.error(f"[JSONParser] 所有解析策略均失败")
        return None

    def _try_direct_json(self, output: str) -> Optional[T]:
        """策略1: 直接JSON解析"""
        try:
            data = json.loads(output.strip())
            return self.pydantic_model(**data)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.debug(f"[JSONParser] 直接JSON解析失败: {e}")
            return None

    def _try_extract_json(self, output: str) -> Optional[T]:
        """策略2: 提取JSON块"""
        try:
            # 移除markdown代码块标记
            output = output.strip()

            # 提取 ```json ... ``` 中的内容
            json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
            matches = re.findall(json_pattern, output, re.DOTALL)

            if matches:
                json_str = matches[0].strip()
            else:
                # 尝试找到第一个完整的JSON对象
                # 查找 { ... } 配对
                brace_count = 0
                start_idx = -1
                for i, char in enumerate(output):
                    if char == '{':
                        if brace_count == 0:
                            start_idx = i
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0 and start_idx >= 0:
                            json_str = output[start_idx:i+1]
                            break
                else:
                    return None

            data = json.loads(json_str)
            return self.pydantic_model(**data)

        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.debug(f"[JSONParser] JSON块提取失败: {e}")
            return None

    def _try_repair_json(self, output: str) -> Optional[T]:
        """策略3: 修复常见JSON错误"""
        try:
            # 提取JSON部分
            json_str = self._extract_json_string(output)
            if not json_str:
                return None

            # 常见修复规则
            repaired = self._apply_common_fixes(json_str)

            data = json.loads(repaired)
            return self.pydantic_model(**data)

        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.debug(f"[JSONParser] JSON修复失败: {e}")
            return None

    def _try_text_extraction(self, output: str) -> Optional[T]:
        """策略4: 基于规则的文本提取（备用方案）"""
        try:
            # 这是一个简化的备用方案
            # 对于复杂的schema，可能需要更智能的提取逻辑

            # 尝试提取关键字段
            extracted = {}

            # 根据模型定义提取字段
            if hasattr(self.pydantic_model, 'model_fields'):
                for field_name in self.pydantic_model.model_fields.keys():
                    # 查找类似 "field_name": value 或 field_name: value 的模式
                    patterns = [
                        rf'"{field_name}"\s*:\s*"([^"]*)"',
                        rf'"{field_name}"\s*:\s*(\d+)',
                        rf'"{field_name}"\s*:\s*(true|false)',
                        rf'{field_name}\s*:\s*"([^"]*)"',
                    ]

                    for pattern in patterns:
                        match = re.search(pattern, output)
                        if match:
                            value = match.group(1)
                            # 尝试转换类型
                            if value.isdigit():
                                extracted[field_name] = int(value)
                            elif value.lower() in ['true', 'false']:
                                extracted[field_name] = value.lower() == 'true'
                            else:
                                extracted[field_name] = value
                            break

            if extracted:
                return self.pydantic_model(**extracted)

            return None

        except (TypeError, ValueError) as e:
            logger.debug(f"[JSONParser] 文本提取失败: {e}")
            return None

    def _extract_json_string(self, output: str) -> Optional[str]:
        """从输出中提取JSON字符串"""
        # 移除markdown标记
        output = re.sub(r'```(?:json)?\s*\n?', '', output)

        # 查找JSON对象
        for pattern in [r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', r'\{.*\}']:
            match = re.search(pattern, output, re.DOTALL)
            if match:
                return match.group(0)

        return None

    def _apply_common_fixes(self, json_str: str) -> str:
        """应用常见的JSON修复规则"""
        repaired = json_str

        # 1. 修复未引用的键名
        # key: value -> "key": value
        repaired = re.sub(r'(\w+)\s*:', r'"\1":', repaired)

        # 2. 修复尾随逗号
        # , } -> }
        repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

        # 3. 修复单引号字符串
        # 'value' -> "value"
        repaired = re.sub(r"'([^']*)'", r'"\1"', repaired)

        # 4. 修复未引用的布尔值
        # true/false -> "true"/"false" (如果需要)
        # repaired = re.sub(r':\s*(true|false)', r': "\1"', repaired)

        # 5. 移除注释
        # // comment
        repaired = re.sub(r'//.*?\n', '', repaired)
        # /* comment */
        repaired = re.sub(r'/\*.*?\*/', '', repaired, flags=re.DOTALL)

        return repaired


def safe_parse_json(
    llm_output: str,
    pydantic_model: type[T],
    fallback: bool = True
) -> Optional[T]:
    """
    便捷函数：安全解析JSON输出

    Args:
        llm_output: LLM原始输出
        pydantic_model: 目标Pydantic模型
        fallback: 是否启用备用解析策略

    Returns:
        解析后的对象，失败返回None
    """
    parser = JSONOutputParser(pydantic_model)
    return parser.parse(llm_output, fallback_to_text=fallback)


# ==================== LangChain 集成 ====================


class RobustPydanticOutputParser(Runnable):
    """
    鲁棒的Pydantic输出解析器

    集成到LangChain，自动处理各种输出格式问题
    继承自 Runnable 以支持链式调用
    """

    def __init__(self, pydantic_object: type[T]):
        self.pydantic_object = pydantic_object
        self._parser = JSONOutputParser(pydantic_object)
        # 同时使用标准解析器作为对比
        from langchain_core.output_parsers import PydanticOutputParser as OriginalParser
        self._original_parser = OriginalParser(pydantic_object=pydantic_object)

    def invoke(self, input: Any, config: Optional[Dict] = None) -> T:
        """
        Runnable 接口实现：解析输入

        Args:
            input: LLM 输出（可能是 str 或 AIMessage 对象）
            config: 可选的配置

        Returns:
            解析后的 Pydantic 对象
        """
        # 处理 AIMessage 对象
        if hasattr(input, 'content'):
            # LangChain AIMessage 对象
            text = input.content
        elif isinstance(input, str):
            text = input
        else:
            # 尝试转换为字符串
            text = str(input)

        return self.parse(text)

    def parse(self, text: str) -> T:
        """解析文本"""
        # 确保 text 是字符串类型
        if not isinstance(text, str):
            if hasattr(text, 'content'):
                text = text.content
            else:
                text = str(text)

        result = self._parser.parse(text, fallback_to_text=True)

        if result is None:
            # 尝试使用原始解析器
            try:
                result = self._original_parser.parse(text)
                logger.info(f"[RobustParser] 使用原始解析器成功")
            except Exception as e:
                logger.error(f"[RobustParser] 原始解析器也失败: {e}")
                # 返回一个默认值或抛出异常
                logger.error(f"[RobustParser] 解析失败，返回空对象")
                # 尝试创建一个空对象
                try:
                    return self.pydantic_object()
                except TypeError:
                    # 如果需要必需参数，返回一个包含默认值的对象
                    return self._create_default_object()

        return result

    def _create_default_object(self) -> T:
        """创建默认对象"""
        # 根据字段创建默认值
        default_values = {}

        if hasattr(self.pydantic_object, 'model_fields'):
            for field_name, field_info in self.pydantic_object.model_fields.items():
                if field_info.default is not None:
                    default_values[field_name] = field_info.default
                elif not field_info.is_required():
                    default_values[field_name] = None
                elif field_info.default_factory is not None:
                    default_values[field_name] = field_info.default_factory()
                else:
                    # 必需字段，使用空值
                    if str(field_info.annotation) == 'str':
                        default_values[field_name] = ""
                    elif 'int' in str(field_info.annotation):
                        default_values[field_name] = 0
                    elif 'bool' in str(field_info.annotation):
                        default_values[field_name] = False
                    elif 'list' in str(field_info.annotation):
                        default_values[field_name] = []

        return self.pydantic_object(**default_values)

    def get_format_instructions(self) -> str:
        """获取格式说明"""
        # 使用原始PydanticOutputParser的格式说明
        return self._original_parser.get_format_instructions()


def create_robust_parser(pydantic_model: type[T]) -> RobustPydanticOutputParser:
    """
    创建鲁棒的解析器

    Args:
        pydantic_model: Pydantic模型类

    Returns:
        鲁棒解析器实例
    """
    return RobustPydanticOutputParser(pydantic_model)
