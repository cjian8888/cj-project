"""
Base abstract detector interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseDetector(ABC):
    """Abstract base class for detectors.

    Subclasses must provide a human-readable name, description and risk_level.
    The detector can be enabled/disabled via the `enabled` property (default: True).
    The `detect` method should accept input data and a configuration dictionary
    and return a list of detection results as dictionaries.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique, human-friendly detector name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description of what the detector checks."""
        raise NotImplementedError

    @property
    @abstractmethod
    def risk_level(self) -> str:
        """String indicating risk level (e.g., 'low', 'medium', 'high')."""
        raise NotImplementedError

    @property
    def enabled(self) -> bool:
        """Whether this detector is enabled by default. Subclasses may override."""
        return True

    @abstractmethod
    def detect(self, data: Dict[str, Any], config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute the detection on provided data using the given configuration.

        Parameters:
        - data: Input data to analyze, typically a dictionary.
        - config: Detector-specific configuration options.

        Returns:
        - List of detection results, where each result is a dictionary with
          keys representing attributes of the finding (e.g., 'id', 'score',
          'metadata', etc.).
        """
        raise NotImplementedError
