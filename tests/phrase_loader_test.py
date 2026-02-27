import os
import json
from utils.phrase_loader import PhraseLoader

def test_historical_redemption_high_risk_rendering():
    loader = PhraseLoader("config/report_phrases.yaml")
    loader.load_config()
    phrase = loader.get_phrase("income_analysis", "historical_redemption", "high_risk")

    test_data = {
        "name": "测试人员",
        "salary_ratio": 39.9,
        "real_income_wan": 1600.84,
        "offset_wealth_excess": 6053900,
        "adjusted_income_wan": 995.45,
        "adjusted_ratio": 64.2
    }

    template = phrase.get("summary", "")
    rendered = loader.render_with_calculation(template, test_data)
    assert rendered == "⚠️ 发现大额历史存量赎回605.39万元，严重虚增当期收入"
