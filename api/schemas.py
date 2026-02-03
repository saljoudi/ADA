from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator


class LabSchema(BaseModel):
    loinc: str
    value: float
    unit: str
    date: date
    source: Optional[str] = "EHR"


class MedicationSchema(BaseModel):
    rxnorm_code: str
    name: str
    start_date: date
    end_date: Optional[date] = None
    failed: Optional[bool] = False
    contraindicated: Optional[bool] = False


class DiagnosisSchema(BaseModel):
    icd10: str
    mondo: str
    name: str
    onset_date: Optional[date] = None


class VitalSignsSchema(BaseModel):
    systolic: Optional[float] = None
    diastolic: Optional[float] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    date: Optional[date] = None


class PatientRequest(BaseModel):
    patient_id: str
    mrn: Optional[str] = None
    age: int
    sex: str = Field(..., regex="^[MF]$")
    diagnoses: List[DiagnosisSchema]
    labs: List[LabSchema]
    medications: List[MedicationSchema]
    vital_signs: Optional[VitalSignsSchema] = None
    pregnant: Optional[bool] = False
    payer: Optional[str] = None
    clinician_id: Optional[str] = None

    @validator("sex")
    def upper_sex(cls, v):
        return v.upper()


class EligibilityItem(BaseModel):
    eligible: bool
    strength: str
    recommendations: List[str]
    contraindications: List[str]
    missing_data: List[str]
    guideline_references: List[str]
    evidence_levels: List[str]
    payer_coverage_notes: List[str] = []
    prior_auth_required: bool = False
    estimated_coverage: Optional[str] = None


class EvaluationResponse(BaseModel):
    evaluation_id: str
    timestamp: str
    validation: Dict[str, List[str]]
    eligibility: Dict[str, EligibilityItem]
    care_gaps: List[Dict[str, str]]
    audit_trail_id: str
    metadata: Dict[str, Any]
