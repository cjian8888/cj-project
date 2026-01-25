import sys
import os
import unittest
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from family_analyzer import infer_extended_relatives

class TestFamilyInference(unittest.TestCase):
    def test_redundant_parent_inference(self):
        """
        Test that an Uncle is not inferred as a Parent when a real Parent is already known.
        
        Scenario:
        - Shi Ling (Male, born 1965) -> Father of Shi Chengtian
        - Shi Chengtian (Male, born 1993) -> Son of Shi Ling
        - Shi Yu (Male, born 1962) -> Older than Shi Ling (Uncle)
        
        Current (Flawed) Behavior:
        - Shi Yu is inferred as "Possible Parent" of Shi Chengtian due to age diff (31 years) and same surname/origin.
        
        Desired Behavior:
        - Shi Yu should NOT be inferred as Parent because Shi Chengtian already has a known father (Shi Ling) in the same household/audit context.
        - Shi Yu might be inferred as an Uncle (Father's Sibling).
        """
        
        # 1. Setup Data
        # Shi Ling (Father)
        p_father = {
            '姓名': '施灵',
            '身份证号': '31010219650409xxxx', # 1965
            '出生日期': '19650409',
            '籍贯': '上海市崇明县',
            '与户主关系': '户主'
        }
        
        # Shi Chengtian (Son)
        p_son = {
            '姓名': '施承天',
            '身份证号': '31011519930619xxxx', # 1993 (Diff from Father: 28 years)
            '出生日期': '19930619',
            '籍贯': '上海市崇明县',
            '与户主关系': '子'
        }
        
        # Shi Yu (Uncle - Father's Brother)
        p_uncle = {
            '姓名': '施育',
            '身份证号': '31023019620814xxxx', # 1962 (Diff from Son: 31 years)
            '出生日期': '19620814',
            '籍贯': '上海市崇明县',
            '与户主关系': '户主' # In his own household
        }
        
        all_persons = [p_father, p_son, p_uncle]
        
        # 2. Setup Known Relations (Family Tree context)
        # This simulates that we already know Shi Ling is Shi Chengtian's father from household data
        family_tree = {
            '施灵': [p_father, p_son], # Shi Ling's household has Son
            '施承天': [p_father, p_son], # Redundant lookup, but logical
            '施育': [p_uncle]          # Shi Yu is in separate household
        }
        
        # 3. Run Inference BEFORE Fix (or blindly)
        # We expect the fix to require passing `family_tree` or `known_relations`
        # For now, let's call the function. If we haven't changed the signature yet, it won't take family_tree.
        # So this test serves as a design guide.
        
        # NOTE: The current function signature is infer_extended_relatives(persons_info)
        # We will modify it to infer_extended_relatives(persons_info, family_tree)
        
        try:
            # Try calling with new signature (simulating future state)
            relations = infer_extended_relatives(all_persons, family_tree=family_tree)
        except TypeError:
            # Fallback to old signature for baseline
            relations = infer_extended_relatives(all_persons)
            
        print("\n--- Inferred Relations ---")
        found_bad_inference = False
        for r in relations:
            print(f"{r['person_a']} <-> {r['person_b']}: {r['relation']}")
            
            # Check for Bad Inference: Shi Yu -> Parent of Shi Chengtian
            if (r['person_a'] == '施育' and r['person_b'] == '施承天') or \
               (r['person_b'] == '施育' and r['person_a'] == '施承天'):
                if '父/母' in r['relation']:
                    found_bad_inference = True
                    
        return found_bad_inference

if __name__ == '__main__':
    t = TestFamilyInference()
    is_bad = t.test_redundant_parent_inference()
    if is_bad:
        print("\n[FAIL] Found redundant/incorrect parent inference (Uncle inferred as Parent).")
    else:
        print("\n[PASS] No redundant parent inference found.")
