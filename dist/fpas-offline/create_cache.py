import json
import os

os.makedirs('output/analysis_cache', exist_ok=True)
    print("Creating cache directory...")
cache_dir = 'output/analysis_cache'
profiles = {'张三': {'totalIncome': 100000}}
metadata = {'persons': ['张三'], 'companies': []}
with open(os.path.join(cache_dir, 'profiles.json'), 'w', encoding='utf-8') as f:
    json.dump(profiles, ensure_ascii=False)
    f.write(json.dumps(profile, indent=4))
with open(os.path.join(cache_dir, 'metadata.json'), 'w', encoding='utf-8') as f:
    json.dump(metadata, ensure_ascii=False)
    f.write(json.dumps(metadata, indent=4))
print("Cache files created successfully!")
