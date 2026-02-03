import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from ada_cds.engine import EnhancedADAReasoningEngine
from api.dependencies import get_engine
from api.schemas import EvaluationResponse, PatientRequest

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_patient(
    payload: PatientRequest,
    engine: EnhancedADAReasoningEngine = Depends(get_engine),
    x_api_key: Optional[str] = Header(None),
):
    expected_key = os.getenv("API_KEY", "demo-key")
    if x_api_key != expected_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if payload.clinician_id:
        engine.set_clinician(payload.clinician_id)

    from ada_cds.models import Diagnosis, LabResult, Medication, Patient, VitalSigns

    patient = Patient(
        patient_id=payload.patient_id,
        mrn=payload.mrn,
        age=payload.age,
        sex=payload.sex,
        diagnoses=[Diagnosis(**d.dict()) for d in payload.diagnoses],
        labs=[LabResult(**l.dict()) for l in payload.labs],
        medications=[Medication(**m.dict()) for m in payload.medications],
        vital_signs=VitalSigns(**(payload.vital_signs.dict() if payload.vital_signs else {})),
        pregnant=payload.pregnant,
        payer=payload.payer,
    )

    out = engine.evaluate(patient)

    return EvaluationResponse(
        evaluation_id=out.audit_trail_id,
        timestamp=out.timestamp.isoformat(),
        validation={"errors": out.validation.errors, "warnings": out.validation.warnings},
        eligibility={k: v.__dict__ for k, v in out.eligibility.items()},
        care_gaps=out.care_gaps,
        audit_trail_id=out.audit_trail_id,
        metadata=out.validation.__dict__,
    )
