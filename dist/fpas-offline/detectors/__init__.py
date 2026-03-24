"""疑点检测引擎 - 8个检测器插件"""
from detectors.base_detector import BaseDetector
from detectors.cash_collision_detector import CashCollisionDetector
from detectors.direct_transfer_detector import DirectTransferDetector
from detectors.fixed_amount_detector import FixedAmountDetector
from detectors.fixed_frequency_detector import FixedFrequencyDetector
from detectors.frequency_anomaly_detector import FrequencyAnomalyDetector
from detectors.round_amount_detector import RoundAmountDetector
from detectors.suspicious_pattern_detector import SuspiciousPatternDetector
from detectors.time_anomaly_detector import TimeAnomalyDetector

__all__ = [
    'BaseDetector',
    'CashCollisionDetector', 
    'DirectTransferDetector',
    'FixedAmountDetector',
    'FixedFrequencyDetector',
    'FrequencyAnomalyDetector',
    'RoundAmountDetector',
    'SuspiciousPatternDetector',
    'TimeAnomalyDetector'
]