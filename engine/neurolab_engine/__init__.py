"""BrainerLab simulation engine (stdlib only). Pipeline: DATASET -> CONNECTOME -> MODEL
-> SIMULATION -> BEHAVIOR -> ANALYSIS. See docs/models.md."""
from .connectome import Connectome
from .models import MODEL_REGISTRY, get_model
from .simulation import run_simulation
from .analysis import summarise, compare
from .experiment import new_experiment_id, validate_experiment, experiment_to_dict

ENGINE_VERSION = "0.1.0"

__all__ = ["Connectome", "MODEL_REGISTRY", "get_model", "run_simulation",
           "summarise", "compare", "new_experiment_id", "validate_experiment",
           "experiment_to_dict", "ENGINE_VERSION"]
