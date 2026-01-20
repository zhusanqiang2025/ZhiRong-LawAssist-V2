"""
文书起草模块配置

定义支持的文书类型及其配置信息
"""

DOCUMENT_DRAFTING_CONFIG = {
    # 函件类（使用 letter 模板）
    "lawyer_letter": {
        "name": "律师函",
        "template_type": "letter",
        "template_file": "lawyer_letter.md",
        "description": "律师事务所函件，用于催告、通知等",
        "legal_features": {
            "transaction_nature": "法律服务",
            "contract_object": "法律服务函件"
        }
    },
    "demand_letter": {
        "name": "催告函",
        "template_type": "letter",
        "template_file": "demand_letter.md",
        "description": "催告履行义务的函件",
        "legal_features": {
            "transaction_nature": "债务催收",
            "contract_object": "债权催收"
        }
    },
    "notification_letter": {
        "name": "通知函",
        "template_type": "letter",
        "template_file": "notification_letter.md",
        "description": "各类通知告知函件",
        "legal_features": {
            "transaction_nature": "通知告知",
            "contract_object": "通知事项"
        }
    },
    "legal_opinion": {
        "name": "法律意见书",
        "template_type": "letter",
        "template_file": "legal_opinion.md",
        "description": "专业法律意见文书",
        "legal_features": {
            "transaction_nature": "法律服务",
            "contract_object": "法律咨询意见"
        }
    },

    # 司法文书类（使用 judicial 模板）
    "civil_complaint": {
        "name": "民事起诉状",
        "template_type": "judicial",
        "template_file": "civil_complaint.md",
        "description": "民事诉讼起诉状",
        "legal_features": {
            "transaction_nature": "民事诉讼",
            "contract_object": "民事纠纷",
            "stance": "原告立场"
        }
    },
    "defense_statement": {
        "name": "答辩状",
        "template_type": "judicial",
        "template_file": "defense_statement.md",
        "description": "被告答辩状",
        "legal_features": {
            "transaction_nature": "民事诉讼",
            "contract_object": "民事纠纷",
            "stance": "被告立场"
        }
    },
    "evidence_list": {
        "name": "证据清单",
        "template_type": "judicial",
        "template_file": "evidence_list.md",
        "description": "诉讼证据清单",
        "legal_features": {
            "transaction_nature": "民事诉讼",
            "contract_object": "证据材料"
        }
    },
    "application": {
        "name": "申请书",
        "template_type": "judicial",
        "template_file": "application.md",
        "description": "各类申请书（财产保全、先予执行等）",
        "legal_features": {
            "transaction_nature": "民事诉讼",
            "contract_object": "程序申请"
        }
    },
    "power_of_attorney": {
        "name": "授权委托书",
        "template_type": "judicial",
        "template_file": "power_of_attorney.md",
        "description": "诉讼授权委托书",
        "legal_features": {
            "transaction_nature": "法律服务",
            "contract_object": "代理授权"
        }
    }
}

# 模板文件路径配置
TEMPLATE_BASE_PATH = "backend/templates/documents/"

def get_document_config(document_type: str) -> dict:
    """
    获取指定文书类型的配置

    Args:
        document_type: 文书类型标识

    Returns:
        文书配置字典，如果不存在则返回None
    """
    return DOCUMENT_DRAFTING_CONFIG.get(document_type)

def get_template_path(document_type: str) -> str:
    """
    获取指定文书类型的模板文件路径

    Args:
        document_type: 文书类型标识

    Returns:
        模板文件完整路径
    """
    config = get_document_config(document_type)
    if config and "template_file" in config:
        return f"{TEMPLATE_BASE_PATH}{config['template_file']}"
    return None

def list_document_types(category: str = None) -> list:
    """
    列出支持的文书类型

    Args:
        category: 可选的分类筛选（letter/judicial）

    Returns:
        文书类型配置列表
    """
    if category:
        return [
            config for config in DOCUMENT_DRAFTING_CONFIG.values()
            if config.get("template_type") == category
        ]
    return list(DOCUMENT_DRAFTING_CONFIG.values())
