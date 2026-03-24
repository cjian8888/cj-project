import re
import yaml
from typing import Dict


class PhraseLoader:
    def __init__(self, config_path: str = "config/report_phrases.yaml"):
        self.config_path = config_path
        self._config: Dict = {}

    def load_config(self) -> Dict:
        with open(self.config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f) or {}
        return self._config

    def get_phrase(self, category: str, scenario: str, level: str) -> Dict:
        if not self._config:
            self.load_config()
        cat = self._config.get(category, {})
        scen = cat.get(scenario, {})
        phrases = None
        for cond in scen.get("conditions", []):
            if cond.get("level") == level:
                phrases = cond.get("phrases")
                break
        return phrases or {}

    def render_phrase(self, phrase_template: str, variables: Dict) -> str:
        if not phrase_template:
            return ""

        # Safe eval environment
        safe_builtins = {
            'abs': abs,
            'min': min,
            'max': max,
            'round': round,
            'int': int,
            'float': float,
        }

        def _safe_eval(expr: str):
            try:
                return eval(expr, {"__builtins__": safe_builtins}, variables)
            except Exception:
                # Fallback to value from variables if available
                return variables.get(expr, "")

        # Replacement logic with support for format specs and simple expressions
        def _replace(match: re.Match) -> str:
            inner = match.group(1).strip()
            # support format spec: expr:spec
            if ":" in inner:
                expr_part, fmt = inner.split(":", 1)
                expr_part = expr_part.strip()
                fmt = fmt.strip()
                val = _safe_eval(expr_part)
                try:
                    return format(val, fmt)
                except Exception:
                    return str(val)
            else:
                expr_part = inner
                # Special-case: offset_wealth_excess followed by 立即万元 unit
                # If the placeholder is used with a trailing '万元', render in 万元 (y/万) units
                tail = phrase_template[match.end():]
                if expr_part == 'offset_wealth_excess' and '万元' in tail:
                    val = variables.get('offset_wealth_excess', 0)
                    wan = val / 10000.0
                    return f"{wan:.2f}"
                val = _safe_eval(expr_part)
                return "" if val is None else str(val)

        pattern = re.compile(r"\{([^{}]+)\}")
        result = pattern.sub(_replace, phrase_template)
        return result

    def render_with_calculation(self, phrase_template: str, data: Dict) -> str:
        return self.render_phrase(phrase_template, data)
