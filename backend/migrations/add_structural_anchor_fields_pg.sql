-- 添加结构锚点字段到 contract_templates 表
-- PostgreSQL 版本迁移脚本
-- 迁移版本：v3.1 - 结构化模板匹配支持

-- 检查表是否存在
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'contract_templates'
    ) THEN
        RAISE EXCEPTION 'Table contract_templates does not exist. Please check your database.';
    END IF;
END $$;

-- 1. 添加主合同类型字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'primary_contract_type'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN primary_contract_type VARCHAR(100) NOT NULL DEFAULT '买卖合同';
        RAISE NOTICE 'Added column: primary_contract_type';
    ELSE
        RAISE NOTICE 'Column already exists: primary_contract_type';
    END IF;
END $$;

-- 2. 添加次要合同类型字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'secondary_types'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN secondary_types JSONB;
        RAISE NOTICE 'Added column: secondary_types';
    ELSE
        RAISE NOTICE 'Column already exists: secondary_types';
    END IF;
END $$;

-- 3. 添加交付模型字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'delivery_model'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN delivery_model VARCHAR(50) NOT NULL DEFAULT '单一交付';
        RAISE NOTICE 'Added column: delivery_model';
    ELSE
        RAISE NOTICE 'Column already exists: delivery_model';
    END IF;
END $$;

-- 4. 添加付款模型字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'payment_model'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN payment_model VARCHAR(50);
        RAISE NOTICE 'Added column: payment_model';
    ELSE
        RAISE NOTICE 'Column already exists: payment_model';
    END IF;
END $$;

-- 5. 添加行业标签字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'industry_tags'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN industry_tags JSONB;
        RAISE NOTICE 'Added column: industry_tags';
    ELSE
        RAISE NOTICE 'Column already exists: industry_tags';
    END IF;
END $$;

-- 6. 添加允许的签约主体模型字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'allowed_party_models'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN allowed_party_models JSONB;
        RAISE NOTICE 'Added column: allowed_party_models';
    ELSE
        RAISE NOTICE 'Column already exists: allowed_party_models';
    END IF;
END $$;

-- 7. 添加风险等级字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'risk_level'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN risk_level VARCHAR(20);
        RAISE NOTICE 'Added column: risk_level';
    ELSE
        RAISE NOTICE 'Column already exists: risk_level';
    END IF;
END $$;

-- 8. 添加推荐级别字段
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates' AND column_name = 'is_recommended'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN is_recommended BOOLEAN DEFAULT FALSE;
        RAISE NOTICE 'Added column: is_recommended';
    ELSE
        RAISE NOTICE 'Column already exists: is_recommended';
    END IF;
END $$;

-- 9. 创建索引以提升查询性能
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_contract_templates_primary_type'
    ) THEN
        CREATE INDEX idx_contract_templates_primary_type ON contract_templates(primary_contract_type);
        RAISE NOTICE 'Created index: idx_contract_templates_primary_type';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_contract_templates_delivery_model'
    ) THEN
        CREATE INDEX idx_contract_templates_delivery_model ON contract_templates(delivery_model);
        RAISE NOTICE 'Created index: idx_contract_templates_delivery_model';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_contract_templates_risk_level'
    ) THEN
        CREATE INDEX idx_contract_templates_risk_level ON contract_templates(risk_level);
        RAISE NOTICE 'Created index: idx_contract_templates_risk_level';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE indexname = 'idx_contract_templates_is_recommended'
    ) THEN
        CREATE INDEX idx_contract_templates_is_recommended ON contract_templates(is_recommended);
        RAISE NOTICE 'Created index: idx_contract_templates_is_recommended';
    END IF;
END $$;

-- 10. 为现有记录设置默认值（基于 category 字段推断）
UPDATE contract_templates
SET primary_contract_type = CASE
    WHEN category LIKE '%买卖%' OR category LIKE '%购销%' OR category LIKE '%采购%' THEN '买卖合同'
    WHEN category LIKE '%建设%' OR category LIKE '%工程%' OR category LIKE '%施工%' THEN '建设工程合同'
    WHEN category LIKE '%承揽%' OR category LIKE '%加工%' OR category LIKE '%定制%' THEN '承揽合同'
    WHEN category LIKE '%技术%' OR category LIKE '%专利%' OR category LIKE '%软件%' THEN '技术转让合同'
    WHEN category LIKE '%租赁%' THEN '租赁合同'
    WHEN category LIKE '%借款%' OR category LIKE '%借贷%' OR category LIKE '%融资%' THEN '借款合同'
    WHEN category LIKE '%劳动%' OR category LIKE '%劳务%' THEN '劳动合同'
    WHEN category LIKE '%委托%' OR category LIKE '%代理%' OR category LIKE '%中介%' THEN '委托合同'
    WHEN category LIKE '%服务%' THEN '服务合同'
    WHEN category LIKE '%合作%' OR category LIKE '%合资%' OR category LIKE '%联营%' THEN '合作协议'
    ELSE '买卖合同'
END
WHERE primary_contract_type IS NULL OR primary_contract_type = '买卖合同';

-- 11. 为现有记录设置默认交付模型
UPDATE contract_templates
SET delivery_model = CASE
    WHEN category LIKE '%租赁%' OR category LIKE '%劳动%' OR category LIKE '%服务%' THEN '持续交付'
    WHEN category LIKE '%建设%' OR category LIKE '%工程%' THEN '分期交付'
    ELSE '单一交付'
END
WHERE delivery_model IS NULL OR delivery_model = '单一交付';

-- 12. 为现有记录设置默认风险等级
UPDATE contract_templates
SET risk_level = CASE
    WHEN category LIKE '%劳动%' OR category LIKE '%建设%' OR category LIKE '%技术%' THEN 'high'
    WHEN category LIKE '%合作%' OR category LIKE '%合资%' THEN 'mid'
    ELSE 'low'
END
WHERE risk_level IS NULL;

-- 完成提示
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '数据库迁移完成！';
    RAISE NOTICE '========================================';
    RAISE NOTICE '已添加以下字段：';
    RAISE NOTICE '  - primary_contract_type (主合同类型)';
    RAISE NOTICE '  - secondary_types (次要合同类型)';
    RAISE NOTICE '  - delivery_model (交付模型)';
    RAISE NOTICE '  - payment_model (付款模型)';
    RAISE NOTICE '  - industry_tags (行业标签)';
    RAISE NOTICE '  - allowed_party_models (签约主体)';
    RAISE NOTICE '  - risk_level (风险等级)';
    RAISE NOTICE '  - is_recommended (推荐级别)';
    RAISE NOTICE '========================================';
    RAISE NOTICE '已创建以下索引：';
    RAISE NOTICE '  - idx_contract_templates_primary_type';
    RAISE NOTICE '  - idx_contract_templates_delivery_model';
    RAISE NOTICE '  - idx_contract_templates_risk_level';
    RAISE NOTICE '  - idx_contract_templates_is_recommended';
    RAISE NOTICE '========================================';
END $$;
