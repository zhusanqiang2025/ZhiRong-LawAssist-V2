# backend/app/services/review_rules_service.py
"""
JSON 规则文件管理服务

负责读取、写入、更新 review_rules.json 文件
"""
import json
import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from app.schemas import (
    RuleCreate,
    RuleUpdate,
    UniversalRulesOut,
    FeatureRuleOut,
    StanceRuleOut,
    RuleInstruction
)

logger = logging.getLogger(__name__)

# 规则文件路径 (在 backend 的 config 文件夹中)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(os.path.dirname(CURRENT_DIR))
RULE_FILE_PATH = os.path.join(BACKEND_DIR, "config", "review_rules.json")


class ReviewRulesService:
    """JSON 规则文件管理服务"""

    def __init__(self):
        self._ensure_rule_file_exists()

    def _ensure_rule_file_exists(self):
        """确保规则文件存在"""
        if not os.path.exists(RULE_FILE_PATH):
            logger.warning(f"规则文件不存在: {RULE_FILE_PATH}")
            # 创建默认规则文件
            self._create_default_rules()

    def _create_default_rules(self):
        """创建默认规则文件"""
        default_rules = {
            "version": "3.0",
            "description": "基于法律特征与立场的模块化审查规则库",
            "universal_rules": {
                "name": "通用底线审查",
                "description": "适用于所有类型合同的微观与形式审查",
                "rules": []
            },
            "feature_rules": {
                "交易性质": {},
                "合同标的": {}
            },
            "stance_rules": {
                "party_a": {
                    "role_definition": "甲方 (通常为：买方/发包方/出资方/雇主)",
                    "rules": []
                },
                "party_b": {
                    "role_definition": "乙方 (通常为：卖方/承包方/受托方/劳动者)",
                    "rules": []
                }
            }
        }
        os.makedirs(os.path.dirname(RULE_FILE_PATH), exist_ok=True)
        with open(RULE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(default_rules, f, ensure_ascii=False, indent=2)
        logger.info(f"已创建默认规则文件: {RULE_FILE_PATH}")

    def _load_rules(self) -> Dict[str, Any]:
        """加载规则文件"""
        try:
            with open(RULE_FILE_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载规则文件失败: {e}")
            raise

    def _save_rules(self, rules: Dict[str, Any]):
        """保存规则文件"""
        try:
            # 备份原文件
            if os.path.exists(RULE_FILE_PATH):
                backup_path = RULE_FILE_PATH + ".backup"
                with open(RULE_FILE_PATH, 'r', encoding='utf-8') as f:
                    with open(backup_path, 'w', encoding='utf-8') as bf:
                        bf.write(f.read())
                logger.debug(f"已备份规则文件至: {backup_path}")

            # 写入新文件
            with open(RULE_FILE_PATH, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            logger.info(f"规则文件已保存: {RULE_FILE_PATH}")
        except Exception as e:
            logger.error(f"保存规则文件失败: {e}")
            raise

    def get_all_rules(self) -> Dict[str, Any]:
        """获取所有规则"""
        return self._load_rules()

    def get_universal_rules(self) -> UniversalRulesOut:
        """获取通用规则"""
        rules = self._load_rules()
        universal = rules.get("universal_rules", {})
        return UniversalRulesOut(
            name=universal.get("name", ""),
            description=universal.get("description", ""),
            rules=[
                {
                    "id": r.get("id", ""),
                    "category": r.get("category", ""),
                    "instruction": r.get("instruction", "")
                }
                for r in universal.get("rules", [])
            ]
        )

    def get_feature_rules(self, feature_type: Optional[str] = None, feature_value: Optional[str] = None) -> List[FeatureRuleOut]:
        """获取特征规则"""
        rules = self._load_rules()
        feature_rules = rules.get("feature_rules", {})
        result = []

        for f_type, f_values in feature_rules.items():
            if feature_type and f_type != feature_type:
                continue

            for f_val, rule_list in f_values.items():
                if feature_value and f_val != feature_value:
                    continue

                result.append(FeatureRuleOut(
                    feature_type=f_type,
                    feature_value=f_val,
                    rules=[RuleInstruction(**r) for r in rule_list]
                ))

        return result

    def get_stance_rules(self, party: Optional[str] = None) -> List[StanceRuleOut]:
        """获取立场规则"""
        rules = self._load_rules()
        stance_rules = rules.get("stance_rules", {})
        result = []

        for party_key, party_data in stance_rules.items():
            if party and party_key != party:
                continue

            result.append(StanceRuleOut(
                party=party_key,
                role_definition=party_data.get("role_definition", ""),
                rules=[RuleInstruction(**r) for r in party_data.get("rules", [])]
            ))

        return result

    def add_universal_rule(self, category: str, instruction: str) -> str:
        """添加通用规则"""
        rules = self._load_rules()
        universal = rules["universal_rules"]

        # 生成规则 ID
        rule_id = f"U{len(universal['rules']) + 1:02d}"

        new_rule = {
            "id": rule_id,
            "category": category,
            "instruction": instruction
        }

        universal["rules"].append(new_rule)
        self._save_rules(rules)

        return rule_id

    def add_feature_rule(self, feature_type: str, feature_value: str, focus: str, instruction: str):
        """添加特征规则"""
        rules = self._load_rules()

        if feature_type not in rules["feature_rules"]:
            rules["feature_rules"][feature_type] = {}

        if feature_value not in rules["feature_rules"][feature_type]:
            rules["feature_rules"][feature_type][feature_value] = []

        new_rule = {"focus": focus, "instruction": instruction}
        rules["feature_rules"][feature_type][feature_value].append(new_rule)

        self._save_rules(rules)

    def add_stance_rule(self, party: str, focus: str, instruction: str):
        """添加立场规则"""
        rules = self._load_rules()

        if party not in rules["stance_rules"]:
            raise ValueError(f"无效的立场: {party}")

        new_rule = {"focus": focus, "instruction": instruction}
        rules["stance_rules"][party]["rules"].append(new_rule)

        self._save_rules(rules)

    def update_universal_rule(self, rule_id: str, category: Optional[str] = None, instruction: Optional[str] = None):
        """更新通用规则"""
        rules = self._load_rules()
        universal = rules["universal_rules"]

        for rule in universal["rules"]:
            if rule["id"] == rule_id:
                if category is not None:
                    rule["category"] = category
                if instruction is not None:
                    rule["instruction"] = instruction
                self._save_rules(rules)
                return

        raise ValueError(f"规则不存在: {rule_id}")

    def update_feature_rule(self, feature_type: str, feature_value: str, index: int,
                           focus: Optional[str] = None, instruction: Optional[str] = None):
        """更新特征规则"""
        rules = self._load_rules()

        try:
            rule_list = rules["feature_rules"][feature_type][feature_value]
            if 0 <= index < len(rule_list):
                if focus is not None:
                    rule_list[index]["focus"] = focus
                if instruction is not None:
                    rule_list[index]["instruction"] = instruction
                self._save_rules(rules)
                return
        except KeyError:
            pass

        raise ValueError(f"规则不存在")

    def update_stance_rule(self, party: str, index: int, focus: Optional[str] = None, instruction: Optional[str] = None):
        """更新立场规则"""
        rules = self._load_rules()

        try:
            rule_list = rules["stance_rules"][party]["rules"]
            if 0 <= index < len(rule_list):
                if focus is not None:
                    rule_list[index]["focus"] = focus
                if instruction is not None:
                    rule_list[index]["instruction"] = instruction
                self._save_rules(rules)
                return
        except KeyError:
            pass

        raise ValueError(f"规则不存在")

    def delete_universal_rule(self, rule_id: str):
        """删除通用规则"""
        rules = self._load_rules()
        universal = rules["universal_rules"]

        original_length = len(universal["rules"])
        universal["rules"] = [r for r in universal["rules"] if r["id"] != rule_id]

        if len(universal["rules"]) == original_length:
            raise ValueError(f"规则不存在: {rule_id}")

        self._save_rules(rules)

    def delete_feature_rule(self, feature_type: str, feature_value: str, index: int):
        """删除特征规则"""
        rules = self._load_rules()

        try:
            rule_list = rules["feature_rules"][feature_type][feature_value]
            if 0 <= index < len(rule_list):
                rule_list.pop(index)
                # 如果列表为空，删除该键
                if not rule_list:
                    del rules["feature_rules"][feature_type][feature_value]
                self._save_rules(rules)
                return
        except (KeyError, IndexError):
            pass

        raise ValueError(f"规则不存在")

    def delete_stance_rule(self, party: str, index: int):
        """删除立场规则"""
        rules = self._load_rules()

        try:
            rule_list = rules["stance_rules"][party]["rules"]
            if 0 <= index < len(rule_list):
                rule_list.pop(index)
                self._save_rules(rules)
                return
        except (KeyError, IndexError):
            pass

        raise ValueError(f"规则不存在")


# 单例
review_rules_service = ReviewRulesService()
