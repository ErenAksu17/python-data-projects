"""Virtual Factory -- synthetic vibration data and autoencoder anomaly detection.

Public surface kept deliberately small; everything heavier (PyTorch training,
scikit-learn baselines) is imported lazily inside the modules that need it, so
``import vfactory`` in a request handler stays cheap.
"""

from .autoencoder import AutoencoderBundle
from .config import DEFAULT_MACHINE, FAULT_MODES, BearingGeometry, MachineSpec, iso_zone
from .detector import Verdict, analyse, analyse_features
from .features import FEATURE_NAMES, N_FEATURES, extract, extract_batch
from .simulator import FaultSpec, Stream, VibrationSimulator

__version__ = "2.0.0"

__all__ = [
    "DEFAULT_MACHINE",
    "FAULT_MODES",
    "FEATURE_NAMES",
    "N_FEATURES",
    "AutoencoderBundle",
    "BearingGeometry",
    "FaultSpec",
    "MachineSpec",
    "Stream",
    "Verdict",
    "VibrationSimulator",
    "__version__",
    "analyse",
    "analyse_features",
    "extract",
    "extract_batch",
    "iso_zone",
]
