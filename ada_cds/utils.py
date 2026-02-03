from typing import List, Tuple


def extract_curie(uri: str) -> str:
    """
    Turn a full URI into a CURIE (prefix:local). Very simple heuristic.
    """
    if "://" not in uri:
        return uri
    parts = uri.split("/")
    local = parts[-1]
    domain = uri.split("//")[1].split("/")[0]
    prefix_map = {
        "loinc.org": "LOINC",
        "rxnorm.info": "rxnorm",
        "purl.obolibrary.org": "MONDO",
        "snomed.info": "SNOMED",
    }
    for dom, pref in prefix_map.items():
        if dom in domain:
            return f"{pref}:{local}"
    return f"ex:{local}"
