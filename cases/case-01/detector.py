"""Prototype nearest-neighbor novelty detector and group brightness adjustment."""
import numpy as np


def make_groups(n, seed, batch_size, evaluator_labels=None):
    rng = np.random.default_rng(seed)
    groups = np.empty(n, dtype=np.int64)
    partitions = ([np.arange(n)] if evaluator_labels is None else
                  [np.flatnonzero(evaluator_labels == label) for label in (0, 1)])
    group = 0
    for partition in partitions:
        order = rng.permutation(partition)
        for start in range(0, len(order), batch_size):
            groups[order[start:start + batch_size]] = group
            group += 1
    return groups


def normalize(images, groups, reference_brightness):
    adjusted = images.copy()
    for group in np.unique(groups):
        selected = groups == group
        adjusted[selected] -= images[selected].mean() - reference_brightness
    return adjusted


def novelty_scores(images, reference_images, neighbors=3):
    distances = np.maximum(
        (images * images).sum(axis=1)[:, None]
        + (reference_images * reference_images).sum(axis=1)[None, :]
        - 2 * images @ reference_images.T, 0.0)
    nearest = np.partition(distances, neighbors - 1, axis=1)[:, :neighbors]
    return np.sqrt(nearest).mean(axis=1)


def auroc(labels, scores):
    positive, negative = scores[labels == 1], scores[labels == 0]
    if not len(positive) or not len(negative):
        raise ValueError("AUROC requires familiar and unfamiliar samples")
    differences = positive[:, None] - negative[None, :]
    return float(np.mean((differences > 0) + 0.5 * (differences == 0)))
