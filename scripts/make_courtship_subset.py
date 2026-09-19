"""Build the illustrative Drosophila male-courtship decision subset.

Textbook/review-consensus pathway topology (Clowney et al. 2015, eLife;
Kallman et al. 2015, eLife; Pavlou & Goodwin 2013, Nat Rev Neurosci),
unweighted, clearly labelled illustrative — NOT measured connectivity.
Clowney et al. explicitly demonstrate functional convergence, NOT
monosynaptic proof; the file states this.

Usage: python scripts/make_courtship_subset.py
Output: data/processed/drosophila_courtship_subset_v1.json
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "processed" / "drosophila_courtship_subset_v1.json"

NODES = [
    {"id": "PPK25", "type": "sensory", "class": "gustatory",
     "region": "foreleg", "x": -4.0, "y": 2.5, "dimorphism": "not-specified",
     "function": "ppk25+ foreleg sensory; detects female pheromone 7,11-HD (Clowney 2015)"},
    {"id": "FCELL", "type": "sensory", "class": "gustatory",
     "region": "leg", "x": -2.0, "y": 2.5, "dimorphism": "not-specified",
     "function": "ppk23+ F cells; female-pheromone sensory, activate P1 (Kallman 2015)"},
    {"id": "MCELL", "type": "sensory", "class": "gustatory",
     "region": "leg", "x": 0.0, "y": 2.5, "dimorphism": "not-specified",
     "function": "ppk23+ M cells; male-pheromone sensory, drive mAL (Kallman 2015)"},
    {"id": "GR32A", "type": "sensory", "class": "gustatory",
     "region": "mouthparts", "x": 2.0, "y": 2.5, "dimorphism": "not-specified",
     "function": "Gr32a sensory; detects male pheromone 7-T, converges on mAL (review)"},
    {"id": "OR67D", "type": "sensory", "class": "olfactory",
     "region": "antenna", "x": 4.0, "y": 2.5, "dimorphism": "not-specified",
     "function": "Or67d olfactory; detects male pheromone cVA, parallel route to P1 (review)"},
    {"id": "VAB3", "type": "interneuron", "class": "ascending",
     "region": "VNC-SEZ-lpr", "x": -3.0, "y": 0.0, "dimorphism": "dimorphic",
     "function": "ascending excitatory relay, female-pheromone selective; feminization alters connectivity (Clowney 2015)"},
    {"id": "MAL", "type": "interneuron", "class": "inhibitory",
     "region": "SEZ-lpr", "x": -1.0, "y": 0.0, "dimorphism": "dimorphic",
     "function": "GABAergic, ~30 male vs ~5 female cells; gain control on P1 (Kimura 2005; Kallman 2015)"},
    {"id": "P1", "type": "interneuron", "class": "command",
     "region": "lateral protocerebrum", "x": 1.5, "y": 0.0, "dimorphism": "male-specific",
     "function": "male-specific courtship command (~30 cells); excitation triggers sustained courtship (Kohatsu 2011)"},
    {"id": "P2B", "type": "interneuron", "class": "relay",
     "region": "lpr-thoracic", "x": 3.5, "y": -1.5, "dimorphism": "not-specified",
     "function": "courtship relay P1>dendrites superimposed; descending to thoracic motor (review)"},
]

# (source, target, sign) — pathway-level functional convergence, qualitative
PATHWAYS = [
    ("PPK25", "VAB3", +1),
    ("VAB3", "P1", +1),
    ("VAB3", "MAL", +1),
    ("FCELL", "P1", +1),
    ("MCELL", "MAL", +1),
    ("GR32A", "MAL", +1),
    ("OR67D", "MAL", +1),
    ("MAL", "P1", -1),
    ("P1", "P2B", +1),
]


def main():
    ids = {n["id"] for n in NODES}
    edges = []
    for s, t, sign in PATHWAYS:
        assert s in ids and t in ids, (s, t)
        edges.append({"source": s, "target": t, "kind": "chemical",
                      "weight": None, "sign": sign})
    doc = {
        "id": "drosophila_courtship_subset",
        "species": "drosophila_melanogaster",
        "version": "1.0.0",
        "source": "BrainerLab (assembled from cited review consensus, no new measurements)",
        "publication": "Clowney et al. 2015, eLife; Kallman et al. 2015, eLife; Pavlou & Goodwin 2013 (pathway identity)",
        "license": "MIT (BrainerLab own file; topology = cited consensus, no copied bulk data)",
        "completeness": "ILLUSTRATIVE SUBSET ONLY: 9 cell types of the male courtship decision pathway, "
                        "unweighted qualitative edges with E/I sign. NOT measured connectivity and NOT "
                        "monosynaptic proof (functional convergence per Clowney 2015).",
        "limitations": "Pathway-level only; intermediate neurons omitted; sim dynamics are model choices, "
                       "not measurements. Dimorphism flags cite the stated sources per node.",
        "nodes": NODES,
        "edges": edges,
    }
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {OUT}: {len(NODES)} nodes, {len(edges)} edges")


if __name__ == "__main__":
    main()
