import datetime as dt
from pathlib import Path

import pytest

from ada_cds.engine import EnhancedADAReasoningEngine
from ada_cds.models import Diagnosis, LabResult, Medication, Patient, VitalSigns


@pytest.fixture
def engine():
    return EnhancedADAReasoningEngine(
        config_path=Path("./configs/default.json"),
        ontology_dir=Path("./ontologies"),
    )


def test_glp1_eligibility(engine):
    patient = Patient(
        patient_id="T001",
        age=58,
        sex="M",
        diagnoses=[
            Diagnosis(icd10="E11.9", mondo="MONDO:0005148", name="Type 2 Diabetes")
        ],
        labs=[
            LabResult(
                loinc="LOINC:4548-4", value=9.6, unit="%", date=dt.date.today() - dt.timedelta(days=30)
            )
        ],
        medications=[
            Medication(
                rxnorm_code="rxnorm:6809",
                name="Metformin",
                start_date=dt.date.today() - dt.timedelta(days=400),
                failed=True,
            )
        ],
        vital_signs=VitalSigns(weight_kg=95, height_cm=175, date=dt.date.today()),
        payer="medicare",
        pregnant=False,
    )
    out = engine.evaluate(patient)

    glp1 = out.eligibility["GLP1"]
    assert glp1.eligible is True
    assert glp1.strength in ("strong", "moderate")
    assert "LOINC:4548-4 >= 9.0" in glp1.recommendations
