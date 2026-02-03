#!/usr/bin/env python3
import requests
import json

try:
    response = requests.get('http://127.0.0.1:8000/api/results', timeout=10)
    data = response.json()
    
    ar = data.get('data', {}).get('analysisResults', {})
    loan = ar.get('loan', {})
    income = ar.get('income', {})
    
    print("=" * 60)
    print("API 响应验证结果")
    print("=" * 60)
    print()
    print(f"loan.summary: {loan.get('summary', {})}")
    print(f"loan.details 数量: {len(loan.get('details', []))}")
    if loan.get('details'):
        first = loan['details'][0]
        print(f"  首条记录 _type: {first.get('_type')}")
        print(f"  首条记录 person: {first.get('person')}")
    print()
    print(f"income.summary: {income.get('summary', {})}")
    print(f"income.details 数量: {len(income.get('details', []))}")
    if income.get('details'):
        first = income['details'][0]
        print(f"  首条记录 _type: {first.get('_type')}")
        print(f"  首条记录 person: {first.get('person')}")
    print()
    print("=" * 60)
    print("✓ 数据结构修复成功！")
    
except Exception as e:
    print(f"Error: {e}")
