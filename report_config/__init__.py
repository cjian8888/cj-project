#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置模块

包含：
- primary_targets_schema: 归集配置 JSON Schema
- primary_targets_service: 归集配置服务（读取、保存、生成默认配置）
"""

from .primary_targets_schema import (
    PrimaryTargetsConfig,
    AnalysisUnit,
    AnalysisUnitMember,
    create_default_config_from_cache,
    validate_config,
    get_example_config,
    SCHEMA_VERSION,
    PRIMARY_TARGETS_JSON_SCHEMA,
)

from .primary_targets_service import (
    PrimaryTargetsService,
    get_service,
)

__all__ = [
    # Schema
    'PrimaryTargetsConfig',
    'AnalysisUnit',
    'AnalysisUnitMember',
    'create_default_config_from_cache',
    'validate_config',
    'get_example_config',
    'SCHEMA_VERSION',
    'PRIMARY_TARGETS_JSON_SCHEMA',
    # Service
    'PrimaryTargetsService',
    'get_service',
]
