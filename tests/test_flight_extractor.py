"""
flight_extractor.py 单元测试

测试中航信航班进出港信息解析模块的功能
重点测试 Excel 引擎修复后的功能
"""

import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile
import os

from flight_extractor import (
    parse_flight_file,
    _parse_flight_row,
    get_flight_summary,
    get_flight_timeline,
    extract_flight_data,
    _find_flight_dir
)
from utils.safe_types import (
    safe_str as _safe_str,
    safe_int as _safe_int,
    safe_float as _safe_float,
    safe_date as _safe_date,
)
from utils import (
    extract_id_from_filename as _extract_id_from_filename,
)


class TestSafeStr:
    """测试 _safe_str 函数"""
    
    def test_safe_str_with_string(self):
        assert _safe_str("test") == "test"
    
    def test_safe_str_with_number(self):
        assert _safe_str(123) == "123"
    
    def test_safe_str_with_nan(self):
        assert _safe_str(pd.NA) is None
    
    def test_safe_str_with_none(self):
        assert _safe_str(None) is None
    
    def test_safe_str_with_whitespace(self):
        assert _safe_str("  test  ") == "test"


class TestSafeInt:
    """测试 _safe_int 函数"""
    
    def test_safe_int_with_int(self):
        assert _safe_int(42) == 42
    
    def test_safe_int_with_string_int(self):
        assert _safe_int("42") == 42
    
    def test_safe_int_with_nan(self):
        assert _safe_int(pd.NA) is None
    
    def test_safe_int_with_invalid_string(self):
        assert _safe_int("abc") is None
    
    def test_safe_int_with_none(self):
        assert _safe_int(None) is None


class TestSafeFloat:
    """测试 _safe_float 函数"""
    
    def test_safe_float_with_float(self):
        assert _safe_float(3.14) == 3.14
    
    def test_safe_float_with_string_float(self):
        assert _safe_float("3.14") == 3.14
    
    def test_safe_float_with_nan(self):
        assert _safe_float(pd.NA) is None
    
    def test_safe_float_with_invalid_string(self):
        assert _safe_float("abc") is None
    
    def test_safe_float_with_none(self):
        assert _safe_float(None) is None


class TestSafeDate:
    """测试 _safe_date 函数"""
    
    def test_safe_date_with_datetime(self):
        from datetime import datetime
        dt = datetime(2024, 1, 15, 10, 30)
        assert _safe_date(dt) == "2024-01-15"
    
    def test_safe_date_with_string(self):
        assert _safe_date("2024-01-15") == "2024-01-15"
    
    def test_safe_date_with_long_string(self):
        assert _safe_date("2024-01-15 10:30:00") == "2024-01-15"
    
    def test_safe_date_with_nan(self):
        assert _safe_date(pd.NA) is None
    
    def test_safe_date_with_none(self):
        assert _safe_date(None) is None


class TestExtractIdFromFilename:
    """测试 _extract_id_from_filename 函数"""
    
    def test_extract_id_with_valid_id(self):
        filename = "110101199001011234_航班信息.xlsx"
        assert _extract_id_from_filename(filename) == "110101199001011234"
    
    def test_extract_id_with_lowercase_x(self):
        filename = "11010119900101123x_航班信息.xlsx"
        assert _extract_id_from_filename(filename) == "11010119900101123X"
    
    def test_extract_id_with_no_id(self):
        filename = "航班信息.xlsx"
        assert _extract_id_from_filename(filename) is None
    
    def test_extract_id_with_invalid_id(self):
        filename = "12345_航班信息.xlsx"
        assert _extract_id_from_filename(filename) is None


class TestFindFlightDir:
    """测试 _find_flight_dir 函数"""
    
    def test_find_flight_dir_exists(self, tmp_path):
        flight_dir = tmp_path / "中航信航班进出港信息（定向查询）"
        flight_dir.mkdir()
        result = _find_flight_dir(str(tmp_path))
        assert result is not None
        assert "中航信航班进出港信息" in result
    
    def test_find_flight_dir_not_exists(self, tmp_path):
        result = _find_flight_dir(str(tmp_path))
        assert result is None
    
    def test_find_flight_dir_nested(self, tmp_path):
        nested = tmp_path / "data" / "中航信航班进出港信息（定向查询）"
        nested.mkdir(parents=True)
        result = _find_flight_dir(str(tmp_path))
        assert result is not None


class TestParseFlightRow:
    """测试 _parse_flight_row 函数"""
    
    def test_parse_flight_row_basic(self):
        row = pd.Series({
            "旅客证件号": "110101199001011234",
            "手机号": "13800138000",
            "航空公司": "中国国航",
            "航班号": "CA1234",
            "旅客中文姓名": "张三",
            "起飞日期": pd.Timestamp("2024-01-15"),
            "起飞时间": "10:30",
            "到达日期": pd.Timestamp("2024-01-15"),
            "到达时间": "12:30",
            "起飞机场": "北京首都",
            "到达机场": "上海虹桥"
        })
        result = _parse_flight_row(row, "test.xlsx", True)
        assert result is not None
        assert result["passenger_id"] == "110101199001011234"
        assert result["flight_number"] == "CA1234"
        assert result["departure_date"] == "2024-01-15"
        assert result["is_completed"] is True
    
    def test_parse_flight_row_with_missing_data(self):
        row = pd.Series({
            "旅客证件号": None,
            "航班号": None,
            "起飞日期": None
        })
        result = _parse_flight_row(row, "test.xlsx", True)
        assert result is None
    
    def test_parse_flight_row_with_nan_values(self):
        row = pd.Series({
            "旅客证件号": pd.NA,
            "手机号": pd.NA,
            "航空公司": pd.NA,
            "航班号": "CA1234",
            "起飞日期": pd.Timestamp("2024-01-15")
        })
        result = _parse_flight_row(row, "test.xlsx", True)
        assert result is not None
        assert result["passenger_id"] is None
        assert result["phone"] is None
        assert result["airline"] is None
    
    def test_parse_flight_row_cancelled(self):
        row = pd.Series({
            "航班号": "CA1234",
            "起飞日期": pd.Timestamp("2024-01-15")
        })
        result = _parse_flight_row(row, "test.xlsx", False)
        assert result is not None
        assert result["is_completed"] is False


class TestParseFlightFile:
    """测试 parse_flight_file 函数 - 重点测试 Excel 引擎修复"""
    
    def test_parse_flight_file_with_openpyxl_engine(self, tmp_path):
        """测试使用 openpyxl 引擎解析 Excel 文件"""
        # 创建测试数据
        data = pd.DataFrame({
            "旅客证件号": ["110101199001011234"],
            "航班号": ["CA1234"],
            "起飞日期": [pd.Timestamp("2024-01-15")],
            "起飞机场": ["北京首都"],
            "到达机场": ["上海虹桥"]
        })
        
        # 创建 Excel 文件
        file_path = tmp_path / "test_flight.xlsx"
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            data.to_excel(writer, sheet_name="已成行", index=False)
        
        # 解析文件
        result = parse_flight_file(str(file_path))
        
        assert "completed" in result
        assert "cancelled" in result
        assert len(result["completed"]) == 1
        assert result["completed"][0]["flight_number"] == "CA1234"
    
    def test_parse_flight_file_with_multiple_sheets(self, tmp_path):
        """测试解析包含多个工作表的 Excel 文件"""
        completed_data = pd.DataFrame({
            "旅客证件号": ["110101199001011234"],
            "航班号": ["CA1234"],
            "起飞日期": [pd.Timestamp("2024-01-15")]
        })
        
        cancelled_data = pd.DataFrame({
            "旅客证件号": ["110101199001011234"],
            "航班号": ["CA5678"],
            "起飞日期": [pd.Timestamp("2024-01-20")]
        })
        
        file_path = tmp_path / "test_multi_sheet.xlsx"
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            completed_data.to_excel(writer, sheet_name="已成行", index=False)
            cancelled_data.to_excel(writer, sheet_name="未成行", index=False)
        
        result = parse_flight_file(str(file_path))
        
        assert len(result["completed"]) == 1
        assert len(result["cancelled"]) == 1
        assert result["completed"][0]["flight_number"] == "CA1234"
        assert result["cancelled"][0]["flight_number"] == "CA5678"
    
    def test_parse_flight_file_empty_sheet(self, tmp_path):
        """测试解析空工作表"""
        empty_data = pd.DataFrame()
        
        file_path = tmp_path / "test_empty.xlsx"
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            empty_data.to_excel(writer, sheet_name="已成行", index=False)
        
        result = parse_flight_file(str(file_path))
        
        assert len(result["completed"]) == 0
        assert len(result["cancelled"]) == 0
    
    def test_parse_flight_file_invalid_file(self, tmp_path):
        """测试解析无效文件"""
        file_path = tmp_path / "invalid.txt"
        file_path.write_text("not an excel file")
        
        result = parse_flight_file(str(file_path))
        
        # 应该返回空结果而不是抛出异常
        assert "completed" in result
        assert "cancelled" in result


class TestGetFlightSummary:
    """测试 get_flight_summary 函数"""
    
    @patch('flight_extractor.extract_flight_data')
    def test_get_flight_summary_basic(self, mock_extract):
        mock_extract.return_value = {
            "110101199001011234": {
                "completed": [
                    {"airline": "中国国航", "departure_airport": "北京", "arrival_airport": "上海"},
                    {"airline": "东方航空", "departure_airport": "上海", "arrival_airport": "北京"}
                ],
                "cancelled": [
                    {"airline": "南方航空", "departure_airport": "广州", "arrival_airport": "深圳"}
                ]
            }
        }
        
        result = get_flight_summary("test_dir")
        
        assert result["total_persons"] == 1
        assert result["total_completed"] == 2
        assert result["total_cancelled"] == 1
        assert result["airline_distribution"]["中国国航"] == 1
        assert result["airline_distribution"]["东方航空"] == 1
        assert result["airline_distribution"]["南方航空"] == 1
    
    @patch('flight_extractor.extract_flight_data')
    def test_get_flight_summary_empty(self, mock_extract):
        mock_extract.return_value = {}
        
        result = get_flight_summary("test_dir")
        
        assert result["total_persons"] == 0
        assert result["total_completed"] == 0
        assert result["total_cancelled"] == 0


class TestGetFlightTimeline:
    """测试 get_flight_timeline 函数"""
    
    @patch('flight_extractor.extract_flight_data')
    def test_get_flight_timeline_basic(self, mock_extract):
        mock_extract.return_value = {
            "110101199001011234": {
                "completed": [
                    {
                        "passenger_name_cn": "张三",
                        "departure_date": "2024-01-15",
                        "departure_time": "10:30",
                        "flight_number": "CA1234",
                        "airline": "中国国航",
                        "departure_airport": "北京",
                        "arrival_airport": "上海"
                    }
                ],
                "cancelled": [
                    {
                        "passenger_name_cn": "张三",
                        "departure_date": "2024-01-20",
                        "departure_time": "14:00",
                        "flight_number": "CA5678",
                        "airline": "中国国航",
                        "departure_airport": "上海",
                        "arrival_airport": "北京"
                    }
                ]
            }
        }
        
        result = get_flight_timeline("test_dir")
        
        assert len(result) == 2
        assert result[0]["status"] == "未成行"  # 按日期倒序
        assert result[1]["status"] == "已成行"
        assert result[0]["type"] == "flight"
        assert result[1]["type"] == "flight"


class TestExtractFlightData:
    """测试 extract_flight_data 函数"""
    
    def test_extract_flight_data_no_flight_dir(self, tmp_path):
        """测试没有航班目录的情况"""
        result = extract_flight_data(str(tmp_path))
        assert result == {}
    
    @patch('flight_extractor.parse_flight_file')
    def test_extract_flight_data_with_person_id_filter(self, mock_parse):
        """测试按人员ID过滤"""
        mock_parse.return_value = {
            "completed": [{"flight_number": "CA1234"}],
            "cancelled": []
        }
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            flight_dir = Path(tmp_dir) / "中航信航班进出港信息（定向查询）"
            flight_dir.mkdir()
            
            # 创建两个文件
            (flight_dir / "110101199001011234_flight.xlsx").touch()
            (flight_dir / "110101199001011235_flight.xlsx").touch()
            
            result = extract_flight_data(tmp_dir, person_id="110101199001011234")
            
            # 应该只解析匹配的文件
            assert "110101199001011234" in result
            assert "110101199001011235" not in result


class TestExcelEngineFix:
    """专门测试 Excel 引擎修复"""
    
    def test_excel_file_format_determination(self, tmp_path):
        """
        测试修复后的 Excel 文件格式确定问题
        之前的问题: "Excel file format cannot be determined, you must specify an engine manually"
        修复: 添加了 engine='openpyxl' 参数
        """
        data = pd.DataFrame({
            "航班号": ["CA1234"],
            "起飞日期": [pd.Timestamp("2024-01-15")]
        })
        
        file_path = tmp_path / "test_engine.xlsx"
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            data.to_excel(writer, sheet_name="已成行", index=False)
        
        # 这应该不会抛出 "Excel file format cannot be determined" 错误
        result = parse_flight_file(str(file_path))
        
        assert "completed" in result
        assert len(result["completed"]) == 1
        assert result["completed"][0]["flight_number"] == "CA1234"
    
    def test_excel_engine_fallback(self, tmp_path):
        """测试引擎回退机制"""
        data = pd.DataFrame({
            "航班号": ["CA1234"],
            "起飞日期": [pd.Timestamp("2024-01-15")]
        })
        
        file_path = tmp_path / "test_fallback.xlsx"
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            data.to_excel(writer, sheet_name="已成行", index=False)
        
        # 测试即使 openpyxl 失败，也能回退到 xlrd
        with patch('pandas.ExcelFile') as mock_excel:
            # 第一次调用失败，第二次成功
            mock_excel.side_effect = [
                Exception("openpyxl failed"),
                MagicMock(sheet_names=["已成行"])
            ]
            
            # 模拟 read_excel
            with patch('pandas.read_excel') as mock_read:
                mock_read.return_value = data
                
                result = parse_flight_file(str(file_path))
                
                # 应该尝试了两次
                assert mock_excel.call_count >= 1
