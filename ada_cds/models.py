from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, List, Optional


class RuleSource(str):
    ADA = "ada"
    PAYER = "payer"
    CLINIC = "clinic"


@dataclass
class LabResult:
    loinc: str
    value: float
    unit: str
    date: date
    source: str = "EHR"


@dataclass
class Medication:
    rxnorm_code: str
    name: str
    start_date: date
    end_date: Optional[date] = None
    failed: bool = False
    contraindicated: bool = False


@dataclass
class Diagnosis:
    icd10: str
    mondo: str
    name: str
    onset_date: Optional[date] = None


@dataclass
class VitalSigns:
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    date: Optional[date] = None


@dataclass
class ValidationResult:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def ok(self) -> bool:
        return not self.errors


@dataclass
class Patient:
    patient_id: str
    age: int
    sex: str
    mrn: Optional[str] = None
    diagnoses: List[Diagnosis] = field(default_factory=list)
    labs: List[LabResult] = field(default_factory=list)
    medications: List[Medication] = field(default_factory=list)
    vital_signs: Optional[VitalSigns] = None
    pregnant: bool = False
    breastfeeding: bool = False
    smoking_status: Optional[str] = None
    payer: Optional[str] = None
    last_eye_exam: Optional[date] = None
    last_foot_exam: Optional[date] = None
    last_dental_exam: Optional[date] = None
    allergies: List[str] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)

    @property
    def bmi(self) -> Optional[float]:
        if not self.vital_signs or not self.vital_signs.weight_kg or not self.vital_signs.height_cm:
            return None
        if self.vital_signs.height_cm <= 0:
            return None
        h_m = self.vital_signs.height_cm / 100.0
        return self.vital_signs.weight_kg / (h_m**2)

    @property
    def uses_insulin(self) -> bool:
        insulin_codes = {"rxnorm:2618", "rxnorm:260265", "rxnorm:575802"}
        return any(m.rxnorm_code in insulin_codes for m in self.medications)

    @property
    def diabetes_complications(self) -> bool:
        complication_codes = {
            "E11.31",
            "E11.32",
            "E11.33",
            "E11.34",
            "E11.35",
            "E11.36",
            "E11.39",
        }
        return any(d.icd10 in complication_codes for d in self.diagnoses)
