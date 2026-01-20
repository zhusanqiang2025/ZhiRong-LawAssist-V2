import requests
import json
import os

BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查端点"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Health check: {response.status_code}")
        print(f"Response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_docs():
    """测试API文档端点"""
    try:
        response = requests.get(f"{BASE_URL}/docs")
        print(f"Docs check: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Docs check failed: {e}")
        return False

def test_register_user():
    """测试用户注册"""
    try:
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "testpass123"
        }
        response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data)
        print(f"User registration: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
        return response.status_code in [200, 400]  # 400表示用户已存在
    except Exception as e:
        print(f"User registration failed: {e}")
        return False

def test_login():
    """测试用户登录"""
    try:
        login_data = {
            "username": "testuser",
            "password": "testpass123"
        }
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/login",
            data=login_data
        )
        print(f"Login: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def test_upload_contract():
    """测试合同上传功能"""
    try:
        # 创建一个临时测试文件
        with open("test_contract.txt", "w") as f:
            f.write("This is a test contract file.")
        
        with open("test_contract.txt", "rb") as f:
            files = {"file": f}
            response = requests.post(f"{BASE_URL}/api/contract/upload", files=files)
        
        print(f"Contract upload: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        else:
            print(f"Error: {response.text}")
        
        # 清理临时文件
        os.remove("test_contract.txt")
        
        return response.status_code == 200
    except Exception as e:
        print(f"Contract upload failed: {e}")
        return False

def main():
    print("Starting API tests...")
    
    tests = [
        ("Health Check", test_health),
        ("Docs Check", test_docs),
        ("User Registration", test_register_user),
        ("User Login", test_login),
        ("Contract Upload", test_upload_contract)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\nRunning {test_name}...")
        success = test_func()
        results.append((test_name, success))
    
    print("\nTest Results:")
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")

if __name__ == "__main__":
    main()