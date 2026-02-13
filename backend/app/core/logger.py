"""
日志配置模块
"""
import logging
import sys


def setup_logging():
    """
    配置日志记录器，防止重复添加 handler
    """
    logger = logging.getLogger("legal_assistant")
    
    # 检查是否已有 handler，如果有则直接返回，避免重复添加
    if logger.hasHandlers():
        return logger

    # 设置基础日志级别
    logger.setLevel(logging.INFO)

    # 防止向上级 logger 传播，避免重复日志
    logger.propagate = False

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)

    # 添加处理器到 logger
    logger.addHandler(console_handler)

    return logger