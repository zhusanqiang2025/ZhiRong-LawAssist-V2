"""
测试 AI 模型调用

验证 qwen3-vl:32b-thinking-q8_0 模型是否能正常访问
"""
import os
import httpx

# 配置
API_URL = "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1/chat/completions"
API_KEY = "7adb34bf-3cb3-4dea-af41-b79de8c08ca3"
MODEL_NAME = "qwen3-vl:32b-thinking-q8_0"

# 测试不同的认证方式
AUTH_TYPES = [
    ("Bearer", "Authorization"),
    ("x-api-key", "x-api-key"),
    ("Direct", "Authorization"),  # 直接使用 API Key 作为 Authorization 值
]

print(f"测试模型: {MODEL_NAME}")
print(f"API 地址: {API_URL}")
print(f"API Key: {API_KEY[:20]}...")
print("=" * 60)

for auth_type, header_name in AUTH_TYPES:
    print(f"\n测试认证方式: {auth_type}")
    print("-" * 40)

    try:
        headers = {
            "Content-Type": "application/json"
        }

        if auth_type == "Bearer":
            headers["Authorization"] = f"Bearer {API_KEY}"
        elif auth_type == "x-api-key":
            headers["x-api-key"] = API_KEY
        elif auth_type == "Direct":
            headers["Authorization"] = API_KEY

        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个助手。"
                },
                {
                    "role": "user",
                    "content": "请简单回复：测试成功"
                }
            ],
            "temperature": 0.1,
            "max_tokens": 50
        }

        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                API_URL,
                headers=headers,
                json=payload
            )

            print(f"状态码: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"✅ 成功! 响应: {content[:100]}")
                print(f"\n*** 推荐使用此认证方式: {auth_type} ***")
                break  # 找到成功的就停止
            else:
                print(f"❌ 失败")
                print(f"响应内容: {response.text[:200]}")

    except Exception as e:
        print(f"❌ 异常: {str(e)}")

print("\n" + "=" * 60)
print("测试完成")
