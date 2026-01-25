---
name: pydantic-validator-v2
description: Use when defining data models for APIs, usage reports, or data exchange between backend and frontend. Focuses on strict validation and schema definition using Pydantic V2.
---

# Pydantic Validator V2

## Overview
Establishes strict data contracts using Pydantic V2. Ensures that data exchanged between backend (`investigation_report_builder.py`) and frontend (`React`) adheres to a rigid schema, preventing runtime errors and "UI white screens".

## When to Use
- Defining the structure of `analysis_report.json` or `profiles.json`.
- Validating external API responses (e.g., from generic extraction tools).
- Ensuring type safety for complex nested structures (like the "Three-Segment Report").
- Migrating from untyped dicts to typed models.

## Core Rules

### 1. Model Definition (V2 Style)
**STOP**: Using `pydantic.BaseModel` without type hints or using V1 `validator` decorators if possible (use `field_validator`).
**USE**: `pydantic.BaseModel` with standard python types and `Field` for metadata.

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from enum import Enum

class RiskLevel(str, Enum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

class IssueItem(BaseModel):
    category: str = Field(..., description="问题分类")
    severity: RiskLevel
    description: str = Field(..., min_length=5)
    
    @field_validator('amount')
    @classmethod
    def check_positive(cls, v: float) -> float:
        if v < 0:
            raise ValueError('Amount must be positive')
        return v
```

### 2. Strict Mode & Extra Fields
- By default, ignore extra fields to stay forward-compatible.
- Use `ConfigDict` in V2.

```python
from pydantic import ConfigDict

class BaseSchema(BaseModel):
    model_config = ConfigDict(extra='ignore') 
```

### 3. Serialization (Backend -> Frontend)
**STOP**: Manually converting objects to dicts with `.__dict__`.
**USE**: `model.model_dump()` (V2) or `model.model_dump_json()`.

```python
# ✅ GOOD
report_json = report_model.model_dump_json(by_alias=True)
```

### 4. Handling Missing Data (The "Default" Trap)
**STOP**: Allowing `None` everywhere without handling it in UI layout.
**USE**: Set sensible defaults in Pydantic or use `Optional[...]` effectively.

```python
class AssetInfo(BaseModel):
    real_estate: List[str] = Field(default_factory=list) # ✅ Returns [] instead of None
```

## Anti-Patterns
- **God Models**: Putting entire app state in one model. Break it down (`PersonSection`, `CompanySection`).
- **Logic in Models**: Don't put heavy computation in validators. Validators are for *checking*, not *doing*.
