#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一缓存管理器 - CacheManager

功能：
1. 统一管理所有缓存文件的保存和读取
2. 维护缓存版本号和时间戳
3. 提供缓存验证机制
4. 支持按需失效和批量清除
5. 确保缓存一致性

使用示例：
    cache_mgr = CacheManager(cache_dir)
    cache_mgr.save_results(results)
    cache = cache_mgr.load_results()
    cache_mgr.invalidate(module="profiles")
"""

import json
import os
import logging
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class CacheManager:
    """
    统一缓存管理器

    管理分析缓存的生命周期，确保数据一致性。
    """

    # 缓存文件名称定义
    # 【2026-02-12 改进】移除 profiles_full，现在统一使用 profiles.json
    CACHE_FILES = {
        "profiles": "profiles.json",
        "suspicions": "suspicions.json",
        "derived_data": "derived_data.json",
        "graph_data": "graph_data.json",
        "metadata": "metadata.json",
        "analysis_results": "analysis_results.json",
        # 外部数据源缓存
        "vehicleData": "vehicleData.json",
        "precisePropertyData": "precisePropertyData.json",
        "wealthProductData": "wealthProductData.json",
        "securitiesData": "securitiesData.json",
        "bankAccountInfo": "bankAccountInfo.json",
        "taxData": "taxData.json",
        "creditData": "creditData.json",
        "amlData": "amlData.json",
        "insuranceData": "insuranceData.json",
        "immigrationData": "immigrationData.json",
        "hotelData": "hotelData.json",
        "hotelCohabitation": "hotelCohabitation.json",
        "railwayData": "railwayData.json",
        "flightData": "flightData.json",
        "coaddressData": "coaddressData.json",
        "coviolationData": "coviolationData.json",
        "walletData": "walletData.json",
        "external_p0": "external_p0.json",
        "external_p1": "external_p1.json",
        "external_p2": "external_p2.json",
    }

    # 当前缓存格式版本
    CACHE_VERSION = "4.0.0"

    def __init__(self, cache_dir: str):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径
        """
        self.cache_dir = Path(cache_dir)
        self.logger = logging.getLogger(__name__)

        # 确保缓存目录存在
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.logger.info(f"[缓存管理器] 初始化完成，目录: {self.cache_dir}")

    def get_cache_path(self, cache_name: str) -> Path:
        """
        获取指定缓存文件的路径

        Args:
            cache_name: 缓存名称（如 'profiles'）

        Returns:
            缓存文件的完整路径

        Raises:
            ValueError: 缓存名称未知
        """
        if cache_name not in self.CACHE_FILES:
            raise ValueError(f"未知的缓存名称: {cache_name}")
        return self.cache_dir / self.CACHE_FILES[cache_name]

    def is_cache_valid(
        self, cache_name: str, max_age_hours: Optional[int] = None
    ) -> bool:
        """
        检查缓存文件是否存在且有效

        Args:
            cache_name: 缓存名称
            max_age_hours: 最大缓存年龄（小时），None 表示不检查时间

        Returns:
            缓存是否有效
        """
        cache_path = self.get_cache_path(cache_name)

        # 检查文件是否存在
        if not cache_path.exists():
            self.logger.debug(f"[缓存验证] {cache_name} 不存在")
            return False

        # 检查缓存版本
        if cache_name == "metadata":
            # metadata.json 包含版本信息
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                    cache_version = metadata.get("version", "")

                # 版本必须匹配
                if cache_version != self.CACHE_VERSION:
                    self.logger.warning(
                        f"[缓存验证] {cache_name} 版本不匹配: {cache_version} (期望: {self.CACHE_VERSION})"
                    )
                    return False
            except Exception as e:
                self.logger.warning(f"[缓存验证] {cache_name} 读取失败: {e}")
                return False

        # 检查缓存年龄
        if max_age_hours is not None:
            cache_age = datetime.now() - datetime.fromtimestamp(
                cache_path.stat().st_mtime
            )
            if cache_age.total_seconds() > max_age_hours * 3600:
                self.logger.warning(
                    f"[缓存验证] {cache_name} 已过期 (年龄: {cache_age})"
                )
                return False

        self.logger.debug(f"[缓存验证] {cache_name} 有效")
        return True

    def invalidate(self, cache_name: Optional[str] = None):
        """
        失效指定的缓存文件

        Args:
            cache_name: 缓存名称，None 表示失效所有缓存
        """
        if cache_name is None:
            # 清除所有缓存
            self.clear_all()
        else:
            cache_path = self.get_cache_path(cache_name)
            if cache_path.exists():
                os.remove(cache_path)
                self.logger.info(f"[缓存失效] 已删除: {cache_name}")

    def clear_all(self):
        """清除所有缓存文件"""
        for cache_file in self.cache_dir.iterdir():
            if cache_file.is_file():
                os.remove(cache_file)
                self.logger.info(f"[缓存清除] 已删除: {cache_file.name}")

    def save_cache(self, cache_name: str, data: Any):
        """
        保存缓存数据

        Args:
            cache_name: 缓存名称
            data: 要保存的数据（可以是字典、列表等）
        """
        cache_path = self.get_cache_path(cache_name)

        if data is None:
            if cache_path.exists():
                os.remove(cache_path)
                self.logger.info(f"[缓存保存] {cache_name} 数据为空，已删除旧缓存")
            else:
                self.logger.warning(f"[缓存保存] {cache_name} 数据为空，跳过保存")
            return

        serialized = json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
            cls=CustomJSONEncoder,
        )
        temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(serialized)
            os.replace(temp_path, cache_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass

        self.logger.info(
            f"[缓存保存] {cache_name} -> {cache_path.name} ({len(str(data))} 字符)"
        )

    def load_cache(self, cache_name: str) -> Optional[Dict]:
        """
        加载缓存数据

        Args:
            cache_name: 缓存名称

        Returns:
            缓存数据，如果不存在或无效则返回 None
        """
        if not self.is_cache_valid(cache_name):
            return None

        cache_path = self.get_cache_path(cache_name)

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.logger.info(f"[缓存加载] {cache_name} <- {cache_path.name}")
            return data
        except Exception as e:
            self.logger.error(f"[缓存加载] {cache_name} 失败: {e}")
            return None

    def save_metadata(self, metadata: Dict):
        """
        保存元数据（包含版本号和生成时间）

        Args:
            metadata: 元数据字典
        """
        # 添加版本号和时间戳
        metadata["version"] = self.CACHE_VERSION
        metadata["generatedAt"] = datetime.now().isoformat()
        metadata["cacheManagerVersion"] = "4.0.0"

        self.save_cache("metadata", metadata)

    def save_results(self, results: Dict, id_to_name_map: Dict = None):
        """
        保存完整的分析结果到缓存

        Args:
            results: 分析结果字典
            id_to_name_map: 身份证号到人名的映射（可选）
        """
        # 保存各个模块的缓存
        if "profiles" in results:
            self.save_cache("profiles", results["profiles"])

        # 【2026-02-12 改进】不再单独保存 profiles_full.json
        # 因为 profiles.json 现在已包含完整数据
        # if "_profiles_raw" in results:
        #     self.save_cache("profiles_full", results["_profiles_raw"])

        if "suspicions" in results:
            self.save_cache("suspicions", results["suspicions"])

        if "analysisResults" in results:
            self.save_cache("derived_data", results["analysisResults"])

        if "graphData" in results:
            self.save_cache("graph_data", results["graphData"])

        if "walletData" in results:
            self.save_cache("walletData", results["walletData"])

        # 【修复】保存外部数据（P0和P1）
        if "externalData" in results:
            external_data = results["externalData"]

            # P0 外部数据
            if "p0" in external_data:
                p0_data = external_data["p0"]
                self.save_cache("external_p0", p0_data)

                # 提取并保存单独的文件以便 InvestigationReportBuilder 使用
                if "credit_data" in p0_data:
                    self.save_cache("creditData", p0_data["credit_data"])
                if "aml_data" in p0_data:
                    self.save_cache("amlData", p0_data["aml_data"])

            # P1 外部数据
            if "p1" in external_data:
                p1_data = external_data["p1"]
                self.save_cache("external_p1", p1_data)

                # 提取并保存单独的文件以便 InvestigationReportBuilder 使用
                if "vehicle_data" in p1_data:
                    self.save_cache("vehicleData", p1_data["vehicle_data"])
                if "wealth_product_data" in p1_data:
                    self.save_cache("wealthProductData", p1_data["wealth_product_data"])
                if "securities_data" in p1_data:
                    self.save_cache("securitiesData", p1_data["securities_data"])
                # 【修复】保存房产数据（P1层）
                if "precise_property_data" in p1_data:
                    self.save_cache("precisePropertyData", p1_data["precise_property_data"])

            # P2 外部数据
            if "p2" in external_data:
                p2_data = external_data["p2"]
                self.save_cache("external_p2", p2_data)

                if "insurance_data" in p2_data:
                    self.save_cache("insuranceData", p2_data["insurance_data"])
                if "immigration_data" in p2_data:
                    self.save_cache("immigrationData", p2_data["immigration_data"])
                if "hotel_data" in p2_data:
                    self.save_cache("hotelData", p2_data["hotel_data"])
                if "hotel_cohabitation" in p2_data:
                    self.save_cache("hotelCohabitation", p2_data["hotel_cohabitation"])
                if "railway_data" in p2_data:
                    self.save_cache("railwayData", p2_data["railway_data"])
                if "flight_data" in p2_data:
                    self.save_cache("flightData", p2_data["flight_data"])
                if "coaddress_data" in p2_data:
                    self.save_cache("coaddressData", p2_data["coaddress_data"])
                if "coviolation_data" in p2_data:
                    self.save_cache("coviolationData", p2_data["coviolation_data"])

        # 保存元数据
        metadata = {
            "persons": results.get("persons", []),
            "companies": results.get("companies", []),
            "version": self.CACHE_VERSION,
            "generatedAt": datetime.now().isoformat(),
            "refactored": True,
            "dataFlow": "external_data_first",
            # 【修复】添加身份证号到人名的映射
            "id_to_name_map": id_to_name_map or {},
            "runtimeLogPaths": results.get("runtimeLogPaths", {}),
        }
        self.save_metadata(metadata)


        self.logger.info("[缓存管理] 所有缓存已保存")

    def load_results(self) -> Optional[Dict]:
        """
        加载完整的分析结果

        Returns:
            分析结果字典，如果缓存无效则返回 None
        """
        # 先验证元数据
        metadata = self.load_cache("metadata")
        if metadata is None:
            self.logger.warning("[缓存加载] 元数据无效，放弃加载")
            return None

        # 加载各个模块
        # 【2026-02-12 改进】profiles_full 不再是必需的，因为 profiles 已包含完整数据
        profiles = self.load_cache("profiles")
        if profiles is None:
            self.logger.warning("[缓存加载] profiles 加载失败")
            return None
            
        wallet_data = self.load_cache("walletData")
        external_p0 = self.load_cache("external_p0")
        external_p1 = self.load_cache("external_p1")
        external_p2 = self.load_cache("external_p2")

        results = {
            "profiles": profiles,
            "_profiles_raw": None,  # 不再使用
            "suspicions": self.load_cache("suspicions"),
            "analysisResults": self.load_cache("derived_data"),
            "graphData": self.load_cache("graph_data"),
            # 【修复】从元数据中提取 persons 和 companies
            "persons": metadata.get("persons", []),
            "companies": metadata.get("companies", []),
            # 【修复】加载外部数据缓存（供InvestigationReportBuilder使用）
            "precisePropertyData": self.load_cache("precisePropertyData"),
            "vehicleData": self.load_cache("vehicleData"),
            "wealthProductData": self.load_cache("wealthProductData"),
            "securitiesData": self.load_cache("securitiesData"),
            "creditData": self.load_cache("creditData"),
            "amlData": self.load_cache("amlData"),
            "insuranceData": self.load_cache("insuranceData"),
            "immigrationData": self.load_cache("immigrationData"),
            "hotelData": self.load_cache("hotelData"),
            "hotelCohabitation": self.load_cache("hotelCohabitation"),
            "railwayData": self.load_cache("railwayData"),
            "flightData": self.load_cache("flightData"),
            "coaddressData": self.load_cache("coaddressData"),
            "coviolationData": self.load_cache("coviolationData"),
            "walletData": wallet_data,
            "external_p0": external_p0,
            "external_p1": external_p1,
            "external_p2": external_p2,
            "externalData": {
                "p0": external_p0 or {},
                "p1": external_p1 or {},
                "p2": external_p2 or {},
                "wallet": wallet_data or {},
            },
            "runtimeLogPaths": metadata.get("runtimeLogPaths", {}),
        }
        # 检查必需缓存（profiles_full 不再是必需的）
        required_caches = ["profiles", "suspicions", "analysisResults", "graphData"]
        if all(results[k] is not None for k in required_caches):
            self.logger.info("[缓存加载] 所有必需缓存加载成功")
            return results
        else:
            self.logger.warning("[缓存加载] 部分必需缓存加载失败")
            return None

    def get_cache_info(self) -> Dict:
        """
        获取缓存信息（用于调试和监控）

        Returns:
            缓存信息字典
        """
        cache_info = {
            "cacheDir": str(self.cache_dir),
            "cacheVersion": self.CACHE_VERSION,
            "files": {},
        }

        for cache_name in self.CACHE_FILES:
            cache_path = self.get_cache_path(cache_name)
            if cache_path.exists():
                stat = cache_path.stat()
                cache_info["files"][cache_name] = {
                    "exists": True,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "valid": self.is_cache_valid(cache_name),
                }
            else:
                cache_info["files"][cache_name] = {"exists": False}

        return cache_info


class CustomJSONEncoder(json.JSONEncoder):
    """
    自定义 JSON 编码器

    处理 pandas Timestamp, numpy 等特殊类型
    """

    def default(self, obj):
        if isinstance(obj, (set, frozenset)):
            return sorted(obj, key=lambda item: str(item))

        # 处理时间戳
        if hasattr(obj, "isoformat"):
            return obj.isoformat()

        # 处理 numpy 类型
        if hasattr(obj, "dtype"):
            import numpy as np

            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.bool_):
                return bool(obj)

        # 处理 pandas Series
        if hasattr(obj, "tolist"):
            return obj.tolist()

        # 处理字典和对象
        if hasattr(obj, "__dict__"):
            return obj.__dict__

        # 处理 Path 对象
        if isinstance(obj, Path):
            return str(obj)

        return super().default(obj)
