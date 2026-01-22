
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import report_service

def test_report_generation():
    print("Loading ReportBuilder...")
    builder = report_service.load_report_builder('./output')
    if not builder:
        print("Failed to load ReportBuilder. Check output/analysis_cache.")
        return

    subjects = builder.get_available_subjects()
    print(f"Found {len(subjects)} subjects.")
    
    if not subjects:
        print("No subjects found.")
        return

    target = subjects[0]['name']
    print(f"Generating report for: {target}")



    # DEBUG: Inspect profile structure
    profile = builder.profiles.get(target, {})
    with open('debug_profile.txt', 'w', encoding='utf-8') as f:
        f.write(f"DEBUG: Profile Keys for {target}: {list(profile.keys())}\n")
        if 'summary' in profile:
            f.write(f"DEBUG: Summary Keys: {list(profile['summary'].keys())}\n")
        if 'assets' in profile:
            f.write(f"DEBUG: Assets Keys: {list(profile['assets'].keys())}\n")
    
    html = builder.generate_html_report([target], case_name="Test Case")
    
    # Verification
    checks = [
        "（二）资产状况", 
        "银行卡(张)", 
        "（三）异常资金分析",
        "疑似民间借贷",
        "异常来源收入"
    ]
    
    missing = []
    for check in checks:
        if check not in html:
            missing.append(check)
            
    if missing:
        print(f"FAILED: Missing key sections: {missing}")
        with open('debug_report.html', 'w', encoding='utf-8') as f:
            f.write(html)
    else:
        print("SUCCESS: All new sections found in the generated HTML.")
        print(f"Report length: {len(html)} chars")


if __name__ == "__main__":
    test_report_generation()
