import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from family_analyzer import infer_extended_relatives


def test_redundant_parent_inference():
    """已知存在父亲时，不应再把叔辈误推断为父母。"""
    father = {
        "姓名": "施灵",
        "身份证号": "31010219650409xxxx",
        "出生日期": "19650409",
        "籍贯": "上海市崇明县",
        "与户主关系": "户主",
    }
    son = {
        "姓名": "施承天",
        "身份证号": "31011519930619xxxx",
        "出生日期": "19930619",
        "籍贯": "上海市崇明县",
        "与户主关系": "子",
    }
    uncle = {
        "姓名": "施育",
        "身份证号": "31023019620814xxxx",
        "出生日期": "19620814",
        "籍贯": "上海市崇明县",
        "与户主关系": "户主",
    }

    family_tree = {
        "施灵": [father, son],
        "施承天": [father, son],
        "施育": [uncle],
    }

    relations = infer_extended_relatives([father, son, uncle], family_tree=family_tree)

    relation_to_son = [
        relation
        for relation in relations
        if {relation["person_a"], relation["person_b"]} == {"施育", "施承天"}
    ]

    assert relation_to_son, "应至少推断出施育与施承天之间存在某种亲属关系"
    assert all("父/母" not in relation["relation"] for relation in relation_to_son)
    assert any("长辈" in relation["relation"] for relation in relation_to_son)
