-- 更新合同模板分类体系
-- 基于 Contract Classification.txt 的完整分类
-- PostgreSQL 版本

-- ============================================
-- 第一步：更新现有的 primary_contract_type 枚举值
-- ============================================

-- 为现有记录更新合同类型（基于新的完整分类）
UPDATE contract_templates
SET primary_contract_type = CASE
    -- 民法典典型合同
    WHEN name LIKE '%买卖%' OR name LIKE '%购销%' OR name LIKE '%采购%' OR name LIKE '%供货%' OR name LIKE '%销售%' THEN '买卖合同'
    WHEN name LIKE '%赠与%' THEN '赠与合同'
    WHEN name LIKE '%借款%' OR name LIKE '%借贷%' OR name LIKE '%融资%' THEN '借款合同'
    WHEN name LIKE '%保证%' THEN '保证合同'
    WHEN name LIKE '%租赁%' THEN '租赁合同'
    WHEN name LIKE '%承揽%' OR name LIKE '%加工%' OR name LIKE '%定制%' THEN '承揽合同'
    WHEN name LIKE '%建设%' OR name LIKE '%工程%' OR name LIKE '%施工%' OR name LIKE '%EPC%' OR name LIKE '%总承包%' OR name LIKE '%分包%' THEN '建设工程合同'
    WHEN name LIKE '%运输%' THEN '运输合同'
    WHEN name LIKE '%技术%' OR name LIKE '%专利%' OR name LIKE '%软件许可%' OR name LIKE '%研发%' THEN '技术合同'
    WHEN name LIKE '%保管%' THEN '保管合同'
    WHEN name LIKE '%委托%' OR name LIKE '%代理%' OR name LIKE '%中介%' OR name LIKE '%行纪%' THEN '委托合同'
    WHEN name LIKE '%物业%' THEN '物业服务合同'
    WHEN name LIKE '%合伙%' OR name LIKE '%有限合伙%' OR name LIKE '%普通合伙%' THEN '合伙合同'

    -- 非典型合同
    WHEN name LIKE '%股东%' OR name LIKE '%股权%' OR name LIKE '%出资%' OR name LIKE '%并购%' OR name LIKE '%增资%' OR name LIKE '%合并%' OR name LIKE '%代持%' OR name LIKE '%回购%' THEN '股权类协议'
    WHEN name LIKE '%劳动%' OR name LIKE '%劳务%' OR name LIKE '%竞业%' OR name LIKE '%保密%' OR name LIKE '%员工%' THEN '劳动合同'
    WHEN name LIKE '%加盟%' OR name LIKE '%特许经营%' OR name LIKE '%知识产权%' OR name LIKE '%债权%' OR name LIKE '%资产重组%' OR name LIKE '%项目合作%' OR name LIKE '%联合经营%' THEN '商业协议'

    -- 行业特定合同
    WHEN name LIKE '%SaaS%' OR name LIKE '%API%' OR name LIKE '%用户协议%' OR name LIKE '%隐私政策%' OR name LIKE '%数据保护%' OR name LIKE '%软件授权%' THEN '互联网合同'
    WHEN name LIKE '%贷款%' OR name LIKE '%担保%' OR name LIKE '%投资%' OR name LIKE '%金融产品%' OR name LIKE '%资产管理%' THEN '金融合同'
    WHEN name LIKE '%房产%' OR name LIKE '%不动产%' OR name LIKE '%装修%' OR name LIKE '%物业托管%' THEN '房地产合同'
    WHEN name LIKE '%医疗%' OR name LIKE '%临床试验%' OR name LIKE '%医药%' THEN '医疗合同'
    WHEN name LIKE '%教育%' OR name LIKE '%培训%' OR name LIKE '%教材%' THEN '教育合同'
    WHEN name LIKE '%采购%' OR name LIKE '%供应链%' OR name LIKE '%生产合作%' OR name LIKE '%质量保证%' THEN '供应链合同'
    WHEN name LIKE '%版权%' OR name LIKE '%创作%' OR name LIKE '%经纪%' OR name LIKE '%演出%' OR name LIKE '%影视%' THEN '娱乐合同'

    -- 个人创客及自由职业者
    WHEN name LIKE '%视频%' OR name LIKE '%直播%' OR name LIKE '%带货%' OR name LIKE '%内容创作%' OR name LIKE '%广告%' OR name LIKE '%咨询%' THEN '服务合同'
    WHEN name LIKE '%外包%' OR name LIKE '%短期项目%' THEN '委托合同'
    WHEN name LIKE '%独立承包%' OR name LIKE '%分包%' THEN '承包合同'
    WHEN name LIKE '%软件开发%' THEN '技术合同'
    WHEN name LIKE '%自由职业%' OR name LIKE '%短期雇佣%' THEN '短期雇佣合同'
    WHEN name LIKE '%品牌代言%' OR name LIKE '%合作推广%' OR name LIKE '%营销%' THEN '营销协议'

    -- 跨境与国际合同
    WHEN name LIKE '%跨境%' OR name LIKE '%国际%' THEN '跨境合同'

    -- 补充与特殊合同类型
    WHEN name LIKE '%电子商务%' OR name LIKE '%环保%' OR name LIKE '%食品安全%' OR name LIKE '%危机管理%' THEN '特殊协议'

    -- 默认值
    ELSE '买卖合同'
END
WHERE primary_contract_type IS NULL OR primary_contract_type = '买卖合同';

-- ============================================
-- 第二步：更新行业标签 (industry_tags)
-- ============================================

UPDATE contract_templates
SET industry_tags = CASE
    -- 民法典典型合同行业
    WHEN category LIKE '%通用%' OR category LIKE '%企业%' THEN '["通用"]'
    WHEN category LIKE '%房地产%' OR name LIKE '%房产%' OR name LIKE '%租赁%' OR name LIKE '%物业%' THEN '["房地产"]'
    WHEN category LIKE '%建筑%' OR name LIKE '%建设%' OR name LIKE '%工程%' OR name LIKE '%施工%' THEN '["建筑业"]'
    WHEN category LIKE '%物流%' OR name LIKE '%运输%' THEN '["物流"]'
    WHEN category LIKE '%互联网%' OR name LIKE '%SaaS%' OR name LIKE '%API%' OR name LIKE '%软件%' THEN '["互联网"]'
    WHEN category LIKE '%医疗%' OR name LIKE '%医药%' OR name LIKE '%临床试验%' THEN '["医疗"]'
    WHEN category LIKE '%制造%' OR name LIKE '%采购%' OR name LIKE '%供应链%' THEN '["制造业"]'
    WHEN category LIKE '%商业%' OR name LIKE '%加盟%' OR name LIKE '%特许经营%' THEN '["商业"]'
    WHEN category LIKE '%金融%' OR name LIKE '%投资%' OR name LIKE '%贷款%' OR name LIKE '%担保%' THEN '["金融"]'
    WHEN category LIKE '%教育%' OR name LIKE '%培训%' THEN '["教育"]'
    WHEN category LIKE '%娱乐%' OR name LIKE '%影视%' OR name LIKE '%演出%' OR name LIKE '%创作%' THEN '["文化创意", "娱乐"]'
    WHEN category LIKE '%能源%' OR name LIKE '%光伏%' OR name LIKE '%储能%' OR name LIKE '%EPC%' THEN '["能源"]'
    WHEN category LIKE '%自由职业%' OR name LIKE '%外包%' THEN '["自由职业"]'
    WHEN category LIKE '%电商%' OR name LIKE '%跨境%' OR name LIKE '%营销%' THEN '["电商", "跨境电商"]'

    -- 默认值
    ELSE '["通用"]'
END
WHERE industry_tags IS NULL OR jsonb_array_length(industry_tags) = 0;

-- ============================================
-- 第三步：更新允许的签约主体模型 (allowed_party_models)
-- ============================================

UPDATE contract_templates
SET allowed_party_models = CASE
    -- B2B（企业对企业）
    WHEN name LIKE '%建设工程%' OR name LIKE '%工程%' OR name LIKE '%总承包%' OR name LIKE '%分包%' OR name LIKE '%采购%' OR name LIKE '%供应链%' THEN '["B2B"]'
    WHEN name LIKE '%股权%' OR name LIKE '%股东%' OR name LIKE '%并购%' OR name LIKE '%增资%' OR name LIKE '%合并%' OR name LIKE '%投资%' THEN '["B2B"]'
    WHEN name LIKE '%合伙%' OR name LIKE '%有限合伙%' OR name LIKE '%普通合伙%' THEN '["B2B"]'
    WHEN name LIKE '%技术合作%' OR name LIKE '%SaaS%' OR name LIKE '%API%' OR name LIKE '%数据保护%' THEN '["B2B"]'
    WHEN name LIKE '%金融产品%' OR name LIKE '%资产管理%' OR name LIKE '%贷款%' OR name LIKE '%担保%' THEN '["B2B"]'

    -- B2C（企业对个人）
    WHEN name LIKE '%住宅租赁%' OR name LIKE '%房屋租赁%' OR name LIKE '%房产买卖%' THEN '["B2C"]'
    WHEN name LIKE '%劳动%' OR name LIKE '%劳务%' OR name LIKE '%员工%' OR name LIKE '%竞业%' THEN '["B2C"]'
    WHEN name LIKE '%用户协议%' OR name LIKE '%隐私政策%' OR name LIKE '%软件授权%' OR name LIKE '%电子商务%' THEN '["B2C"]'
    WHEN name LIKE '%教育服务%' OR name LIKE '%培训%' THEN '["B2C"]'
    WHEN name LIKE '%医疗%' OR name LIKE '%医药%' THEN '["B2C"]'

    -- B2P（企业对自由职业者/个人）
    WHEN name LIKE '%视频制作%' OR name LIKE '%直播%' OR name LIKE '%带货%' OR name LIKE '%内容创作%' OR name LIKE '%外包%' OR name LIKE '%自由职业%' THEN '["B2P"]'

    -- 混合模式（B2B + B2C）
    WHEN name LIKE '%买卖%' OR name LIKE '%购销%' OR name LIKE '%供货%' OR name LIKE '%销售%' OR name LIKE '%服务%' OR name LIKE '%咨询%' THEN '["B2B", "B2C"]'
    WHEN name LIKE '%租赁%' OR name LIKE '%装修%' OR name LIKE '%物业%' THEN '["B2B", "B2C"]'
    WHEN name LIKE '%加盟%' OR name LIKE '%特许经营%' OR name LIKE '%品牌代言%' OR name LIKE '%合作推广%' THEN '["B2B", "B2C"]'

    -- 默认值：B2B 和 B2C
    ELSE '["B2B", "B2C"]'
END
WHERE allowed_party_models IS NULL OR jsonb_array_length(allowed_party_models) = 0;

-- ============================================
-- 第四步：更新交付模型 (delivery_model)
-- ============================================

UPDATE contract_templates
SET delivery_model = CASE
    -- 单一交付
    WHEN name LIKE '%买卖%' OR name LIKE '%购销%' OR name LIKE '%采购%' OR name LIKE '%供货%' OR name LIKE '%赠与%' OR name LIKE '%保管%' THEN '单一交付'

    -- 分期交付
    WHEN name LIKE '%建设%' OR name LIKE '%工程%' OR name LIKE '%施工%' OR name LIKE '%总承包%' OR name LIKE '%分包%' OR name LIKE '%研发%' OR name LIKE '%培训%' THEN '分期交付'

    -- 持续交付
    WHEN name LIKE '%租赁%' OR name LIKE '%劳动%' OR name LIKE '%劳务%' OR name LIKE '%物业%' OR name LIKE '%SaaS%' OR name LIKE '%用户协议%' OR name LIKE '%服务%' OR name LIKE '%咨询%' OR name LIKE '%外包%' THEN '持续交付'

    -- 复合交付（商品+服务）
    WHEN name LIKE '%EPC%' OR name LIKE '%设备%安装%' OR name LIKE '%供货%施工%' OR name LIKE '%建设%设备%' OR name LIKE '%装修%' THEN '复合交付'

    -- 默认值
    ELSE '单一交付'
END
WHERE delivery_model IS NULL OR delivery_model = '单一交付';

-- ============================================
-- 第五步：更新付款模型 (payment_model)
-- ============================================

UPDATE contract_templates
SET payment_model = CASE
    -- 一次性付款
    WHEN name LIKE '%买卖%' OR name LIKE '%购销%' OR name LIKE '%赠与%' OR name LIKE '%保管%' THEN '一次性付款'

    -- 分期付款
    WHEN name LIKE '%建设%' OR name LIKE '%工程%' OR name LIKE '%施工%' OR name LIKE '%租赁%' OR name LIKE '%装修%' OR name LIKE '%培训%' THEN '分期付款'

    -- 定期结算
    WHEN name LIKE '%劳动%' OR name LIKE '%劳务%' OR name LIKE '%物业%' OR name LIKE '%SaaS%' OR name LIKE '%服务%' OR name LIKE '%咨询%' OR name LIKE '%外包%' OR name LIKE '%自由职业%' THEN '定期结算'

    -- 混合模式
    WHEN name LIKE '%EPC%' OR name LIKE '%设备%安装%' OR name LIKE '%供货%施工%' OR name LIKE '%加盟%' OR name LIKE '%特许经营%' THEN '混合模式'

    -- 默认值
    ELSE '一次性付款'
END
WHERE payment_model IS NULL;

-- ============================================
-- 第六步：更新风险等级 (risk_level)
-- ============================================

UPDATE contract_templates
SET risk_level = CASE
    -- 高风险
    WHEN name LIKE '%劳动%' OR name LIKE '%劳务%' OR name LIKE '%建设工程%' OR name LIKE '%工程%' OR name LIKE '%股权%' OR name LIKE '%并购%' OR name LIKE '%增资%' OR name LIKE '%合并%' OR name LIKE '%技术开发%' OR name LIKE '%医疗%' OR name LIKE '%临床试验%' THEN 'high'

    -- 中风险
    WHEN name LIKE '%合作%' OR name LIKE '%合资%' OR name LIKE '%合伙%' OR name LIKE '%租赁%' OR name LIKE '%加盟%' OR name LIKE '%特许经营%' OR name LIKE '%知识产权%' OR name LIKE '%数据保护%' OR name LIKE '%外包%' OR name LIKE '%自由职业%' OR name LIKE '%直播%' OR name LIKE '%带货%' THEN 'mid'

    -- 低风险
    WHEN name LIKE '%买卖%' OR name LIKE '%购销%' OR name LIKE '%采购%' OR name LIKE '%赠与%' OR name LIKE '%保管%' OR name LIKE '%委托%' OR name LIKE '%代理%' OR name LIKE '%教育%' OR name LIKE '%培训%' OR name LIKE '%咨询%' OR name LIKE '%用户协议%' THEN 'low'

    -- 默认值
    ELSE 'low'
END
WHERE risk_level IS NULL OR risk_level = 'low';

-- ============================================
-- 第七步：更新推荐级别 (is_recommended)
-- ============================================

UPDATE contract_templates
SET is_recommended = CASE
    -- 推荐的高频标准合同
    WHEN name IN (
        '一般商品买卖合同（简单版）',
        '房屋买卖合同',
        '货物买卖合同',
        '一般住宅房屋租赁合同（简单版）',
        '商业房屋租赁合同',
        '劳动合同',
        '劳务合同',
        '技术咨询合同',
        '技术服务合同',
        '咨询服务合同',
        '采购合同（适用于机械设备类货物采购）',
        '采购合同（适用物资采购）',
        '建设工程设计合同',
        '软件开发合同',
        '保密协议',
        '和解协议'
    ) THEN TRUE

    -- 不推荐
    ELSE FALSE
END
WHERE is_recommended IS NULL OR is_recommended = FALSE;

-- ============================================
-- 第八步：添加次要合同类型 (secondary_types)
-- ============================================

UPDATE contract_templates
SET secondary_types = CASE
    -- 设备供货+安装
    WHEN name LIKE '%设备%' AND name LIKE '%安装%' THEN '["买卖合同", "建设工程合同"]'
    WHEN name LIKE '%供货%' AND name LIKE '%施工%' THEN '["买卖合同", "建设工程合同"]'

    -- 技术+服务
    WHEN name LIKE '%技术转让%' AND name LIKE '%服务%' THEN '["技术转让合同", "服务合同"]'
    WHEN name LIKE '%技术开发%' AND name LIKE '%服务%' THEN '["技术开发合同", "服务合同"]'

    -- 融资+租赁
    WHEN name LIKE '%融资租赁%' THEN '["借款合同", "租赁合同"]'

    -- 股权+劳动
    WHEN name LIKE '%股权激励%' AND name LIKE '%劳动%' THEN '["股权类协议", "劳动合同"]'

    -- 其他复合情况
    WHEN name LIKE '%EPC%' THEN '["建设工程合同", "买卖合同", "承揽合同"]'
    WHEN name LIKE '%特许经营%' THEN '["商业协议", "知识产权许可"]'
    WHEN name LIKE '%供应链%' THEN '["买卖合同", "运输合同", "保管合同"]'

    -- 单一合同类型，无次要类型
    ELSE NULL
END
WHERE secondary_types IS NULL;

-- ============================================
-- 完成提示
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE '合同分类体系更新完成！';
    RAISE NOTICE '========================================';
    RAISE NOTICE '更新内容：';
    RAISE NOTICE '  1. primary_contract_type - 主合同类型（基于完整分类）';
    RAISE NOTICE '  2. industry_tags - 行业标签';
    RAISE NOTICE '  3. allowed_party_models - 签约主体模型';
    RAISE NOTICE '  4. delivery_model - 交付模型';
    RAISE NOTICE '  5. payment_model - 付款模型';
    RAISE NOTICE '  6. risk_level - 风险等级';
    RAISE NOTICE '  7. is_recommended - 推荐级别';
    RAISE NOTICE '  8. secondary_types - 次要合同类型';
    RAISE NOTICE '========================================';
    RAISE NOTICE '新分类体系特点：';
    RAISE NOTICE '  - 包含民法典典型合同（19种）';
    RAISE NOTICE '  - 包含非典型合同（4大类）';
    RAISE NOTICE '  - 包含行业特定合同（8个行业）';
    RAISE NOTICE '  - 包含个人创客及自由职业者合同（6类）';
    RAISE NOTICE '  - 包含跨境与国际合同';
    RAISE NOTICE '  - 包含补充与特殊合同类型';
    RAISE NOTICE '========================================';
END $$;
