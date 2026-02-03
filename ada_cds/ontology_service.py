from pathlib import Path
from typing import List

import rdflib
from rdflib.namespace import OWL, RDFS, SKOS


class OntologyService:
    """
    Wrapper around an rdflib.Graph that loads LOINC, RxNorm,
    MONDO (and any custom ADA extension) and provides
    convenient lookup / subclass reasoning.
    """

    def __init__(self, ontology_dir: Path | str = Path("./ontologies"), preload: bool = True):
        self.graph = rdflib.Graph()
        self.ns = {
            "loinc": rdflib.Namespace("http://loinc.org/rdf/"),
            "rxnorm": rdflib.Namespace("http://rxnorm.info/rdf/"),
            "mondo": rdflib.Namespace("http://purl.obolibrary.org/obo/MONDO_"),
            "snomed": rdflib.Namespace("http://snomed.info/id/"),
            "ex": rdflib.Namespace("http://example.org/ada#"),
        }

        if preload:
            self.load_ontologies(Path(ontology_dir))

    def load_ontologies(self, base_dir: Path):
        for pattern in ("*.ttl", "*.rdf", "*.owl"):
            for p in base_dir.rglob(pattern):
                try:
                    fmt = rdflib.util.guess_format(str(p))
                    self.graph.parse(p, format=fmt)
                    print(f"✔ Loaded {p.relative_to(base_dir)}")
                except Exception as exc:
                    print(f"⚠️  Failed to load {p.name}: {exc}")

    def resolve_code(self, curie: str) -> rdflib.URIRef:
        """Expand CURIE -> URI and follow owl:sameAs / skos:exactMatch."""
        ns, code = curie.split(":")
        uri = self.ns[ns][code]
        return self.equivalent(curie)[0]

    def label(self, uri: rdflib.URIRef) -> str:
        lbl = self.graph.value(uri, RDFS.label)
        if lbl:
            return str(lbl)
        for pfx, ns in self.ns.items():
            if str(uri).startswith(str(ns)):
                return f"{pfx}:{uri.split(str(ns))[-1]}"
        return str(uri)

    def synonyms(self, uri: rdflib.URIRef) -> List[str]:
        syn = {str(self.graph.value(uri, RDFS.label))}
        for lit in self.graph.objects(uri, SKOS.altLabel):
            syn.add(str(lit))
        for eq in self.graph.objects(uri, OWL.equivalentClass):
            syn.add(self.label(eq))
        return [s for s in syn if s]

    def is_a(self, child: rdflib.URIRef, parent: rdflib.URIRef) -> bool:
        """Transitive subclass reasoning (rdfs:subClassOf+)."""
        q = """
        ASK {
            ?child rdfs:subClassOf+ ?parent .
        }
        """
        return bool(
            self.graph.query(
                q,
                initBindings={"child": child, "parent": parent},
            )
        )

    def equivalent(self, curie: str) -> List[rdflib.URIRef]:
        """Collect owl:sameAs / skos:exactMatch for a CURIE."""
        ns, code = curie.split(":")
        uri = self.ns[ns][code]
        matches = {uri}
        for eq in self.graph.objects(uri, OWL.sameAs):
            matches.add(eq)
        for eq in self.graph.objects(uri, SKOS.exactMatch):
            matches.add(eq)
        return list(matches)

    def find_lab_by_parent(self, parent_curie: str) -> List[rdflib.URIRef]:
        """All LOINC children of a parent LOINC concept."""
        parent_uri = self.resolve_code(parent_curie)
        q = """
        SELECT ?lab WHERE {
            ?lab rdfs:subClassOf+ ?parent .
        }
        """
        return [
            row.lab
            for row in self.graph.query(q, initBindings={"parent": parent_uri})
        ]

    def serialize(self, fmt: str = "turtle") -> str:
        return self.graph.serialize(format=fmt).decode()
