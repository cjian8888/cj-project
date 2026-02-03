#!/usr/bin/env python3
"""展示 report_v4.json 的结构"""
import json

def show_structure(obj, indent=0, max_depth=4, max_items=5):
    """递归展示 JSON 结构"""
    result = []
    prefix = "  " * indent
    
    if indent >= max_depth:
        return ["..."]
    
    if isinstance(obj, dict):
        items = list(obj.items())
        for i, (k, v) in enumerate(items):
            if i >= max_items:
                result.append(f"{prefix}... ({len(items) - max_items} more keys)")
                break
            if isinstance(v, dict):
                result.append(f"{prefix}{k}: {{}} ({len(v)} keys)")
                result.extend(show_structure(v, indent + 1, max_depth, max_items))
            elif isinstance(v, list):
                result.append(f"{prefix}{k}: [] ({len(v)} items)")
                if len(v) > 0:
                    result.extend(show_structure(v[0], indent + 1, max_depth, max_items))
            else:
                vstr = str(v)[:40] + "..." if len(str(v)) > 40 else str(v)
                result.append(f"{prefix}{k}: {vstr}")
    elif isinstance(obj, list):
        if len(obj) > 0:
            result.append(f"{prefix}[0]:")
            result.extend(show_structure(obj[0], indent + 1, max_depth, max_items))
    
    return result

with open("output/report_v4.json", "r", encoding="utf-8") as f:
    report = json.load(f)

print("=" * 60)
print("report_v4.json 结构概览")
print("=" * 60)
print("\n".join(show_structure(report)))
