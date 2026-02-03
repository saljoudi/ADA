import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from fastapi import Header

from ada_cds.engine import EnhancedADAReasoningEngine


def _resolve_config_path(tenant_id: Optional[str]) -> Path:
    config_dir = Path(os.getenv("CONFIG_DIR", "./configs/tenants"))
    if tenant_id:
        for suffix in (".json", ".yaml", ".yml"):
            candidate = config_dir / f"{tenant_id}{suffix}"
            if candidate.exists():
                return candidate
    return Path("./configs/default.json")


@lru_cache(maxsize=64)
def _engine_for_tenant(tenant_id: Optional[str]) -> EnhancedADAReasoningEngine:
    return EnhancedADAReasoningEngine(
        config_path=_resolve_config_path(tenant_id),
        ontology_dir=Path(os.getenv("ONTOLOGY_DIR", "./ontologies")),
    )


def get_engine(x_tenant_id: Optional[str] = Header(None)) -> EnhancedADAReasoningEngine:
    return _engine_for_tenant(x_tenant_id)
