"""CONNECTOME stage: directed multigraph over dataset nodes/edges (stdlib only)."""
from collections import defaultdict


class Connectome:
    def __init__(self, dataset):
        self.dataset_id = dataset.get("id")
        self.nodes = {n["id"]: n for n in dataset.get("nodes", [])}
        self.edges = list(dataset.get("edges", []))
        self._out = defaultdict(list)
        self._in = defaultdict(list)
        for e in self.edges:
            self._out[e["source"]].append(e)
            self._in[e["target"]].append(e)

    def get(self, nid):
        return self.nodes.get(nid)

    def out_edges(self, nid, kind="all"):
        return [e for e in self._out.get(nid, []) if kind == "all" or e.get("kind") == kind]

    def in_edges(self, nid, kind="all"):
        return [e for e in self._in.get(nid, []) if kind == "all" or e.get("kind") == kind]

    def degree(self, nid, kind="all"):
        return {"in": len(self.in_edges(nid, kind)), "out": len(self.out_edges(nid, kind))}

    def hub_scores(self, kind="all", top=10):
        scored = [(n, len(self.in_edges(n, kind)) + len(self.out_edges(n, kind)))
                  for n in self.nodes]
        scored.sort(key=lambda t: (-t[1], t[0]))
        return [{"neuron": n, "degree": d} for n, d in scored[:top]]

    def subgraph(self, seeds, depth=1, direction="both", kind="all", max_nodes=400):
        seen, frontier = set(), list(seeds)
        for s in seeds:
            if s in self.nodes:
                seen.add(s)
        for _ in range(max(depth, 0)):
            nxt = []
            for n in frontier:
                nb = []
                if direction in ("out", "both"):
                    nb += [e["target"] for e in self.out_edges(n, kind)]
                if direction in ("in", "both"):
                    nb += [e["source"] for e in self.in_edges(n, kind)]
                for m in nb:
                    if m in self.nodes and m not in seen:
                        seen.add(m)
                        nxt.append(m)
                        if len(seen) >= max_nodes:
                            break
                if len(seen) >= max_nodes:
                    break
            frontier = nxt
        edges = [e for e in self.edges if e["source"] in seen and e["target"] in seen
                 and (kind == "all" or e.get("kind") == kind)]
        return {"nodes": [self.nodes[n] for n in sorted(seen)], "edges": edges,
                "truncated": len(seen) >= max_nodes}
