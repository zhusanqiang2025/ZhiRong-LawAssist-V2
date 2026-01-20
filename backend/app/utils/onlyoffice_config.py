"""
OnlyOffice 配置辅助函数
支持自定义插件和增强功能
"""
import os
from typing import Dict, Any, Optional


def get_onlyoffice_config_with_plugins(
    file_url: str,
    document_key: str,
    title: str,
    callback_url: str,
    user_id: str = "1",
    user_name: str = "法务管理员",
    mode: str = "edit",
    is_review_mode: bool = False
) -> Dict[str, Any]:
    """
    生成包含自定义插件的 OnlyOffice 配置

    Args:
        file_url: 文档URL
        document_key: 文档唯一标识
        title: 文档标题
        callback_url: 回调URL
        user_id: 用户ID
        user_name: 用户名
        mode: 编辑模式 (edit/review/view)
        is_review_mode: 是否为审查模式

    Returns:
        OnlyOffice 配置字典
    """
    # 构建插件配置
    plugins_config = []

    # 添加合同审查插件
    base_url = os.getenv("BACKEND_URL", "http://localhost:8000")
    plugin_url = f"{base_url}/static/onlyoffice-plugins/contract-review-plugin"

    plugins_config.append({
        "name": "合同审查插件",
        "nameLocale": {
            "zh": "合同审查插件",
            "en": "Contract Review Plugin"
        },
        "guid": "FADF8F0B-0C89-43C4-8016-2F2316A9E9E1",
        "url": f"{plugin_url}/config.json",
        "icons": [f"{plugin_url}/icon.png", f"{plugin_url}/icon@2x.png"],
        "isViewer": False,
        "EditorsSupport": ["word"],
        "isSystem": False,
        "isVisual": True,
        "initDataType": "none",
        "initData": "",
        "buttons": [
            {
                "text": "搜索并高亮",
                "primary": True,
                "isViewer": False,
                "data": "highlight"
            },
            {
                "text": "应用修订",
                "primary": True,
                "isViewer": False,
                "data": "apply-revision"
            }
        ]
    })

    # 根据模式设置不同的配置
    if mode == "review" or is_review_mode:
        # 审查模式：启用修订跟踪
        customization = {
            "features": {
                "spellcheck": False,
                "trackChanges": True,
                "comments": True
            },
            "review": {
                "showReviewChanges": True,
                "reviewDisplay": "markup",
                "trackChanges": True,
                "hideReviewChanges": False
            },
            "goback": {
                "url": os.getenv("FRONTEND_URL", "http://localhost:3000")
            }
        }
    else:
        customization = {
            "features": {
                "spellcheck": False,
                "trackChanges": False,
                "comments": True
            },
            "goback": {
                "url": os.getenv("FRONTEND_URL", "http://localhost:3000")
            }
        }

    config = {
        "document": {
            "fileType": "docx",
            "key": document_key,
            "title": title,
            "url": file_url,
            "permissions": {
                "comment": True,
                "copy": True,
                "download": True,
                "edit": mode == "edit" or mode == "review",
                "fillForms": True,
                "modifyFilter": True,
                "modifyContentControl": True,
                "review": mode == "review" or is_review_mode,
                "print": True,
                "save": True
            }
        },
        "editorConfig": {
            "mode": mode,
            "lang": "zh-CN",
            "callbackUrl": callback_url,
            "user": {
                "id": user_id,
                "name": user_name
            },
            "embedded": {
                "saveUrl": file_url,
                "embedUrl": file_url,
                "shareUrl": file_url,
                "toolbarDocked": "top"
            },
            "customization": customization,
            "plugins": {
                "pluginsData": plugins_config,
                "autostart": is_review_mode  # 审查模式自动启动插件
            }
        }
    }

    return config


def get_review_mode_config(
    file_url: str,
    document_key: str,
    title: str,
    callback_url: str,
    review_items: list = None
) -> Dict[str, Any]:
    """
    获取审查模式的配置（启用修订跟踪）

    Args:
        file_url: 文档URL
        document_key: 文档唯一标识
        title: 文档标题
        callback_url: 回调URL
        review_items: 审查意见列表

    Returns:
        审查模式配置
    """
    config = get_onlyoffice_config_with_plugins(
        file_url=file_url,
        document_key=document_key,
        title=title,
        callback_url=callback_url,
        mode="review",
        is_review_mode=True
    )

    # 如果有审查意见，添加到配置中
    if review_items:
        config["editorConfig"]["reviewItems"] = review_items

    return config
