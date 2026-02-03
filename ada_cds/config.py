import json
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigManager:
    """Loads JSON/YAML configuration and provides dot-notation access."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        "thresholds": {
            "hba1c_poor_control": 9.0,
            "hba1c_recency_days": 90,
            "annual_hba1c_days": 365,
            "obesity_bmi": 30,
            "ckd_egfr_threshold": 20,
            "ckd_uacr_threshold": 30,
            "age_cv_screening": 40,
            "annual_eye_exam_days": 365,
            "annual_foot_exam_days": 365,
            "annual_dental_exam_days": 365,
        },
        "payer_rules": {
            "medicare": {"cgm_min_age": 65, "requires_prior_auth": True},
            "medicaid": {"state_specific": True},
            "commercial": {"cgm_min_age": 18, "requires_prior_auth": False},
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path and config_path.exists():
            self._deep_update(self.config, self._load_config(config_path))

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        suffix = config_path.suffix.lower()
        with open(config_path, "r") as f:
            if suffix in {".yaml", ".yml"}:
                return yaml.safe_load(f) or {}
            return json.load(f)

    def _deep_update(self, base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Key can be dot-separated, e.g. 'thresholds.hba1c_poor_control'."""
        parts = key.split(".")
        cur = self.config
        for p in parts:
            if isinstance(cur, dict) and p in cur:
                cur = cur[p]
            else:
                return default
        return cur

    def update_clinic_rules(self, clinic_id: str, rules: Dict[str, Any]) -> None:
        if "clinic_overrides" not in self.config:
            self.config["clinic_overrides"] = {}
        self.config["clinic_overrides"][clinic_id] = rules
