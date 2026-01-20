"""
获取 categories.json 中的所有二级分类（用于 primary_contract_type）
"""
import json

with open('backend/categories.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('二级分类列表（用于 primary_contract_type 字段）:')
print('='*60)

secondary_types = []
for primary_cat in data.get('primary_categories', []):
    for sub_type in primary_cat.get('sub_types', []):
        name = sub_type.get('name')
        secondary_types.append(name)
        print(f'  - {name}')

print()
print(f'总计: {len(secondary_types)} 个二级分类')

print('\n\n用于代码的常量定义:')
print('const SECONDARY_CONTRACT_TYPES = [')
for st in secondary_types:
    print(f"  '{st}',")
print('];')
