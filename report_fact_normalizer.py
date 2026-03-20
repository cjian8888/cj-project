#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize analysis cache facts into a report-package friendly shape."""

from typing import Any, Dict, List, Optional, Tuple


EXTERNAL_SOURCE_DEFINITIONS: List[Tuple[str, str]] = [
    ("precisePropertyData", "property"),
    ("vehicleData", "vehicle"),
    ("wealthProductData", "wealth_product"),
    ("securitiesData", "securities"),
    ("insuranceData", "insurance"),
    ("immigrationData", "immigration"),
    ("hotelData", "hotel"),
    ("hotelCohabitation", "hotel_cohabitation"),
    ("railwayData", "railway"),
    ("flightData", "flight"),
    ("coaddressData", "coaddress"),
    ("coviolationData", "coviolation"),
]


def _as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _as_float(value: Any) -> float:
    try:
        if value in ("", None):
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_int(value: Any) -> int:
    return int(round(_as_float(value)))


def _pick(mapping: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) is not None:
            return mapping.get(key)
    return default


def _count_records(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        total = 0
        for item in value.values():
            if isinstance(item, list):
                total += len(item)
            elif isinstance(item, dict):
                nested_lists = [
                    nested for nested in item.values() if isinstance(nested, list)
                ]
                if nested_lists:
                    total += sum(len(nested) for nested in nested_lists)
                elif item:
                    total += 1
            elif item not in (None, "", [], {}):
                total += 1
        return total
    return 0


def _extract_data_range(metadata: Dict[str, Any]) -> Dict[str, Optional[str]]:
    start = _pick(
        metadata,
        "start_date",
        "startDate",
        "analysis_start_date",
        "analysisStartDate",
        default=None,
    )
    end = _pick(
        metadata,
        "end_date",
        "endDate",
        "analysis_end_date",
        "analysisEndDate",
        default=None,
    )
    return {
        "start_date": str(start).strip() if start else None,
        "end_date": str(end).strip() if end else None,
    }


def _build_entity_summary(name: str, profile: Dict[str, Any], entity_type: str) -> Dict[str, Any]:
    summary = _as_dict(profile.get("summary"))
    account_layer_summary = _as_dict(
        profile.get("account_layer_summary") or summary.get("account_layer_summary")
    )
    layers = _as_dict(account_layer_summary.get("layers"))
    return {
        "entity_name": name,
        "entity_type": entity_type,
        "transaction_count": _as_int(
            _pick(profile, "transactionCount", default=summary.get("transaction_count", 0))
        ),
        "total_income": _as_float(
            _pick(profile, "totalIncome", default=summary.get("total_income", 0))
        ),
        "total_expense": _as_float(
            _pick(profile, "totalExpense", default=summary.get("total_expense", 0))
        ),
        "real_income": _as_float(summary.get("real_income")),
        "real_expense": _as_float(summary.get("real_expense")),
        "offset_detail": _as_dict(summary.get("offset_detail")),
        "account_layer_summary": {
            "has_corporate_account_activity": bool(
                account_layer_summary.get("has_corporate_account_activity", False)
            ),
            "has_mixed_personal_corporate_activity": bool(
                account_layer_summary.get(
                    "has_mixed_personal_corporate_activity", False
                )
            ),
            "dominant_layer": str(account_layer_summary.get("dominant_layer") or "").strip(),
            "note": str(account_layer_summary.get("note") or "").strip(),
            "personal_layer_income": _as_float(
                _as_dict(layers.get("personal")).get("total_income")
            ),
            "personal_layer_expense": _as_float(
                _as_dict(layers.get("personal")).get("total_expense")
            ),
            "corporate_layer_income": _as_float(
                _as_dict(layers.get("corporate")).get("total_income")
            ),
            "corporate_layer_expense": _as_float(
                _as_dict(layers.get("corporate")).get("total_expense")
            ),
        },
    }


def _build_family_entries(
    report: Dict[str, Any], derived_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    families: List[Dict[str, Any]] = []
    family_sections = _as_list(report.get("family_sections"))
    if family_sections:
        for item in family_sections:
            if not isinstance(item, dict):
                continue
            anchor = str(item.get("anchor") or item.get("family_name") or "").strip()
            family_name = str(item.get("family_name") or anchor or "").strip()
            members = [
                str(member).strip()
                for member in _as_list(item.get("members"))
                if str(member).strip()
            ]
            pending_members = []
            for pending in _as_list(item.get("pending_members")):
                if isinstance(pending, dict):
                    pending_name = str(pending.get("name") or "").strip()
                    if pending_name:
                        pending_members.append(pending_name)
            family_summary = _as_dict(item.get("family_summary"))
            families.append(
                {
                    "family_name": family_name or anchor,
                    "anchor": anchor or family_name,
                    "members": members,
                    "member_count": _as_int(
                        item.get("member_count", len(members) if members else 0)
                    ),
                    "pending_members": pending_members,
                    "total_income": _as_float(
                        _pick(
                            family_summary,
                            "real_income",
                            "total_income",
                            default=item.get("total_income", 0),
                        )
                    ),
                    "total_expense": _as_float(
                        _pick(
                            family_summary,
                            "real_expense",
                            "total_expense",
                            default=item.get("total_expense", 0),
                        )
                    ),
                }
            )
        return families

    for item in _as_list(derived_data.get("family_units_v2")):
        if not isinstance(item, dict):
            continue
        anchor = str(item.get("anchor") or "").strip()
        members = [
            str(member).strip()
            for member in _as_list(item.get("members"))
            if str(member).strip()
        ]
        pending_members = []
        for member_detail in _as_list(item.get("member_details")):
            if not isinstance(member_detail, dict):
                continue
            if not member_detail.get("has_data"):
                pending_name = str(member_detail.get("name") or "").strip()
                if pending_name:
                    pending_members.append(pending_name)
        families.append(
            {
                "family_name": str(item.get("family_name") or anchor or "").strip(),
                "anchor": anchor,
                "members": members,
                "member_count": len(members),
                "pending_members": pending_members,
                "total_income": _as_float(item.get("real_income", 0)),
                "total_expense": _as_float(item.get("real_expense", 0)),
            }
        )
    return families


def _build_aggregation_highlights(
    report: Dict[str, Any], derived_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    conclusion = _as_dict(report.get("conclusion"))
    highlights = _as_list(conclusion.get("aggregation_highlights"))
    if highlights:
        normalized: List[Dict[str, Any]] = []
        for item in highlights:
            if not isinstance(item, dict):
                continue
            entity_name = str(item.get("entity") or item.get("name") or "").strip()
            if not entity_name:
                continue
            normalized.append(
                {
                    "entity": entity_name,
                    "entity_type": str(
                        item.get("entity_type") or item.get("entityType") or ""
                    ).strip(),
                    "risk_score": round(
                        _as_float(item.get("risk_score", item.get("riskScore", 0))), 1
                    ),
                    "risk_confidence": round(
                        _as_float(
                            item.get("risk_confidence", item.get("riskConfidence", 0))
                        ),
                        2,
                    ),
                    "risk_level": str(
                        item.get("risk_level") or item.get("riskLevel") or ""
                    ).strip(),
                    "summary": str(item.get("summary") or "").strip(),
                    "top_clues": [
                        str(clue).strip()
                        for clue in _as_list(item.get("top_clues"))
                        if str(clue).strip()
                    ],
                }
            )
        return normalized

    aggregation = _as_dict(derived_data.get("aggregation"))
    ranked_entities = aggregation.get("rankedEntities")
    if not isinstance(ranked_entities, list):
        ranked_entities = aggregation.get("ranked_entities", [])
    normalized = []
    for item in _as_list(ranked_entities):
        if not isinstance(item, dict):
            continue
        entity_name = str(item.get("name") or item.get("entity") or "").strip()
        if not entity_name:
            continue
        explainability = _as_dict(
            item.get("aggregationExplainability", item.get("aggregation_explainability", {}))
        )
        top_clues = []
        for clue in _as_list(explainability.get("top_clues")):
            if isinstance(clue, dict):
                clue_text = str(clue.get("description") or "").strip()
            else:
                clue_text = str(clue).strip()
            if clue_text:
                top_clues.append(clue_text)
        normalized.append(
            {
                "entity": entity_name,
                "entity_type": str(
                    item.get("entityType") or item.get("entity_type") or ""
                ).strip(),
                "risk_score": round(
                    _as_float(item.get("riskScore", item.get("risk_score", 0))), 1
                ),
                "risk_confidence": round(
                    _as_float(
                        item.get("riskConfidence", item.get("risk_confidence", 0))
                    ),
                    2,
                ),
                "risk_level": str(
                    item.get("riskLevel") or item.get("risk_level") or ""
                ).strip(),
                "summary": str(item.get("summary") or "").strip(),
                "top_clues": top_clues[:3],
            }
        )
    return normalized


def _build_suspicion_summary(suspicions: Dict[str, Any]) -> Dict[str, int]:
    return {
        "cash_collisions": len(
            _as_list(suspicions.get("cashCollisions") or suspicions.get("cash_collisions"))
        ),
        "cash_timing_patterns": len(
            _as_list(
                suspicions.get("cashTimingPatterns")
                or suspicions.get("cash_timing_patterns")
            )
        ),
        "direct_transfers": len(
            _as_list(
                suspicions.get("directTransfers") or suspicions.get("direct_transfers")
            )
        ),
        "hidden_assets": len(
            _as_list(suspicions.get("hiddenAssets") or suspicions.get("hidden_assets"))
        ),
        "aml_alerts": len(
            _as_list(suspicions.get("amlAlerts") or suspicions.get("aml_alerts"))
        ),
        "credit_alerts": len(
            _as_list(suspicions.get("creditAlerts") or suspicions.get("credit_alerts"))
        ),
    }


def normalize_report_facts(
    analysis_cache: Dict[str, Any],
    report: Optional[Dict[str, Any]] = None,
    core_persons: Optional[List[str]] = None,
    companies: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Normalize the current cache/report state into a stable semantic fact layer."""
    analysis_cache = _as_dict(analysis_cache)
    report = _as_dict(report)

    profiles = _as_dict(analysis_cache.get("profiles"))
    derived_data = _as_dict(analysis_cache.get("derived_data"))
    suspicions = _as_dict(analysis_cache.get("suspicions"))
    wallet_data = _as_dict(analysis_cache.get("walletData"))
    metadata = _as_dict(analysis_cache.get("metadata"))

    core_persons = [name for name in (core_persons or []) if str(name).strip()]
    companies = [name for name in (companies or []) if str(name).strip()]

    persons = [
        _build_entity_summary(name, _as_dict(profiles.get(name)), "person")
        for name in core_persons
    ]
    company_entities = [
        _build_entity_summary(name, _as_dict(profiles.get(name)), "company")
        for name in companies
    ]

    families = _build_family_entries(report, derived_data)
    aggregation_summary = _as_dict(
        _as_dict(report.get("conclusion")).get("aggregation_summary")
        or _as_dict(derived_data.get("aggregation")).get("summary")
    )
    aggregation_highlights = _build_aggregation_highlights(report, derived_data)

    wallet_summary = _as_dict(wallet_data.get("summary"))
    wallet_subject_count = _as_int(
        wallet_summary.get("subjectCount", len(_as_list(wallet_data.get("subjects"))))
    )
    wallet_transaction_count = _as_int(
        wallet_summary.get("alipayTransactionCount", 0)
    ) + _as_int(wallet_summary.get("tenpayTransactionCount", 0))
    property_record_count = _count_records(analysis_cache.get("precisePropertyData"))
    vehicle_record_count = _count_records(analysis_cache.get("vehicleData"))

    available_external_sources: List[str] = []
    missing_sources: List[str] = []
    for cache_key, label in EXTERNAL_SOURCE_DEFINITIONS:
        if _count_records(analysis_cache.get(cache_key)) > 0:
            available_external_sources.append(label)
        else:
            missing_sources.append(label)

    if wallet_data.get("available"):
        available_external_sources.append("wallet")
    else:
        missing_sources.append("wallet")

    known_limitations: List[str] = []
    if not wallet_data.get("available"):
        known_limitations.append("third_party_wallet_details_not_loaded")
    if property_record_count <= 0:
        known_limitations.append("property_records_missing")
    if vehicle_record_count <= 0:
        known_limitations.append("vehicle_records_missing")
    if not families:
        known_limitations.append("family_units_not_materialized")

    total_transactions = sum(
        item.get("transaction_count", 0) for item in persons + company_entities
    )

    meta = {
        "generated_at": str(
            _pick(_as_dict(report.get("meta")), "generated_at", "generatedAt")
            or metadata.get("generatedAt")
            or ""
        ).strip(),
        "report_version": str(
            _pick(_as_dict(report.get("meta")), "version", default="5.0.0")
        ).strip()
        or "5.0.0",
        "cache_version": str(metadata.get("version") or "").strip(),
        "data_flow": str(metadata.get("dataFlow") or "").strip(),
        "doc_number": str(
            _pick(_as_dict(report.get("meta")), "doc_number", default="") or ""
        ).strip(),
        "case_name": str(
            _pick(_as_dict(report.get("meta")), "title_subject", default="") or ""
        ).strip(),
        "primary_subjects": core_persons,
        "companies": companies,
        "generator": str(
            _pick(_as_dict(report.get("meta")), "generator", default="") or ""
        ).strip(),
    }

    coverage = {
        "data_range": _extract_data_range(metadata),
        "persons_count": len(persons),
        "companies_count": len(company_entities),
        "families_count": len(families),
        "bank_transaction_count": total_transactions,
        "wallet_subject_count": wallet_subject_count,
        "wallet_transaction_count": wallet_transaction_count,
        "property_record_count": property_record_count,
        "vehicle_record_count": vehicle_record_count,
        "available_external_sources": available_external_sources,
        "missing_sources": missing_sources,
        "known_limitations": known_limitations,
    }

    return {
        "meta": meta,
        "coverage": coverage,
        "persons": persons,
        "companies": company_entities,
        "families": families,
        "aggregation_summary": aggregation_summary,
        "aggregation_highlights": aggregation_highlights,
        "suspicion_summary": _build_suspicion_summary(suspicions),
    }
