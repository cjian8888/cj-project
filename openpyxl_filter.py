"""
日志过滤器 - 过滤重复的openpyxl警告
"""

import logging

class OpenpyxlWarningFilter(logging.Filter):
    """过滤openpyxl的重复警告"""
    def __init__(self):
        super().__init__()
        self.last_warning_time = 0
        self.cooldown_seconds = 60  # 每分钟最多输出一次

    def filter(self, record):
        # 只过滤来自openpyxl的警告
        if 'openpyxl' in record.name and 'styles/stylesheet.py:237' in record.getMessage():
            import time
            current_time = time.time()
            if current_time - self.last_warning_time < self.cooldown_seconds:
                return False  # 过滤掉
            self.last_warning_time = current_time
        return True
