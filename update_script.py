import os

target_file = r'd:\CJ\project\report_generator.py'
new_content_file = r'd:\CJ\project\new_html_content.py'

# Read original file
with open(target_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the cutoff point
cutoff_index = -1
for i, line in enumerate(lines):
    if line.strip().startswith('def generate_html_report('):
        cutoff_index = i
        break

if cutoff_index == -1:
    print("Error: Could not find function definition in target file")
    exit(1)

# Keep lines up to cutoff
kept_lines = lines[:cutoff_index]

# Read new content
with open(new_content_file, 'r', encoding='utf-8') as f:
    new_lines = f.readlines()

# Find start of function in new file (skip imports)
start_index = -1
for i, line in enumerate(new_lines):
    if line.strip().startswith('def generate_html_report('):
        start_index = i
        break

if start_index == -1:
    print("Error: Could not find new function definition in new content file")
    exit(1)

new_func_lines = new_lines[start_index:]

# Concatenate
final_lines = kept_lines + new_func_lines

# Write back
with open(target_file, 'w', encoding='utf-8') as f:
    f.writelines(final_lines)

print("Success")
