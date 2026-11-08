"""Reproduce the submitted evaluation. Researchers may inspect and modify this copy."""
import argparse
import json
from pathlib import Path
import numpy as np
from detector import auroc, normalize, novelty_scores
from loader import evaluation_groups


def evaluate(split):
    with np.load(Path(__file__).parent / "data" / f"{split}.npz", allow_pickle=False) as data:
        images, bank, labels = data["images"], data["reference"], data["labels"]
        groups = evaluation_groups(data, split)
        baseline = novelty_scores(images, bank)
        candidate = novelty_scores(normalize(images, groups, bank.mean()), bank)
        b, c = auroc(labels, baseline), auroc(labels, candidate)
        return {"split": split, "n": len(labels), "baseline_auc": b,
                "candidate_auc": c, "delta_auc": c - b}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["initial", "reserve"], default="initial")
    args = parser.parse_args()
    print(json.dumps(evaluate(args.split), indent=2))
