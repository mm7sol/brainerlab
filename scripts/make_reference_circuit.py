"""Build the bundled C. elegans reference-circuit file (illustrative subset).

Topology: anterior/posterior gentle-touch withdrawal circuit (textbook consensus:
Chalfie et al. 1985; Wicks & Rankin 1995). Edges are qualitative/unweighted
(weight=null). Coordinates are schematic display-only.
Usage: python scripts/make_reference_circuit.py [--check]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "processed" / "c_elegans_reference_circuit_v1.json"

NODES = [
    # id, class, type, region, function note, schematic x,y
    ("ALML", "ALM", "sensory", "head", "anterior gentle-touch mechanosensory", -8, 6),
    ("ALMR", "ALM", "sensory", "head", "anterior gentle-touch mechanosensory", -8, -6),
    ("AVM", "AVM", "sensory", "head", "anterior gentle-touch mechanosensory", -6, 0),
    ("PLML", "PLM", "sensory", "tail", "posterior gentle-touch mechanosensory", 8, 5),
    ("PLMR", "PLM", "sensory", "tail", "posterior gentle-touch mechanosensory", 8, -5),
    ("PVM", "PVM", "sensory", "tail", "posterior mechanosensory", 6, 0),
    ("AVAL", "AVA", "interneuron", "head", "command: backward locomotion", -3, 3),
    ("AVAR", "AVA", "interneuron", "head", "command: backward locomotion", -3, -3),
    ("AVBL", "AVB", "interneuron", "head", "command: forward locomotion", -1, 3),
    ("AVBR", "AVB", "interneuron", "head", "command: forward locomotion", -1, -3),
    ("AVDL", "AVD", "interneuron", "head", "anterior touch relay", -5, 2),
    ("AVDR", "AVD", "interneuron", "head", "anterior touch relay", -5, -2),
    ("PVCL", "PVC", "interneuron", "tail", "posterior touch relay", 4, 2),
    ("PVCR", "PVC", "interneuron", "tail", "posterior touch relay", 4, -2),
    ("DA1", "DA", "motor", "ventral_cord", "dorsal A-type motor (backward)", 1, 4),
    ("VB1", "VB", "motor", "ventral_cord", "ventral B-type motor (forward)", 1, -4),
]

EDGES = [
    # (source, target) — qualitative chemical direction, textbook consensus
    ("ALML", "AVDL"), ("ALMR", "AVDR"), ("ALML", "AVAL"), ("ALMR", "AVAR"),
    ("AVM", "AVDL"), ("AVM", "AVDR"), ("AVM", "AVAL"), ("AVM", "PVCL"),
    ("PLML", "PVCL"), ("PLMR", "PVCR"), ("PVM", "PVCL"), ("PVM", "PVCR"),
    ("AVDL", "AVAL"), ("AVDR", "AVAR"), ("AVDL", "AVBL"), ("AVDR", "AVBR"),
    ("PVCL", "AVBL"), ("PVCR", "AVBR"), ("PVCL", "AVAR"),
    ("AVAL", "DA1"), ("AVAR", "DA1"), ("AVBL", "VB1"), ("AVBR", "VB1"),
]


def build():
    doc = {
        "id": "c_elegans_reference_circuit",
        "species": "caenorhabditis_elegans",
        "version": "1.0.0",
        "source": "BrainerLab (curated from cited textbook circuit)",
        "publication": "Chalfie et al. 1985; Wicks & Rankin 1995 (circuit identity)",
        "license": "MIT (own file; no copied bulk data)",
        "completeness": "ILLUSTRATIVE SUBSET ONLY: touch-withdrawal circuit, 16 nodes / "
                        "23 directed qualitative edges. NOT a connectome.",
        "limitations": "Unweighted edges; schematic coordinates display-only; "
                       "dynamics are model choices.",
        "position_note": "x,y are schematic layout for display only, not measured anatomy.",
        "nodes": [
            {"id": n, "class": c, "type": t, "region": r, "function": f, "x": x, "y": y,
             "neurotransmitter": None}
            for (n, c, t, r, f, x, y) in NODES
        ],
        "edges": [
            {"source": s, "target": t, "kind": "chemical", "weight": None,
             "provenance": "textbook circuit consensus (qualitative)"}
            for (s, t) in EDGES
        ],
    }
    return doc


def main():
    doc = build()
    if "--check" in sys.argv:
        on_disk = json.loads(OUT.read_text(encoding="utf-8"))
        print("MATCH" if on_disk == doc else "MISMATCH")
        sys.exit(0 if on_disk == doc else 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(doc['nodes'])} nodes, {len(doc['edges'])} edges)")


if __name__ == "__main__":
    main()
