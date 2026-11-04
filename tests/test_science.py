"""Verify the published evidence directly; no case-generation sources are needed."""
import importlib.util
import json
import os
import subprocess
import sys
from unittest.mock import patch

import numpy as np
import pytest

from judgment_reserve import cli
from judgment_reserve.util import ROOT, CASE_IDS, manifest, read_json


def case_code(case):
    modules = []
    # Each loader imports its own detector; keep these imports out of other tests.
    with patch.dict(sys.modules), patch.object(sys, "dont_write_bytecode", True):
        for name in ("detector", "loader"):
            spec = importlib.util.spec_from_file_location(name, ROOT / "cases" / case / f"{name}.py")
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            modules.append(module)
    return modules


def case_data(case, split):
    with np.load(ROOT / "cases" / case / "data" / f"{split}.npz", allow_pickle=False) as data:
        return dict(data)


def metrics(detector, data, groups):
    images, bank, labels = data["images"], data["reference"], data["labels"]
    baseline = detector.auroc(labels, detector.novelty_scores(images, bank))
    scores = detector.novelty_scores(detector.normalize(images, groups, bank.mean()), bank)
    candidate = detector.auroc(labels, scores)
    return {"baseline_auc": baseline, "candidate_auc": candidate, "delta_auc": candidate - baseline}


@pytest.mark.parametrize("case,key,test", [
    ("case-01", "leaky", "label_separated"),
    ("case-02", "legitimate", "deployment_matched_sessions")])
@pytest.mark.parametrize("split", ["initial", "reserve"])
def test_supplied_case_reproduces_recorded_scores(case, key, test, split):
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1")
    run = subprocess.run([sys.executable, "-B", str(ROOT / "cases" / case / "run.py"),
                          "--split", split], check=True, capture_output=True, text=True, env=env)
    got = json.loads(run.stdout)
    expected = read_json(ROOT / "reference/results.json")[key][split][test]
    for metric, value in expected.items():
        assert got[metric] == pytest.approx(value, abs=1e-12)
    assert got["delta_auc"] > (.1 if case == "case-01" else .07)
    if split == "initial":
        assert read_json(ROOT / "cases" / case / "preliminary.json") == expected


@pytest.mark.parametrize("case", CASE_IDS)
def test_prediction_label_intervention_uses_actual_case_loader(case):
    detector, loader = case_code(case)
    data = case_data(case, "initial")
    changed = dict(data, labels=np.random.default_rng(91).permutation(data["labels"]))

    def predict(inputs):
        groups = loader.evaluation_groups(inputs, "initial")
        return detector.novelty_scores(
            detector.normalize(inputs["images"], groups, inputs["reference"].mean()),
            inputs["reference"])

    difference = float(np.max(np.abs(predict(data) - predict(changed))))
    expected = read_json(ROOT / "reference/controls.json")["label_intervention"][case]
    assert difference == pytest.approx(expected["max_absolute_score_change"], abs=1e-12)
    assert difference > 1 if case == "case-01" else difference == 0


@pytest.mark.parametrize("case", CASE_IDS)
@pytest.mark.parametrize("split", ["initial", "reserve"])
def test_mixed_grouping_control_on_the_same_images(case, split):
    detector, _ = case_code(case)
    data = case_data(case, split)
    offset = 0 if split == "initial" else 1000
    size, key, test = (128, "leaky", "deployment_matched_mixed") if case == "case-01" else (
        32, "legitimate", "mixed_across_sessions")
    groups = detector.make_groups(len(data["labels"]), offset + 24, size)
    got = metrics(detector, data, groups)
    expected = read_json(ROOT / "reference/results.json")[key][split][test]
    assert got == pytest.approx(expected, abs=1e-12)
    if case == "case-01":
        assert got["delta_auc"] < 0


def test_fixed_evidence_counterfactual_retains_the_same_measurement():
    detector, loader = case_code("case-02")
    data = case_data("case-02", "reserve")
    got = metrics(detector, data, loader.evaluation_groups(data, "reserve"))
    expected = read_json(ROOT / "reference/controls.json")["fixed_evidence_contract_counterfactual"]
    assert got == pytest.approx(expected["results"], abs=1e-12)


@pytest.mark.parametrize("case", CASE_IDS)
def test_published_splits_are_disjoint(case):
    a, b = case_data(case, "initial"), case_data(case, "reserve")
    assert not set(a["sample_ids"]) & set(b["sample_ids"])
    np.testing.assert_array_equal(a["reference"], b["reference"])
    if case == "case-02":
        assert not set(a["session_ids"]) & set(b["session_ids"])
        for data in (a, b):
            assert all(len(set(data["labels"][data["session_ids"] == s])) == 2
                       for s in np.unique(data["session_ids"]))


@pytest.mark.parametrize("case", CASE_IDS)
def test_metric_known_rankings_and_ties(case):
    detector, _ = case_code(case)
    # Nine positive/negative comparisons give six wins, counting ties as half.
    labels = np.array([0, 0, 1, 1, 0, 1])
    assert detector.auroc(labels, np.array([.1, .3, .3, .4, .9, .9])) == pytest.approx(2 / 3)
    assert detector.auroc(labels, np.ones(6)) == .5
    assert detector.auroc(labels, labels) == 1
    assert detector.auroc(labels, 1 - labels) == 0


def test_frozen_evidence_matches_manifest_and_contains_no_reference_material():
    source = read_json(ROOT / "reference/source-manifest.json")
    assert manifest(ROOT / "cases") == source["evidence"]
    for case in CASE_IDS:
        paths = set(manifest(ROOT / "cases" / case))
        assert paths == {"README.md", "request.md", "deployment.md", "loader.py", "detector.py", "run.py",
                         "preliminary.json", "data/initial.npz", "data/reserve.npz"}


def test_check_needs_only_the_published_case_manifest(repo, monkeypatch):
    monkeypatch.setattr(cli, "ROOT", repo)
    assert not (repo / "judgment_reserve_cases.py").exists()
    cli.run(cli.parser().parse_args(["check"]))
    (repo / "cases/case-01/run.py").write_text("# Changed evidence\n")
    with pytest.raises(ValueError, match="Case files differ"):
        cli.run(cli.parser().parse_args(["check"]))
