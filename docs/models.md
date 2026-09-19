# Models (engine v0.1.0)

All models: discrete-time, dt = 1 ms, current-based, seeded (`random.Random(seed)`).
No parameter pretends to be a biological measurement unless `source` says so.

## `iaf` — integrate-and-fire (v1)

- `tau_ms=20.0` (modelling choice), `v_rest=-65.0 mV`, `v_reset=-65.0 mV`,
  `v_thr=-50.0 mV`, `w_scale=8.0 mV/synapse-unit`, `noise=0.0`, `refractory_ms=2.0`
- update: `V += dt*((I_syn + I_ext + noise)/tau)` ; spike if `V>=thr` → reset, refractory.
- `w_scale` default is a **demo calibration** (lets a sustained unit-weight drive cross
  threshold in the unweighted reference circuit), not a biological measurement.

## `lif` — leaky integrate-and-fire (v1, default)

- adds leak: `V += dt*(-(V-rest)/tau + (I_syn+I_ext)/C)`, `C=1.0` (arbitrary units).
- same thresholds/reset/refractory as `iaf`. Reference experiment uses `lif`.

## `propagation` — discrete cascade (v1)

- Abstract spread model for topology demos: active nodes excite neighbours with probability
  `p = clip(base_p * weight_or_1 * w_scale)`; `steps` = simulation ms; refractory via `cooldown`.
- Params: `base_p=0.3`, `w_scale=0.2`, `cooldown=3`, `noise=0.0`. **Not biophysical.**

## Stimulus & virtual manipulations (model-only!)

- stimulus: `{neuron, t_start_ms, t_end_ms, amplitude}` current injection.
- manipulations: `silence` (clamp V=rest), `force_spike`/`activate` (drive above threshold),
  `scale_weights {edge_filter, factor}`, `remove_edges [{source,target,kind}]`.
- Always labelled **Virtual manipulation** in UI/reports.

## Behavioural readout

Toy `forward_bias = spikes(AVB,PVCL,PVCR,DB,VB) − spikes(AVA,AVD,DA,VA)` normalised.
Reported as **model behaviour proxy**, never animal behaviour.
