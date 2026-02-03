import json
from pathlib import Path

config = {
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
    "clinic_overrides": {
        "clinic_001": {"hba1c_recency_days": 60, "annual_eye_exam_days": 180}
    },
}

out_path = Path("../configs/default.json")
out_path.write_text(json.dumps(config, indent=2))
print(f"Wrote example config to {out_path}")
