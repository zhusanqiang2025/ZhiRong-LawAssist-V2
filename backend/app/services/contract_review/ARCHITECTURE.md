# Contract Review Module - Architecture Summary

## Overview
This document describes the refactored contract review system using LangGraph and database-driven rules.

## System Architecture

### 1. Core Components

```
contract_review/
├── graph.py                 # LangGraph state machine definition
├── state.py                 # AgentState schema
├── schemas.py               # Pydantic models (ReviewOutput, ContractProfile, etc.)
├── rule_assembler.py        # Dynamic rule loading from database
└── nodes/
    ├── basic.py             # Metadata extraction and final report nodes
    └── ai_reviewer.py       # Three-stage AI review node
```

### 2. LangGraph State Machine

```
┌─────────────────────────────────────────────────────────────────┐
│                        Contract Review Workflow                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Start ──> extract_metadata ──> ai_reviewer ──> human_gate     │
│                                            │                    │
│                                            v                    │
│                                       final_report ──> End      │
│                                                                   │
│  Interrupt Point: human_gate (waits for human confirmation)     │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Three-Stage Review Process (ai_reviewer.py)

#### Stage 1: Contract Profiling
- **Purpose**: Identify legal attributes of the contract
- **Output**: `ContractProfile` (contract_type, ongoing_service, composite, personal_dependency)
- **Input**: Contract text (first 6000 chars) + metadata

#### Stage 2: Legal Relationship Analysis
- **Purpose**: Analyze legal relationships and applicable laws
- **Output**: `LegalRelationshipAnalysis` (labor_relation_risk, tort_risk, applicable_laws)
- **Input**: Contract text + Stage 1 profile

#### Stage 3: Rule-Based Risk Review
- **Purpose**: Execute risk review using RuleAssembler
- **Output**: `ReviewOutput` (summary, issues list)
- **Input**: Contract text + profile + relationships + stance + rules

### 4. Rule Categories

The new system uses four rule categories (replacing the old macro/meso/micro system):

| Category | Description | Example Rules |
|----------|-------------|---------------|
| **universal** | General rules applicable to all contracts | Form quality, definition consistency, dispute resolution |
| **feature** | Rules based on transaction nature and contract subject | [交易性质-转移所有权], [合同标的-不动产] |
| **stance** | Position-specific defensive rules | [立场-party_a], [立场-party_b] |
| **custom** | User-defined custom rules | User-specific review preferences |

### 5. RuleAssembler - Dynamic Rule Loading

```python
# RuleAssembler queries the database for rules
rule_assembler.assemble_prompt_context(
    legal_features=profile,      # From Stage 1
    stance=stance,               # User's position (party_a/party_b)
    user_id=user_id             # For custom rules
)
```

**Key Features**:
- **No caching**: Reads from database on each invocation
- **Admin changes take immediate effect**: No restart required
- **Feature-based filtering**: Matches rules by transaction nature and contract subject
- **Stance-based filtering**: Applies defensive rules based on user position
- **Knowledge graph integration**: Dynamic rule deduction based on contract type

### 6. Database Schema

#### `contract_review_rules` table
```sql
CREATE TABLE contract_review_rules (
    id INTEGER PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    description VARCHAR(255),
    content TEXT NOT NULL,
    rule_category VARCHAR(20) NOT NULL DEFAULT 'custom',  -- universal/feature/stance/custom
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    is_system BOOLEAN DEFAULT FALSE,
    creator_id INTEGER REFERENCES users(id),
    created_at DATETIME
);
```

### 7. API Endpoints

#### Contract Review API
- `POST /api/contract/{contract_id}/deep-review` - Start LangGraph review
- `GET /api/contract/{contract_id}/review-results` - Get review results

#### Admin API (Rule Management)
- `GET /api/v1/admin/rules` - List all rules
- `POST /api/v1/admin/rules` - Create new rule
- `PUT /api/v1/admin/rules/{id}` - Update rule
- `DELETE /api/v1/admin/rules/{id}` - Delete rule
- `PUT /api/v1/admin/rules/{id}/toggle` - Enable/disable rule
- `POST /api/v1/admin/rules/migrate-from-json` - Import rules from JSON file

### 8. Frontend Components

#### `ReviewRulesManager.tsx`
Admin UI for managing review rules:
- Display rules by category (universal/feature/stance/custom)
- Create/Edit/Delete rules
- Enable/Disable rules
- Import rules from JSON file
- Filter by category

### 9. Migration Path

#### From JSON to Database
```bash
# Run migration to import rules from review_rules.json
POST /api/v1/admin/rules/migrate-from-json
```

This endpoint:
1. Clears existing system rules (is_system=True)
2. Imports universal rules from JSON
3. Imports feature rules from JSON
4. Imports stance rules from JSON
5. Commits to database

### 10. Integration Points

#### In `contract_router.py`:
```python
@router.post("/{contract_id}/deep-review")
def start_deep_review(
    contract_id: int,
    stance: str = "甲方",
    use_langgraph: bool = True,  # Default to new system
    ...
):
    if use_langgraph:
        result = run_langgraph_review(
            contract_id=contract_id,
            stance=stance,
            user_id=current_user.id
        )
        return {"success": True, "message": "LangGraph 审查完成"}
    else:
        # Fallback to legacy system
        service = ContractReviewService(db)
        service.run_deep_review(...)
```

#### In `ai_reviewer.py` (Stage 3):
```python
def execute_stage_3(text, stance, profile, relationships, user_rules):
    # Dynamic rule assembly
    rule_pack_text = rule_assembler.assemble_prompt_context(
        legal_features=profile,
        stance=stance,
        user_custom_rules=user_rules
    )
    # Execute LLM review with rule pack
    ...
```

### 11. Knowledge Graph Integration

The `KnowledgeGraphService` loads contract type definitions from `config/contract_knowledge_graph.json`:
- Provides contract type definitions for dynamic rule deduction
- Supports alias matching for flexible contract type recognition
- Gracefully handles missing files (returns empty list)

**Dynamic Deduction in RuleAssembler**:
```python
def _get_dynamic_deduction_prompt(contract_type_name: str) -> List[str]:
    kg_data = kg_service.get_contract_definition(contract_type_name)
    if not kg_data:
        return []
    # Generate deduction prompt based on contract type features
    ...
```

### 12. Files Modified/Created

#### Modified Files:
- `backend/app/models/contract.py` - Updated comment for rule_category
- `backend/app/schemas.py` - Updated comment for rule_category
- `backend/app/api/contract_router.py` - Added use_langgraph parameter
- `backend/app/api/admin.py` - Added migration endpoint
- `frontend/src/pages/admin/views/ReviewRulesManager.tsx` - Updated categories

#### Created Files:
- `backend/app/services/langgraph_review_service.py` - New unified review service
- `backend/app/services/contract_review/rule_assembler.py` - Complete rewrite (DB-based)

#### Deleted Files:
- `backend/app/services/contract_review/langgraph_runner.py` - Old PoC runner
- `backend/app/services/contract_review/__init__.py` - Not needed (Python 3.3+)
- `backend/app/services/contract_review/nodes/__init__.py` - Not needed (Python 3.3+)

### 13. Testing Checklist

- [x] Module imports work correctly
- [x] Graph builds successfully with all nodes
- [x] RuleAssembler has all required methods
- [x] Database schema supports new categories
- [x] Frontend displays new categories correctly
- [ ] End-to-end test: Upload contract → Review → Verify results
- [ ] Test rule migration from JSON to database
- [ ] Test admin panel: Create/Edit/Delete/Enable/Disable rules

### 14. Known Issues / Future Enhancements

1. **Knowledge Graph File**: `contract_knowledge_graph.json` is optional but recommended for full dynamic deduction functionality

2. **Legacy System**: The old `ContractReviewService` (macro/meso/micro) is kept for backward compatibility but should be deprecated after migration

3. **Python Version Warning**: Pydantic V1 compatibility warning with Python 3.14 (cosmetic only, doesn't affect functionality)

4. **Future Enhancements**:
   - Add rule versioning
   - Implement rule testing/validation before activation
   - Add rule usage analytics
   - Support rule templates for common patterns
