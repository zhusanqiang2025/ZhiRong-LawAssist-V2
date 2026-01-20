-- =====================================================
-- Legal Transaction Logic V2 - 数据库字段升级
-- =====================================================
--
-- 功能：为 contract_templates 表添加法律交易逻辑相关字段
--
-- 新增字段：
-- 1. transaction_nature - 交易实质（法律关系性质）
-- 2. contract_object - 核心标的（交易对象）
-- 3. complexity - 交易复杂度
--
-- 升级字段：
-- 4. stance - 合同立场（从原有字段扩展使用）
-- 5. metadata_info - JSONB 存储（完整法律特征备份）
--
-- 兼容性：保留原有 delivery_model 和 payment_model 字段
-- =====================================================

-- =====================================================
-- 第一步：添加新字段
-- =====================================================

-- 1. 交易实质 (Transaction Nature)
-- 判断合同背后的法律关系性质
ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS transaction_nature VARCHAR(50);

COMMENT ON COLUMN contract_templates.transaction_nature IS
'交易实质（法律关系性质）：asset_transfer(资产转移), service_delivery(服务提供), resource_sharing(资源共享), entity_creation(主体设立), capital_finance(资本金融), dispute_resolution(争议解决), authorization(单方授权)';

-- 添加索引（用于快速查询特定交易类型的模板）
CREATE INDEX IF NOT EXISTS idx_contract_templates_transaction_nature
ON contract_templates(transaction_nature) WHERE transaction_nature IS NOT NULL;


-- 2. 核心标的 (Contract Object)
-- 交易的对象是什么？
ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS contract_object VARCHAR(50);

COMMENT ON COLUMN contract_templates.contract_object IS
'核心标的（交易对象）：tangible_goods(实物商品), equity(股权), ip(知识产权), human_labor(人工劳务), monetary_debt(金钱债权), data_traffic(数据流量), credibility(信用资质)';

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_contract_templates_contract_object
ON contract_templates(contract_object) WHERE contract_object IS NOT NULL;


-- 3. 交易复杂度 (Complexity)
-- 评估交易的复杂程度
ALTER TABLE contract_templates
ADD COLUMN IF NOT EXISTS complexity VARCHAR(50);

COMMENT ON COLUMN contract_templates.complexity IS
'交易复杂度：internal_simple(内部简单), standard_commercial(标准商业), complex_strategic(复杂战略)';

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_contract_templates_complexity
ON contract_templates(complexity) WHERE complexity IS NOT NULL;


-- =====================================================
-- 第二步：扩展 stance 字段（如果需要）
-- =====================================================

-- 检查 stance 字段是否存在，如果不存在则创建
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates'
        AND column_name = 'stance'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN stance VARCHAR(20);

        COMMENT ON COLUMN contract_templates.stance IS
        '合同立场：buyer_friendly(买方友好), seller_friendly(卖方友好), neutral(中立平衡)';
    END IF;
END $$;

-- 添加索引
CREATE INDEX IF NOT EXISTS idx_contract_templates_stance
ON contract_templates(stance) WHERE stance IS NOT NULL;


-- =====================================================
-- 第三步：确保 metadata_info 字段存在（JSONB 类型）
-- =====================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'contract_templates'
        AND column_name = 'metadata_info'
    ) THEN
        ALTER TABLE contract_templates
        ADD COLUMN metadata_info JSONB DEFAULT '{}'::jsonb;

        COMMENT ON COLUMN contract_templates.metadata_info IS
        '元数据信息（JSONB）：存储完整的法律特征、AI 分析结果等扩展信息';
    END IF;
END $$;


-- =====================================================
-- 第四步：创建组合索引（用于多维查询）
-- =====================================================

-- 交易实质 + 标的物 组合索引
CREATE INDEX IF NOT EXISTS idx_contract_templates_nature_object
ON contract_templates(transaction_nature, contract_object)
WHERE transaction_nature IS NOT NULL AND contract_object IS NOT NULL;

-- 复杂度 + 立场 组合索引
CREATE INDEX IF NOT EXISTS idx_contract_templates_complexity_stance
ON contract_templates(complexity, stance)
WHERE complexity IS NOT NULL AND stance IS NOT NULL;


-- =====================================================
-- 第五步：数据迁移示例（可选）
-- =====================================================

-- 如果需要，可以根据原有的 delivery_model 推断 transaction_nature
-- 这只是一个示例，实际逻辑可能需要更复杂的规则

/*
-- 示例：单一交付 -> 可能是资产转移
UPDATE contract_templates
SET transaction_nature = 'asset_transfer'
WHERE delivery_model = '单一交付'
  AND transaction_nature IS NULL;

-- 示例：持续交付 -> 可能是服务提供
UPDATE contract_templates
SET transaction_nature = 'service_delivery'
WHERE delivery_model = '持续交付'
  AND transaction_nature IS NULL;

-- 示例：分期交付 -> 可能是资产转移或服务提供（需要人工判断）
-- 这里暂时不自动填充，留给 V2 脚本处理
*/


-- =====================================================
-- 第六步：创建视图（便于查询）
-- =====================================================

-- 创建法律交易逻辑视图
CREATE OR REPLACE VIEW v_contract_templates_legal_logic AS
SELECT
    id,
    name,
    category,
    subcategory,

    -- 法律交易逻辑字段
    transaction_nature,
    contract_object,
    complexity,
    stance,

    -- 原有字段（保留兼容）
    primary_contract_type,
    delivery_model,
    payment_model,
    risk_level,

    -- 状态信息
    status,
    is_public,
    is_recommended,

    -- 元数据
    metadata_info,
    created_at,
    updated_at

FROM contract_templates
WHERE status = 'active';

COMMENT ON VIEW v_contract_templates_legal_logic IS
'合同模板法律交易逻辑视图：展示所有活跃模板的法律特征';


-- =====================================================
-- 第七步：创建统计查询函数
-- =====================================================

-- 统计各交易实质的模板数量
CREATE OR REPLACE FUNCTION get_transaction_nature_stats()
RETURNS TABLE (
    transaction_nature VARCHAR(50),
    count BIGINT,
    percentage NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        transaction_nature,
        COUNT(*) as count,
        ROUND(COUNT(*)::NUMERIC / NULLIF((SELECT COUNT(*) FROM contract_templates WHERE transaction_nature IS NOT NULL), 0) * 100, 2) as percentage
    FROM contract_templates
    WHERE transaction_nature IS NOT NULL
    GROUP BY transaction_nature
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_transaction_nature_stats() IS
'统计各交易实质类型的模板数量和占比';


-- =====================================================
-- 第八步：验证脚本
-- =====================================================

-- 检查新字段是否创建成功
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'contract_templates'
  AND column_name IN ('transaction_nature', 'contract_object', 'complexity', 'stance', 'metadata_info')
ORDER BY ordinal_position;


-- =====================================================
-- 完成提示
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '=====================================================';
    RAISE NOTICE '✅ Legal Transaction Logic V2 数据库升级完成！';
    RAISE NOTICE '=====================================================';
    RAISE NOTICE '';
    RAISE NOTICE '新增字段：';
    RAISE NOTICE '  - transaction_nature: 交易实质';
    RAISE NOTICE '  - contract_object: 核心标的';
    RAISE NOTICE '  - complexity: 交易复杂度';
    RAISE NOTICE '';
    RAISE NOTICE '扩展字段：';
    RAISE NOTICE '  - stance: 合同立场';
    RAISE NOTICE '  - metadata_info: 元数据（JSONB）';
    RAISE NOTICE '';
    RAISE NOTICE '下一步：';
    RAISE NOTICE '  1. 运行 V2 脚本填充数据：python scripts/enrich_templates_with_categories.py';
    RAISE NOTICE '  2. 验证数据填充结果：SELECT * FROM v_contract_templates_legal_logic;';
    RAISE NOTICE '=====================================================';
END $$;
