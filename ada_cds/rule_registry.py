from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .config import ConfigManager
from .models import Patient
from .ontology_service import OntologyService
from .temporal import TemporalEngine


class ConditionSource(Enum):
    CURIE = "curie"
    ONTOLOGY_QUERY = "query"


@dataclass
class ClinicalCondition:
    type: str
    code: Optional[str] = None
    operator: str = "exists"
    value: Optional[Any] = None
    source: ConditionSource = ConditionSource.CURIE
    query: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClinicalRule:
    rule_id: str
    name: str
    description: str
    intervention: str
    conditions: List[ClinicalCondition]
    action: str
    guideline_ref: str
    evidence_level: str
    source: str
    effective_date: date
    expiration_date: Optional[date] = None
    payer_specific: Optional[List[str]] = None

    def __post_init__(self):
        self.ontology: Optional[OntologyService] = None

    def evaluate(
        self,
        patient: Patient,
        config: ConfigManager,
        temporal: TemporalEngine,
    ) -> Tuple[bool, List[str], List[str]]:
        met, unmet = [], []

        for cond in self.conditions:
            ok, reason = self._evaluate_condition(cond, patient, config, temporal)
            if ok:
                met.append(reason)
            else:
                unmet.append(reason)

        return len(unmet) == 0, met, unmet

    def _evaluate_condition(
        self,
        condition: ClinicalCondition,
        patient: Patient,
        config: ConfigManager,
        temporal: TemporalEngine,
    ) -> Tuple[bool, str]:
        if condition.type == "diagnosis":
            target = self.ontology.resolve_code(condition.code)
            patient_uris = {
                self.ontology.resolve_code(d.mondo) for d in patient.diagnoses if d.mondo
            } | {
                self.ontology.resolve_code(d.icd10) for d in patient.diagnoses if d.icd10
            }

            match = any(self.ontology.is_a(p_uri, target) for p_uri in patient_uris)
            return (
                match if condition.operator == "exists" else not match,
                f"Diagnosis {condition.code}",
            )

        if condition.type == "lab":
            if condition.source == ConditionSource.CURIE:
                lab = next((l for l in patient.labs if l.loinc == condition.code), None)
            else:
                labs_curie = [
                    str(uri).split("/")[-1]
                    for uri in self.ontology.graph.query(condition.query)
                ]
                lab = next((l for l in patient.labs if l.loinc in labs_curie), None)

            ok, reason = temporal.is_lab_current(lab, "lab")
            if not ok:
                return False, f"Lab {condition.code or 'query'}: {reason}"

            if condition.operator == ">=":
                return lab.value >= condition.value, f"{lab.loinc} >= {condition.value}"
            if condition.operator == "<=":
                return lab.value <= condition.value, f"{lab.loinc} <= {condition.value}"

        if condition.type == "medication":
            if condition.source == ConditionSource.CURIE:
                target = self.ontology.resolve_code(condition.code)
                has = any(
                    self.ontology.is_a(
                        self.ontology.resolve_code(m.rxnorm_code), target
                    )
                    for m in patient.medications
                )
            else:
                meds_curie = [
                    str(uri).split("/")[-1]
                    for uri in self.ontology.graph.query(condition.query)
                ]
                has = any(m.rxnorm_code in meds_curie for m in patient.medications)

            return (
                has if condition.operator == "exists" else not has,
                f"Medication {condition.code or 'query'}",
            )

        if condition.type == "demographic":
            if condition.code == "age":
                if condition.operator == ">=":
                    return patient.age >= condition.value, f"Age >= {condition.value}"
                if condition.operator == "<=":
                    return patient.age <= condition.value, f"Age <= {condition.value}"
            if condition.code == "pregnancy":
                return (
                    (not patient.pregnant) if condition.operator == "not_exists" else patient.pregnant,
                    "Pregnancy status",
                )

        if condition.type == "diagnosis_generic":
            if condition.code == "diabetes" and condition.operator == "exists":
                has = any(d.mondo.startswith("MONDO:000514") for d in patient.diagnoses)
                return has, "Has diabetes"

        return False, "Condition type not implemented"


class RuleRegistry:
    """Loads all rules (hard-coded defaults + optional JSON extensions)."""

    def __init__(self, config: ConfigManager, ontology: OntologyService):
        self.config = config
        self.ontology = ontology
        self.rules: Dict[str, ClinicalRule] = {}
        self._load_default_rules()

    def _load_default_rules(self):
        """Hard-coded ADA rules - they receive the ontology instance."""
        glp1 = ClinicalRule(
            rule_id="GLP1_ADA_2026",
            name="GLP-1 RA for Poorly Controlled T2DM",
            description="GLP-1 RA when HbA1c >= 9% after oral therapy failure",
            intervention="GLP1",
            conditions=[
                ClinicalCondition(
                    type="diagnosis",
                    code="MONDO:0005148",
                    operator="exists",
                    source=ConditionSource.CURIE,
                ),
                ClinicalCondition(
                    type="lab",
                    code="LOINC:4548-4",
                    operator=">=",
                    value=9.0,
                    source=ConditionSource.CURIE,
                ),
                ClinicalCondition(
                    type="medication",
                    source=ConditionSource.ONTOLOGY_QUERY,
                    query="""
                        SELECT ?rx WHERE {
                            ?rx rdfs:subClassOf+ <rxnorm:8600> .
                        }
                    """,
                    operator="exists",
                ),
                ClinicalCondition(
                    type="demographic",
                    code="pregnancy",
                    operator="not_exists",
                ),
            ],
            action="recommend",
            guideline_ref="ADA 2026 Section 9",
            evidence_level="A",
            source="ada",
            effective_date=date(2026, 1, 1),
        )
        glp1.ontology = self.ontology
        self.rules[glp1.rule_id] = glp1

        sglt2 = ClinicalRule(
            rule_id="SGLT2_CKD_ADA_2026",
            name="SGLT2i for CKD in T2DM",
            description="Renoprotective SGLT2i when eGFR >= 20 & UACR >= 30",
            intervention="SGLT2",
            conditions=[
                ClinicalCondition(
                    type="diagnosis",
                    code="MONDO:0005148",
                    operator="exists",
                ),
                ClinicalCondition(
                    type="lab",
                    code="LOINC:48643-1",
                    operator=">=",
                    value=20,
                ),
                ClinicalCondition(
                    type="lab",
                    code="LOINC:9318-7",
                    operator=">=",
                    value=30,
                ),
            ],
            action="recommend",
            guideline_ref="ADA 2026 Section 11",
            evidence_level="A",
            source="ada",
            effective_date=date(2026, 1, 1),
        )
        sglt2.ontology = self.ontology
        self.rules[sglt2.rule_id] = sglt2

        cgm = ClinicalRule(
            rule_id="CGM_ADA_2026",
            name="CGM for Diabetes Management",
            description="CGM for insulin-treated diabetes or high hypoglycemia risk",
            intervention="CGM",
            conditions=[
                ClinicalCondition(
                    type="diagnosis_generic",
                    code="diabetes",
                    operator="exists",
                ),
                ClinicalCondition(
                    type="medication",
                    code="insulin",
                    operator="exists",
                ),
            ],
            action="recommend",
            guideline_ref="ADA 2026 Section 7",
            evidence_level="A",
            source="ada",
            effective_date=date(2026, 1, 1),
        )
        cgm.ontology = self.ontology
        self.rules[cgm.rule_id] = cgm

    def get_rules_for_intervention(self, intervention: str) -> List[ClinicalRule]:
        return [r for r in self.rules.values() if r.intervention == intervention]

    def evaluate_all(
        self,
        patient: Patient,
        temporal: TemporalEngine,
    ) -> Dict[str, Dict[str, Any]]:
        """Return a dict keyed by rule_id with evaluation details."""
        out: Dict[str, Dict[str, Any]] = {}
        for rule in self.rules.values():
            if rule.payer_specific and patient.payer not in rule.payer_specific:
                continue
            if rule.expiration_date and rule.expiration_date < date.today():
                continue

            eligible, met, unmet = rule.evaluate(patient, self.config, temporal)
            out[rule.rule_id] = {
                "eligible": eligible,
                "intervention": rule.intervention,
                "met_conditions": met,
                "unmet_conditions": unmet,
                "guideline_ref": rule.guideline_ref,
                "evidence_level": rule.evidence_level,
                "action": rule.action,
            }
        return out
