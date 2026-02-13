# backend/app/services/embedding_service.py
import httpx
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# 配置你的 AI 模型服务器地址
# 根据你的架构图，这里指向 BGE 模型服务
# 假设是 Ollama 格式，如果端口不同请修改
EMBEDDING_API_URL = "http://115.190.43.141:11434/api/embeddings"
MODEL_NAME = "bge-m3"  # 确保这个名字和你服务器上跑的模型一致

async def get_text_embedding(text: str) -> Optional[List[float]]:
    """
    调用远程 AI 服务，将文本转换为向量
    """
    if not text or len(text.strip()) == 0:
        return None

    try:
        # 设置超时时间为 30 秒，防止模型处理慢导致报错
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                EMBEDDING_API_URL,
                json={
                    "model": MODEL_NAME,
                    "prompt": text
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                # 适配 Ollama 返回格式
                embedding = data.get("embedding") 
                
                # 兜底：如果是其他格式
                if not embedding and "data" in data:
                     embedding = data["data"][0]["embedding"]

                if embedding:
                    return embedding
                else:
                    logger.warning(f"API返回数据中未找到向量: {data}")
                    return None
            else:
                logger.error(f"向量服务请求失败: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"获取向量失败 (网络/服务错误): {str(e)}")
        return None