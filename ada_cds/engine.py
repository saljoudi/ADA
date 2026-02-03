from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .audit import AuditLogger
from .config import ConfigManager
from .models import Patient, ValidationResult
from .ontology_service import OntologyService
from .rule_registry import RuleRegistry
from .temporal import TemporalEngine


class EnhancedEligibilityResult:
    """Result for a single intervention."""

    def __init__(
        self,
        eligible: bool,
        strength: str,
        recommendations: List[str],
        contraindications: List[str],
        missing_data: List[str],
        guideline_references: List[str],
        evidence_levels: List[str],
        payer_coverage_notes: Optional[List[str]] = None,
        prior_auth_required: bool = False,
        estimated_coverage: Optional[str] = None,
    ):
        self.eligible = eligible
        self.strength = strength
        self.recommendations = recommendations
        self.contraindications = contraindications
        self.missing_data = missing_data
        self.guideline_references = guideline_references
        self.evidence_levels = evidence_levels
        self.payer_coverage_notes = payer_coverage_notes or []
        self.prior_auth_required = prior_auth_required
        self.estimated_coverage = estimated_coverage


class EnhancedEngineOutput:
    """Aggregated output returned to the API layer."""

    def __init__(
        self,
        validation: ValidationResult,
        eligibility: Dict[str, EnhancedEligibilityResult],
        care_gaps: List[Dict[str, str]],
        rule_evaluations: Dict[str, Dict[str, Any]],
        audit_trail_id: str,
    ):
        self.validation = validation
        self.eligibility = eligibility
        self.care_gaps = care_gaps
        self.rule_evaluations = rule_evaluations
        self.audit_trail_id = audit_trail_id
        self.timestamp = datetime.utcnow()


class EnhancedADAReasoningEngine:
    """The public facade used by the FastAPI router."""

    def __init__(self, config_path: Optional[Path] = None, ontology_dir: Optional[Path] = None):
        self.config = ConfigManager(config_path)
        self.temporal = TemporalEngine(self.config)

        self.ontology = OntologyService(ontology_dir or Path("./ontologies"))
        self.rule_registry = RuleRegistry(self.config, self.ontology)

        self.audit_logger = AuditLogger()
        self.clinician_id: Optional[str] = None

    def set_clinician(self, clinician_id: str) -> None:
        self.clinician_id = clinician_id

    def evaluate(self, patient: Patient) -> EnhancedEngineOutput:
        validation = self._validate_patient_data(patient)
        rule_results = self.rule_registry.evaluate_all(patient, self.temporal)
        eligibility = self._aggregate_eligibility(patient, rule_results)
        care_gaps = self._identify_care_gaps(patient)

        audit_id = self.audit_logger.log_evaluation(
            patient,
            self.clinician_id,
            rule_results,
            {k: v.__dict__ for k, v in eligibility.items()},
        )

        return EnhancedEngineOutput(
            validation,
            eligibility,
            care_gaps,
            rule_results,
            audit_id,
        )

    def _validate_patient_data(self, patient: Patient) -> ValidationResult:
        v = ValidationResult()
        if not patient.diagnoses:
            v.errors.append("No diagnoses recorded")
        hba1c = next((l for l in patient.labs if l.loinc == "LOINC:4548-4"), None)
        ok, reason = self.temporal.is_lab_current(hba1c, "hba1c")
        if not ok:
            v.errors.append(f"HbA1c: {reason}")
        if patient.pregnant and patient.age > 55:
            v.warnings.append("Pregnant age > 55")
        for med in patient.medications:
            if med.contraindicated:
                v.errors.append(f"Contraindicated medication: {med.name}")
        return v

    def _aggregate_eligibility(
        self,
        patient: Patient,
        rule_results: Dict[str, Dict[str, Any]],
    ) -> Dict[str, EnhancedEligibilityResult]:
        """Group rule results by intervention and calculate strength / coverage."""
        by_int: Dict[str, Dict] = {}
        for rid, r in rule_results.items():
            intr = r["intervention"]
            if intr not in by_int:
                by_int[intr] = {
                    "eligible_rules": [],
                    "ineligible_rules": [],
                    "guideline_refs": set(),
                    "evidence_levels": set(),
                    "met": [],
                    "unmet": [],
                }

            target = by_int[intr]
            if r["eligible"]:
                target["eligible_rules"].append(rid)
            else:
                target["ineligible_rules"].append(rid)

            target["guideline_refs"].add(r["guideline_ref"])
            target["evidence_levels"].add(r["evidence_level"])
            target["met"].extend(r["met_conditions"])
            target["unmet"].extend(r["unmet_conditions"])

        out: Dict[str, EnhancedEligibilityResult] = {}
        for intr, data in by_int.items():
            eligible = len(data["eligible_rules"]) > 0

            if eligible:
                if len(data["eligible_rules"]) >= 2:
                    strength = "strong"
                elif "A" in data["evidence_levels"]:
                    strength = "strong"
                else:
                    strength = "moderate"
            else:
                strength = "weak"

            payer_notes = []
            prior_auth = False
            if patient.payer == "medicare":
                if intr == "CGM" and patient.age >= 65:
                    payer_notes.append("Medicare covers CGM for age >=65")
                    prior_auth = True

            est_cov = self._estimate_coverage(patient, intr)

            out[intr] = EnhancedEligibilityResult(
                eligible=eligible,
                strength=strength,
                recommendations=list(set(data["met"])),
                contraindications=self._check_contraindications(patient, intr),
                missing_data=list(set(data["unmet"])),
                guideline_references=list(data["guideline_refs"]),
                evidence_levels=list(data["evidence_levels"]),
                payer_coverage_notes=payer_notes,
                prior_auth_required=prior_auth,
                estimated_coverage=est_cov,
            )
        return out

    def _check_contraindications(self, patient: Patient, intervention: str) -> List[str]:
        contra = []
        if intervention == "GLP1":
            if patient.pregnant:
                contra.append("Pregnancy")
            if "pancreatitis" in patient.contraindications:
                contra.append("History of pancreatitis")
        if intervention == "SGLT2":
            if any(d.name.lower() == "esrd" for d in patient.diagnoses):
                contra.append("End-stage renal disease")
        return contra

    def _estimate_coverage(self, patient: Patient, intervention: str) -> Optional[str]:
        if not patient.payer:
            return "unknown"
        map_ = {
            "medicare": {
                "GLP1": "likely",
                "SGLT2": "likely",
                "CGM": "likely" if patient.uses_insulin else "unlikely",
            },
            "medicaid": {"GLP1": "unlikely", "SGLT2": "likely", "CGM": "unlikely"},
            "commercial": {
                "GLP1": "likely",
                "SGLT2": "likely",
                "CGM": "likely" if patient.uses_insulin else "unlikely",
            },
        }
        return map_.get(patient.payer, {}).get(intervention, "unknown")

    def _identify_care_gaps(self, patient: Patient) -> List[Dict[str, str]]:
        gaps = []
        for typ, name, section, last in (
            ("eye_exam", "Eye Exam", "12", patient.last_eye_exam),
            ("foot_exam", "Foot Exam", "12", patient.last_foot_exam),
            ("dental_exam", "Dental Exam", "4", patient.last_dental_exam),
        ):
            needed, reason = self.temporal.needs_annual_screening(last, typ, patient)
            if needed:
                gaps.append({"name": name, "ada_section": section, "action": reason})

        hba1c = next((l for l in patient.labs if l.loinc == "LOINC:4548-4"), None)
        if hba1c:
            cur, reason = self.temporal.is_lab_current(hba1c, "hba1c")
            if not cur:
                gaps.append(
                    {"name": "HbA1c Monitoring", "ada_section": "6", "action": reason}
                )
        else:
            gaps.append({"name": "HbA1c Monitoring", "ada_section": "6", "action": "No result"})

        if any(d.mondo.startswith("MONDO:000514") for d in patient.diagnoses) and patient.age >= 40:
            gaps.append(
                {"name": "CV Risk Assessment", "ada_section": "10", "action": "Consider statin therapy"}
            )

        if any(d.mondo.startswith("MONDO:000514") for d in patient.diagnoses):
            egfr = next((l for l in patient.labs if l.loinc == "LOINC:48643-1"), None)
            uacr = next((l for l in patient.labs if l.loinc == "LOINC:9318-7"), None)
            if not (egfr and uacr):
                gaps.append({"name": "CKD Screening", "ada_section": "11", "action": "Order eGFR & UACR"})

        return gaps
