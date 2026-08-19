"""The shipped artifact must load, score sensibly, and agree with PyTorch."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from vfactory.autoencoder import SCHEMA_VERSION, AutoencoderBundle
from vfactory.config import DEFAULT_MACHINE
from vfactory.detector import analyse
from vfactory.features import FEATURE_NAMES, extract
from vfactory.simulator import FaultSpec, VibrationSimulator

ARTIFACT = Path(__file__).resolve().parents[1] / "artifacts" / "model.json"

pytestmark = pytest.mark.skipif(
    not ARTIFACT.exists(), reason="run scripts/train_and_benchmark.py first"
)


@pytest.fixture(scope="module")
def bundle() -> AutoencoderBundle:
    return AutoencoderBundle.load(ARTIFACT)


def test_bundle_shape_matches_the_feature_contract(bundle: AutoencoderBundle):
    assert bundle.feature_names == FEATURE_NAMES
    assert bundle.architecture[0] == bundle.architecture[-1] == len(FEATURE_NAMES)
    assert bundle.latent_dim < len(FEATURE_NAMES), "a latent wider than the input is not a bottleneck"


def test_bundle_round_trips_through_json(bundle: AutoencoderBundle, tmp_path: Path):
    path = bundle.save(tmp_path / "model.json")
    reloaded = AutoencoderBundle.load(path)
    features = extract(VibrationSimulator(seed=2).window(FaultSpec("healthy")), DEFAULT_MACHINE)
    assert reloaded.score_one(features) == pytest.approx(bundle.score_one(features))


def test_unknown_schema_version_is_refused(bundle: AutoencoderBundle):
    payload = bundle.to_json()
    payload["schema_version"] = SCHEMA_VERSION + 99
    with pytest.raises(ValueError, match="schema"):
        AutoencoderBundle.from_json(payload)


def test_healthy_windows_score_below_the_threshold(bundle: AutoencoderBundle):
    sim = VibrationSimulator(seed=101)
    scores = np.array(
        [
            bundle.score_one(extract(sim.window(FaultSpec("healthy")), DEFAULT_MACHINE))
            for _ in range(60)
        ]
    )
    # The threshold is a 99.5th percentile, so a handful of exceedances is
    # expected; a majority would mean the artifact does not match the code.
    assert (scores < bundle.threshold).mean() > 0.9


@pytest.mark.parametrize("mode", ["outer_race", "inner_race", "ball", "imbalance", "looseness"])
def test_severe_faults_are_flagged(bundle: AutoencoderBundle, mode: str):
    sim = VibrationSimulator(seed=202)
    flagged = [
        bundle.score_one(extract(sim.window(FaultSpec(mode, 0.9)), DEFAULT_MACHINE))
        > bundle.threshold
        for _ in range(12)
    ]
    assert sum(flagged) >= 11, f"{mode} at severity 0.9 should be unmissable"


def test_health_index_is_monotone_and_anchored(bundle: AutoencoderBundle):
    assert bundle.health_index(bundle.threshold) == pytest.approx(50.0, abs=0.01)
    assert bundle.health_index(bundle.threshold * 0.1) > 90
    assert bundle.health_index(bundle.threshold * 8) < 1
    grid = [bundle.health_index(bundle.threshold * f) for f in (0.1, 0.5, 1.0, 2.0, 4.0)]
    assert grid == sorted(grid, reverse=True)


def test_numpy_inference_agrees_with_pytorch(bundle: AutoencoderBundle):
    """The exported bundle and the training framework must not drift apart."""
    torch = pytest.importorskip("torch")

    sim = VibrationSimulator(seed=303)
    features = np.stack(
        [extract(sim.window(FaultSpec("outer_race", 0.5)), DEFAULT_MACHINE) for _ in range(8)]
    )
    scaled = bundle.standardise(features)

    x = torch.tensor(scaled, dtype=torch.float64)
    for i, layer in enumerate(bundle.layers):
        x = x @ torch.tensor(layer.weight, dtype=torch.float64).T + torch.tensor(
            layer.bias, dtype=torch.float64
        )
        if i < len(bundle.layers) - 1:
            x = torch.relu(x)

    np.testing.assert_allclose(bundle.reconstruct(scaled), x.numpy(), rtol=1e-9, atol=1e-12)


def test_diagnosis_names_the_right_bearing_fault(bundle: AutoencoderBundle):
    sim = VibrationSimulator(seed=404)
    for mode in ("outer_race", "inner_race"):
        hits = 0
        for _ in range(10):
            verdict, _ = analyse(sim.window(FaultSpec(mode, 0.85)), bundle, DEFAULT_MACHINE)
            hits += verdict.diagnosis == mode
        assert hits >= 8, f"{mode} misdiagnosed {10 - hits}/10 times"


def test_healthy_windows_report_no_diagnosis(bundle: AutoencoderBundle):
    sim = VibrationSimulator(seed=505)
    verdict, _ = analyse(sim.window(FaultSpec("healthy")), bundle, DEFAULT_MACHINE)
    if not verdict.is_anomaly:
        assert verdict.diagnosis == "healthy"
        assert verdict.status in ("normal", "watch")


def test_contributors_are_a_normalised_ranking(bundle: AutoencoderBundle):
    features = extract(
        VibrationSimulator(seed=606).window(FaultSpec("outer_race", 0.9)), DEFAULT_MACHINE
    )
    shares = bundle.top_contributors(features, k=4)
    assert len(shares) == 4
    assert [s for _, s in shares] == sorted([s for _, s in shares], reverse=True)
    assert all(name in FEATURE_NAMES for name, _ in shares)
    assert 0.0 < sum(s for _, s in shares) <= 1.0 + 1e-9


def test_artifact_is_plain_text_not_a_pickle():
    """torch.load on an untrusted .pth executes arbitrary code; JSON does not."""
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert isinstance(payload["layers"], list)
