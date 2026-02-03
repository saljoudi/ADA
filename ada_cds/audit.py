from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class AuditEntry:
    timestamp: datetime
    patient_id: str
    clinician_id: Optional[str]
    action: str
    rule_id: Optional[str] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """In-memory logger - replace with DB writer for production."""

    def __init__(self):
        self.entries: List[AuditEntry] = []

    def log_evaluation(
        self,
        patient,
        clinician_id: Optional[str],
        rules_evaluated: Dict[str, Any],
        final_recommendations: Dict[str, Any],
    ) -> str:
        entry = AuditEntry(
            timestamp=datetime.utcnow(),
            patient_id=patient.patient_id,
            clinician_id=clinician_id,
            action="clinical_evaluation",
            input_data={
                "age": patient.age,
                "sex": patient.sex,
                "diagnoses": [d.name for d in patient.diagnoses],
                "labs": len(patient.labs),
                "medications": len(patient.medications),
            },
            output_data=final_recommendations,
            metadata={
                "rules_evaluated": list(rules_evaluated.keys()),
                "payer": patient.payer,
            },
        )
        self.entries.append(entry)
        return entry.timestamp.isoformat()

    def get_patient_trail(self, patient_id: str) -> List[AuditEntry]:
        return [e for e in self.entries if e.patient_id == patient_id]

    def export_fhir_audit(self, start: datetime, end: datetime) -> List[Dict]:
        """
        Returns a list of FHIR-compatible AuditEvent resources.
        For a real implementation you would use `fhir.resources`.
        """
        out = []
        for e in self.entries:
            if start <= e.timestamp <= end:
                out.append(
                    {
                        "resourceType": "AuditEvent",
                        "type": {"code": e.action},
                        "recorded": e.timestamp.isoformat(),
                        "agent": [{"who": {"identifier": e.clinician_id or "system"}}],
                        "entity": [
                            {
                                "what": {"reference": f"Patient/{e.patient_id}"},
                                "detail": e.metadata,
                            }
                        ],
                    }
                )
        return out
