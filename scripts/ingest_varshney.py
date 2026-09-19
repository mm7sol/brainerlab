"""Ingest full Varshney et al. 2011 C. elegans wiring.

Source: NeuronConnect.xls hosted in OpenWorm ConnectomeToolbox (MIT repo);
data extracted from Varshney et al. 2011, PLoS Comput Biol (CC-BY, cited in
the registry — redistribution with attribution allowed).

Semantics mirror the official VarshneyDataReader:
- S / Sp rows  -> directed chemical edge Neuron1 -> Neuron2, weight = count
- R / Rp rows  -> receive-view of the same wiring (verified 99.9% identical);
                  unioned with max weight, conflicts documented in output
- EJ rows      -> gap junctions, kept as directed entries (both directions)
- NMJ rows     -> aggregated to a single BWM (body-wall muscle) node,
                  one edge per neuron with summed weights

Nodes carry ids only: this matrix has no cell-type/region metadata
(types live in the illustrative reference subset, not here).

Usage: pip install xlrd ; python scripts/ingest_varshney.py
Output: data/processed/c_elegans_varshney2011_v1.json (BrainerLab schema)
"""
import json
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "c_elegans_varshney2011_v1.json"
URL = ("https://raw.githubusercontent.com/openworm/ConnectomeToolbox/main/"
       "cect/data/NeuronConnect.xls")


def norm(cell):
    cell = str(cell).strip().upper()
    if cell[:2] in ["VA", "VB", "VC", "VD", "DA", "DB", "DD", "AS"] and cell[-2:].startswith("0"):
        return "%s%s" % (cell[:-2], cell[-1:])
    return cell


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    xls = RAW / "NeuronConnect.xls"
    if not xls.exists():
        print(f"downloading {URL} ...")
        urllib.request.urlretrieve(URL, xls)
    try:
        import xlrd
    except ImportError:
        print("xlrd required: pip install xlrd")
        sys.exit(2)
    send, recv, ej, nmj = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    sh = xlrd.open_workbook(str(xls)).sheet_by_index(0)
    for r in range(1, sh.nrows):
        a, b, t = norm(sh.cell_value(r, 0)), norm(sh.cell_value(r, 1)), sh.cell_value(r, 2)
        n = int(sh.cell_value(r, 3))
        if t in ("S", "Sp"):
            send[(a, b)] += n
        elif t in ("R", "Rp"):
            recv[(b, a)] += n
        elif t == "EJ":
            ej[(a, b)] += n
        elif t == "NMJ":
            nmj[a] += n
        else:
            raise ValueError(f"unknown row type {t!r}")
    conflicts = {k: (send[k], recv[k]) for k in set(send) & set(recv) if send[k] != recv[k]}
    chem = {k: max(send.get(k, 0), recv.get(k, 0)) for k in set(send) | set(recv)}
    neurons = sorted({a for a, _ in chem} | {b for _, b in chem}
                     | {a for a, _ in ej} | {b for _, b in ej} | set(nmj))
    assert len(neurons) == 280, f"expected 280 connected neurons, got {len(neurons)}"
    assert len({tuple(sorted(k)) for k in ej}) == 517, "expected 517 unique gap pairs"
    assert sum(ej.values()) == 1777, "expected EJ weight sum 1777"
    edges = ([{"source": s, "target": t, "kind": "chemical", "weight": w}
              for (s, t), w in sorted(chem.items())]
             + [{"source": s, "target": t, "kind": "electrical", "weight": w}
                for (s, t), w in sorted(ej.items())]
             + [{"source": n, "target": "BWM", "kind": "chemical", "weight": w}
                for n, w in sorted(nmj.items())])
    doc = {
        "id": "c_elegans_varshney2011",
        "species": "caenorhabditis_elegans",
        "version": "2011.1",
        "source": "WormAtlas / White lab notebooks + new EM, via OpenWorm ConnectomeToolbox",
        "publication": "Varshney et al. 2011, PLoS Comput Biol (CC-BY)",
        "license": "CC-BY (PLOS paper); bundled with attribution, see registry",
        "completeness": f"Full somatic wiring excl. pharynx: {len(neurons)} connected neurons + BWM aggregator "
                        f"{len(chem)} directed chemical pairs (union of send/receive views, "
                        f"{len(conflicts)} weight conflicts resolved by max), "
                        f"{len(ej)} directed gap-junction entries, {len(nmj)} NMJ neurons aggregated to BWM. "
                        "Name casing/leading-zero normalised (one source row 'avfl/avfr' merged). "
                        "Nodes carry ids only (no cell-type/region metadata in this matrix).",
        "limitations": "Paper reports 281 matrix nodes; this export lists 280 distinct connected names "
                       "(one node likely connection-free here). Gap-junction weights are contact counts, "
                       "not conductances; no dynamics; pharyngeal neurons excluded; "
                       "receive-view conflicts resolved by max weight.",
        "nodes": [{"id": n} for n in neurons] + [{"id": "BWM", "class": "muscle-aggregator",
                                                  "function": "all neuromuscular junctions aggregated here"}],
        "edges": edges,
    }
    OUT.write_text(json.dumps(doc), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e6:.2f} MB)")
    print(f"neurons={len(doc['nodes'])} chem={len(chem)} elec={len(ej)} nmj_neurons={len(nmj)} "
          f"conflicts={len(conflicts)}")


if __name__ == "__main__":
    main()
