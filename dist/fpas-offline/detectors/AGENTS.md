# DETECTORS MODULE

## OVERVIEW
8个疑点检测器插件，继承 `BaseDetector` 抽象基类。

## STRUCTURE
```
detectors/
├── base_detector.py        # 抽象基类
├── cash_collision_detector.py    # 现金碰撞
├── direct_transfer_detector.py   # 直接转账
├── fixed_amount_detector.py      # 固定金额
├── fixed_frequency_detector.py   # 固定频率
├── frequency_anomaly_detector.py # 频率异常
├── round_amount_detector.py      # 整数金额
├── suspicious_pattern_detector.py # 可疑模式
└── time_anomaly_detector.py      # 时间异常
```

## WHERE TO LOOK

| 检测类型 | 文件 | 风险级别 |
|----------|------|----------|
| 现金碰撞 | cash_collision_detector.py | high |
| 直接转账 | direct_transfer_detector.py | high |
| 固定金额 | fixed_amount_detector.py | medium |
| 固定频率 | fixed_frequency_detector.py | medium |
| 频率异常 | frequency_anomaly_detector.py | medium |
| 整数金额 | round_amount_detector.py | low |
| 可疑模式 | suspicious_pattern_detector.py | high |
| 时间异常 | time_anomaly_detector.py | medium |

## CONVENTIONS

### 添加新检测器
```python
from detectors.base_detector import BaseDetector

class MyDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "my_detector"
    
    @property
    def description(self) -> str:
        return "检测描述"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # low/medium/high
    
    def detect(self, data: Dict, config: Dict) -> List[Dict]:
        # 实现检测逻辑
        return [{"id": "...", "score": 0.8, "metadata": {...}}]
```

### 必须注册
在 `__init__.py` 中添加导出。

## NOTES
- 所有检测器返回 `List[Dict]` 格式结果
- 配置从 `config.py` 传入
- 检测器可通过 `enabled` 属性禁用
