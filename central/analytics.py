"""Detecção de anomalias por Isolation Forest simplificado, sem dependências externas."""
import math
import random


def _average_path_length(n):
    if n <= 1:
        return 0.0
    harmonic = sum(1.0 / k for k in range(1, n))
    return 2.0 * harmonic - (2.0 * (n - 1) / n)


def _build_tree(values, depth, max_depth, rng):
    size = len(values)
    if size <= 1 or depth >= max_depth or min(values) == max(values):
        return ("leaf", size)

    lower, upper = min(values), max(values)
    split = rng.uniform(lower, upper)
    left = [v for v in values if v < split]
    right = [v for v in values if v >= split]

    if not left or not right:
        return ("leaf", size)

    return (
        "node",
        split,
        _build_tree(left, depth + 1, max_depth, rng),
        _build_tree(right, depth + 1, max_depth, rng),
    )


def _path_length(tree, value, depth=0):
    if tree[0] == "leaf":
        return depth + _average_path_length(tree[1])
    _, split, left, right = tree
    return _path_length(left if value < split else right, value, depth + 1)


def detect_anomalies(records, trees=64, sample_size=128,
                     contamination=0.05, seed=42):
    """Retorna leituras ordenadas por score; scores maiores indicam anomalia."""
    if not 0 < contamination <= 0.20:
        raise ValueError("contamination deve estar entre 0 e 0.20")
    if trees < 16:
        raise ValueError("São necessárias pelo menos 16 árvores")

    valid = []
    for record in records:
        try:
            value = float(record["value"])
            if math.isfinite(value):
                valid.append((record, value))
        except (KeyError, TypeError, ValueError):
            continue

    if len(valid) < 8:
        return {
            "model": "Isolation Forest simplificado (stdlib)",
            "status": "insufficient_data",
            "message": "São necessárias pelo menos 8 leituras num?ricas.",
            "total": len(valid),
            "anomaly_count": 0,
            "results": [],
        }

    values = [value for _, value in valid]
    size = min(sample_size, len(values))
    max_depth = math.ceil(math.log2(size))
    rng = random.Random(seed)
    forest = []

    for _ in range(trees):
        sample = rng.sample(values, size)
        forest.append(_build_tree(sample, 0, max_depth, rng))

    normalizer = _average_path_length(size)
    scored = []

    for record, value in valid:
        average_path = sum(
            _path_length(tree, value) for tree in forest
        ) / len(forest)
        score = 2 ** (-average_path / normalizer) if normalizer else 0.5
        scored.append((score, record))

    anomaly_count = max(1, math.ceil(len(scored) * contamination))
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)
    anomaly_ids = {id(record) for _, record in ranked[:anomaly_count]}

    results = []
    for score, record in ranked:
        results.append({
            **record,
            "anomaly_score": round(score, 6),
            "is_anomaly": id(record) in anomaly_ids,
        })

    return {
        "model": "Isolation Forest simplificado (stdlib)",
        "status": "ok",
        "total": len(results),
        "anomaly_count": anomaly_count,
        "contamination": contamination,
        "trees": trees,
        "sample_size": size,
        "results": results,
    }
