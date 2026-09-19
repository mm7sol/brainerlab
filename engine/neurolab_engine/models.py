"""MODEL stage: plugin registry. Params are modelling choices (source field says so),
never invented biology. Versions bump on semantic change."""
from . import connectome as _c  # noqa: F401  (keeps stage import explicit)


class BaseModel:
    name = "base"
    version = "v1"
    defaults = {}
    doc = {}

    def __init__(self, params=None):
        self.params = dict(self.defaults)
        if params:
            unknown = sorted(set(params) - set(self.defaults))
            if unknown:
                raise ValueError(f"unknown parameters for model '{self.name}': {unknown}")
            self.params.update(params)

    def step(self, state, t, ext, incoming, rng):
        raise NotImplementedError


class IntegrateAndFire(BaseModel):
    name = "iaf"
    version = "v1"
    defaults = {"tau_ms": 20.0, "v_rest": -65.0, "v_reset": -65.0, "v_thr": -50.0,
                "w_scale": 8.0, "noise": 0.0, "refractory_ms": 2.0}
    doc = {"tau_ms": "membrane time constant, ms (modelling choice)",
           "v_rest": "mV (modelling choice)", "v_reset": "mV (modelling choice)",
           "v_thr": "mV (modelling choice)",
           "w_scale": "mV per synapse-count unit (modelling choice; default 8.0 chosen so a "
                      "sustained single-input drive can cross threshold in the unweighted "
                      "reference circuit — demo calibration, not biology)",
           "noise": "gaussian V noise sigma per step, mV (0 = deterministic)",
           "refractory_ms": "ms (modelling choice)"}

    def step(self, st, t, ext, incoming, rng):
        p = self.params
        if st.get("ref", 0) > 0:
            st["ref"] -= 1
            st["V"] = p["v_reset"]
            return False
        v = st.get("V", p["v_rest"])
        v += (incoming * p["w_scale"] + ext) / p["tau_ms"]
        if p["noise"]:
            v += rng.gauss(0.0, p["noise"])
        if v >= p["v_thr"]:
            st["V"] = p["v_reset"]
            st["ref"] = int(p["refractory_ms"])
            return True
        st["V"] = v
        return False


class LeakyIF(IntegrateAndFire):
    name = "lif"
    version = "v1"
    defaults = {"tau_ms": 20.0, "v_rest": -65.0, "v_reset": -65.0, "v_thr": -50.0,
                "w_scale": 8.0, "noise": 0.0, "refractory_ms": 2.0, "C": 1.0}
    doc = {"C": "arbitrary capacitance units (modelling choice)"}

    def step(self, st, t, ext, incoming, rng):
        p = self.params
        if st.get("ref", 0) > 0:
            st["ref"] -= 1
            st["V"] = p["v_reset"]
            return False
        v = st.get("V", p["v_rest"])
        v += (-(v - p["v_rest"]) / p["tau_ms"] + (incoming * p["w_scale"] + ext) / p["C"])
        if p["noise"]:
            v += rng.gauss(0.0, p["noise"])
        if v >= p["v_thr"]:
            st["V"] = p["v_reset"]
            st["ref"] = int(p["refractory_ms"])
            return True
        st["V"] = v
        return False


class Propagation(BaseModel):
    """Discrete cascade (abstract topology spread, NOT biophysical)."""
    name = "propagation"
    version = "v1"
    defaults = {"base_p": 0.3, "w_scale": 0.2, "cooldown": 3, "noise": 0.0}
    doc = {"base_p": "base transmission probability (modelling choice)",
           "w_scale": "per-weight gain (modelling choice)",
           "cooldown": "steps refractory after firing (modelling choice)",
           "noise": "spontaneous activation prob. per step (0 = deterministic)"}

    def step(self, st, t, ext, incoming, rng):
        p = self.params
        if st.get("ref", 0) > 0:
            st["ref"] -= 1
            return False
        prob = max(0.0, min(1.0, p["base_p"] * max(incoming, 0.0) * p["w_scale"] + ext + p["noise"]))
        if ext > 0 and incoming <= 0 and p["noise"] == 0:
            fire = ext >= 1.0
        else:
            fire = rng.random() < prob or ext >= 1.0
        if fire:
            st["ref"] = int(p["cooldown"])
            return True
        return False


MODEL_REGISTRY = {m.name: m for m in (IntegrateAndFire, LeakyIF, Propagation)}


def get_model(name, params=None):
    try:
        cls = MODEL_REGISTRY[name]
    except KeyError:
        raise ValueError(f"unknown model '{name}'. Available: {sorted(MODEL_REGISTRY)}")
    return cls(params)
