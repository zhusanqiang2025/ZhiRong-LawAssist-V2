import json
import requests

# 测试费用测算API
def test_cost_calculation_api():
    url = "http://localhost:8000/api/cost-calculation"
    
    # 测试数据
    payload = {
        "case_type": "合同纠纷",
        "case_description": "买卖合同纠纷，对方未按时交付货物",
        "case_amount": 100000
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            result = response.json()
            print("✅ 费用测算API测试成功!")
            print(f"总费用: {result['total_cost']}元")
            print(f"费用明细数量: {len(result['cost_breakdown'])}")
            for item in result['cost_breakdown']:
                print(f"  - {item['name']}: {item['amount']}元")
        else:
            print(f"❌ API请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"❌ API测试出错: {str(e)}")
        print("请确保后端服务正在运行 (uvicorn app:app --reload --port 8000)")

if __name__ == "__main__":
    test_cost_calculation_api()