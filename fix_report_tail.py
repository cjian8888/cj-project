
import os

path = 'd:/CJ/project/report_generator.py'

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
found_target = False

for i, line in enumerate(lines):
    new_lines.append(line)
    # 查找特定结束行 (带有一些空格容错)
    if 'return text_lines' in line:
        # 确认这是我们要找的那个 _analyze_person_asset_trails 的结尾
        # 通过上下文判断：下一行应该是乱码或缩进错误的 total_suspicions
        if i + 1 < len(lines):
            next_line = lines[i+1].strip()
            if next_line.startswith('sum(') or 'total_suspicions' in next_line or next_line == ')':
                print(f"Found cut point at line {i+1}")
                found_target = True
                break

if found_target:
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print("File truncated successfully.")
else:
    print("Detailed cut point not found. Checking for absolute line number...")
    # Fallback: Just cut at line 933 if content matches
    if len(lines) >= 933 and 'return text_lines' in lines[932]:
         with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines[:933])
         print("Fallback truncation at line 933 applied.")
    else:
        print("Could not fix file.")
