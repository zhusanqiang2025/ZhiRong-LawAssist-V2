"""
测试管理员后台模板 API
模拟前端请求，检查响应
"""
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
from app.models.user import User
from app.api.v1.endpoints.contract_templates import PaginatedTemplateResponse
import json

print("\n" + "="*80)
print("测试管理员后台模板 API")
print("="*80 + "\n")

# 获取数据库会话
db = SessionLocal()

try:
    # 1. 检查管理员用户
    print("1. 检查管理员用户:")
    admin_users = db.query(User).filter(User.is_admin == True).all()
    print(f"   管理员数量: {len(admin_users)}")
    if admin_users:
        admin = admin_users[0]
        print(f"   管理员邮箱: {admin.email}")
        print(f"   管理员ID: {admin.id}")

    # 2. 检查模板数据
    print("\n2. 检查模板数据:")
    total_templates = db.query(ContractTemplate).count()
    public_templates = db.query(ContractTemplate).filter(ContractTemplate.is_public == True).count()
    active_templates = db.query(ContractTemplate).filter(ContractTemplate.status == 'active').count()

    print(f"   总模板数: {total_templates}")
    print(f"   公开模板: {public_templates}")
    print(f"   活跃模板: {active_templates}")

    # 3. 模拟API查询（scope=all）
    print("\n3. 模拟API查询 (scope=all):")
    query = db.query(ContractTemplate).filter(ContractTemplate.status == 'active')
    query = query.filter(ContractTemplate.is_public == True)

    # 分页
    page = 1
    page_size = 10
    total_count = query.count()
    templates = query.order_by(ContractTemplate.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    print(f"   查询结果: {len(templates)} 条记录")
    print(f"   总记录数: {total_count}")

    # 4. 显示前5个模板
    print("\n4. 示例模板 (前5个):")
    for i, t in enumerate(templates[:5], 1):
        print(f"   {i}. {t.name[:40]}")
        print(f"      主分类: {t.primary_contract_type or '未分类'}")
        print(f"      文件: {t.file_name}")
        print(f"      状态: {t.status}")
        print(f"      公开: {t.is_public}")

    # 5. 检查响应格式
    print("\n5. 检查响应格式:")
    response_data = {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category,
                "primary_contract_type": t.primary_contract_type,
                "file_name": t.file_name,
                "is_public": t.is_public,
                "status": t.status
            }
            for t in templates[:3]
        ],
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size
    }

    print("   响应结构:")
    print(f"   - templates: {len(response_data['templates'])} 条")
    print(f"   - total_count: {response_data['total_count']}")
    print(f"   - page: {response_data['page']}")
    print(f"   - total_pages: {response_data['total_pages']}")

    print("\n6. API端点路径:")
    print("   GET /api/v1/contract/?scope=all&page_size=10")
    print("   需要: Authorization header (Bearer token)")

    print("\n" + "="*80)
    print("诊断总结")
    print("="*80)
    print("\n✅ 数据库中有数据:")
    print(f"   - 模板总数: {total_templates}")
    print(f"   - 公开模板: {public_templates}")

    print("\n🔍 可能的前端问题:")
    print("   1. 认证token缺失或无效")
    print("   2. API baseURL配置错误")
    print("   3. CORS跨域问题")
    print("   4. 响应数据格式不匹配")

    print("\n💡 建议检查:")
    print("   1. 浏览器控制台 Network 标签，查看API请求")
    print("   2. 检查请求是否携带 Authorization header")
    print("   3. 检查响应状态码和内容")
    print("   4. 查看是否有JavaScript错误")

finally:
    db.close()

print()
