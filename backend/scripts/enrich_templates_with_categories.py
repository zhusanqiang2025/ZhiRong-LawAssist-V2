"""
模板智能分类与结构化参数提取脚本 (Legal Transaction Logic V2)

升级核心：
1. 弃用工程化参数 (delivery_model/payment_model)，改用法律交易参数。
2. 引入四维特征：Transaction Nature, Contract Object, Complexity, Stance。
3. 强化 DeepSeek 对非典型合同的理解力。

使用方法：
    python scripts/enrich_templates_v2.py
"""
import os
import sys
import json
import time
import re
from typing import Dict, Any, Optional
from pathlib import Path

# 添加 backend 目录到 Python 路径
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

# ==================== 配置区 ====================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/legal_v3_db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-key")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.deepseek.com/v1")

# 分类表路径（在 Docker 容器中是 /app/categories.json）
TAXONOMY_PATH = BACKEND_DIR / "categories.json"

# ==================== 初始化 ====================

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def get_llm():
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_API_BASE,
        temperature=0.0, # 必须为0，确保分类结果的确定性
        timeout=60
    )

def get_db_session():
    """获取数据库会话"""
    return SessionLocal()

def load_taxonomy() -> str:
    # 尝试多个可能的路径
    possible_paths = [
        BACKEND_DIR / "categories.json",           # /app/categories.json (Docker)
        BACKEND_DIR / "config" / "categories.json", # /app/config/categories.json
        BACKEND_DIR.parent / "categories.json",    # 项目根目录
    ]

    for path in possible_paths:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    # 如果所有路径都失败，列出所有尝试的路径
    paths_str = "\n  ".join(str(p) for p in possible_paths)
    raise FileNotFoundError(f"❌ 分类体系文件不存在，已尝试以下路径：\n  {paths_str}")

# ==================== 核心逻辑：AI 分析 (V2 Prompt) ====================

def analyze_template_with_ai(llm, content: str, taxonomy_str: str, filename: str) -> Optional[Dict[str, Any]]:
    """
    让 AI 从【法律交易逻辑】的角度分析合同
    """
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名资深法务数据治理专家。请分析合同内容，完成两大任务：
1. **标准化归类**：将其映射到给定的标准分类体系中。
2. **法律特征提取**：基于【法律交易逻辑】提取结构化参数（非工程参数）。

## 任务一：标准分类 (Strict Mapping)
参考以下分类表 JSON，选出最匹配的路径：
{taxonomy}

*要求：必须输出 id, name, sub_type_name, sub_category_name。*

## 任务二：法律特征提取 (Legal Logic Extraction)

请根据合同实质，提取以下 4 个维度的参数：

### 1. Transaction Nature (交易实质)
*判断合同背后的法律关系性质*
- **asset_transfer**: 资产/权益的所有权转移（如买卖、股权转让、赠与）
- **service_delivery**: 提供劳务、技术或服务（如开发、咨询、物业、运输）
- **resource_sharing**: 资源互换、渠道合作、联营（无新主体设立）
- **entity_creation**: 共同出资设立新公司或合伙企业（如合伙协议、章程）
- **capital_finance**: 资金的借贷、担保、融资、债权处理
- **dispute_resolution**: 解决纠纷（如和解协议、调解书）
- **authorization**: 单方授权或承诺（如授权书、承诺函）

### 2. Contract Object (核心标的)
*交易的对象是什么？*
- **tangible_goods**: 实物商品、设备、房产、车辆
- **equity**: 股权、股份、出资额
- **ip**: 知识产权（商标、专利、著作权、专有技术）
- **human_labor**: 人的劳动、智力成果、演艺行为
- **monetary_debt**: 纯金钱债权/债务
- **data_traffic**: 数据、流量、用户资源、广告位
- **credibility**: 信用、资质、经营权

### 3. Complexity (交易复杂度)
- **internal_simple**: 关联方交易、内部划转、简易模版、单方文件
- **standard_commercial**: 标准的市场化商业交易（一般买卖/租赁）
- **complex_strategic**: 涉及对赌、分期行权、并购重组、跨境等复杂安排

### 4. Stance (合同立场)
- **buyer_friendly**: 偏向买方/受让方/甲方（重赔偿、严验收、付款慢）
- **seller_friendly**: 偏向卖方/转让方/乙方（重免责、快回款、轻交付）
- **neutral**: 权利义务对等（标准示范文本）

## 输出格式
请直接输出纯 JSON，不要包含 Markdown 标记：
{{
    "classification": {{
        "primary_id": "2",
        "primary_name": "非典型商事合同",
        "sub_type": "股权与投资",
        "sub_category": "股权转让协议"
    }},
    "features": {{
        "transaction_nature": "asset_transfer",
        "contract_object": "equity",
        "complexity": "internal_simple",
        "stance": "neutral"
    }}
}}
"""),
        ("user", """文件名：{filename}
合同内容摘要（前3000字）：
{content}""")
    ])

    try:
        chain = prompt | llm
        response = chain.invoke({
            "taxonomy": taxonomy_str,
            "content": content[:3000],
            "filename": filename
        })
        
        # 清洗 JSON
        json_str = re.sub(r'```json\s*|```', '', response.content).strip()
        return json.loads(json_str)
        
    except Exception as e:
        print(f"  ⚠️ AI 分析异常: {e}")
        return None

# ==================== 数据库更新 (V2 Schema) ====================

def update_db(session, tmpl_id: str, data: Dict[str, Any]) -> bool:
    """
    将提取的新维度数据写入数据库
    注意：你需要确保数据库表里有这些新字段！
    """
    try:
        cls = data["classification"]
        feat = data["features"]

        # 兼容不同的字段名（AI 可能返回 sub_type 或 sub_type_name）
        sub_type = cls.get("sub_type") or cls.get("sub_type_name", "")
        sub_category = cls.get("sub_category") or cls.get("sub_category_name", "")

        # 构造增强版关键词
        keywords = [
            cls["primary_name"],
            sub_type,
            sub_category,
            feat["transaction_nature"], # 把 'asset_transfer' 也作为关键词索引
            feat["contract_object"]
        ]
        
        # SQL 更新语句
        # 注意：这里我们把新的4维特征存入对应的字段
        # 如果你的数据库表还没加字段，建议先存入 metadata_info (JSON) 字段作为过渡
        sql = text("""
            UPDATE contract_templates
            SET 
                category = :cat,
                subcategory = :sub_cat,
                
                -- 核心 4 维特征 (存入新字段)
                transaction_nature = :nature,
                contract_object = :obj,
                complexity = :comp,
                stance = :stance,
                
                -- 更新关键词索引
                keywords = :kw,
                
                -- 同时也存一份完整 JSON 到 metadata_info 以备不时之需
                metadata_info = jsonb_set(
                    COALESCE(metadata_info, '{}'), 
                    '{legal_features}', 
                    :features_json
                ),
                
                updated_at = NOW()
            WHERE id = :id
        """)
        
        session.execute(sql, {
            "id": tmpl_id,
            "cat": cls["primary_name"],
            "sub_cat": sub_category,
            "nature": feat["transaction_nature"],
            "obj": feat["contract_object"],
            "comp": feat["complexity"],
            "stance": feat["stance"],
            "kw": json.dumps(keywords, ensure_ascii=False),
            "features_json": json.dumps(feat, ensure_ascii=False)
        })
        session.commit()
        return True
        
    except Exception as e:
        print(f"  ❌ 数据库写入失败: {e}")
        session.rollback()
        return False

# ==================== 主流程 ====================

def main():
    print("🚀 启动 Data Governance 2.0 (Legal Logic Edition)...")
    
    db = get_db_session()
    llm = get_llm()
    taxonomy = load_taxonomy()
    
    # 1. 选出待处理的模板（仅处理 templates_source 目录下的 Markdown 文件）
    # 逻辑：如果 transaction_nature 为空，说明还没被 V2 脚本处理过
    try:
        templates = db.execute(text("""
            SELECT id, name, file_url
            FROM contract_templates
            WHERE transaction_nature IS NULL
              AND file_url LIKE 'templates_source/%'
            ORDER BY name
        """)).fetchall()
    except Exception as e:
        print(f"❌ 数据库查询失败，请检查是否已添加 transaction_nature 等新字段！错误: {e}")
        return

    print(f"📄 待治理模板数 (templates_source): {len(templates)}")
    
    for i, tmpl in enumerate(templates):
        tmpl_id, name, file_url = tmpl
        print(f"[{i+1}/{len(templates)}] 分析: {name} ...", end="", flush=True)
        
        # 读取文件
        full_path = BACKEND_DIR / file_url
        if not full_path.exists():
            print(" ❌ 文件丢失")
            continue
            
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        # AI 分析
        result = analyze_template_with_ai(llm, content, taxonomy, name)
        
        if result:
            if update_db(db, tmpl_id, result):
                print(f" ✅ -> {result['features']['transaction_nature']}")
            else:
                print(" ❌ DB Error")
        else:
            print(" ❌ AI Error")
            
        time.sleep(0.5) # 限流保护

    print("\n🎉 治理完成！")
    db.close()

if __name__ == "__main__":
    main()