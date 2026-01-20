import jwt
import time
import os

class OfficeTokenManager:
    @staticmethod
    def create_token(config_payload):
        """
        为 ONLYOFFICE 配置生成签名 Token
        """
        # 从环境变量读取密钥，默认值作为防呆措施
        secret = os.getenv("ONLYOFFICE_JWT_SECRET", "legal_doc_secret_2025")
        
        # 复制配置字典，避免修改原对象
        payload = config_payload.copy()
        
        # 添加标准 JWT 声明
        # iat: 签发时间
        # exp: 过期时间 (设置为 5 分钟后过期，防止 Token 被恶意截获后长期使用)
        payload['iat'] = int(time.time())
        payload['exp'] = int(time.time()) + 300 
        
        # 使用 HS256 算法进行签名
        token = jwt.encode(payload, secret, algorithm="HS256")
        return token