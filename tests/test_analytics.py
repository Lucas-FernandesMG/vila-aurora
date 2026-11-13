import random

from central.analytics import detect_anomalies


def test_isolation_forest_identifies_extreme_value():
    rng = random.Random(7)
    records = [
        {"id": i, "value": rng.gauss(20, 1)}
        for i in range(200)
    ]
    records.append({"id": 999, "value": 1000.0})

    result = detect_anomalies(records, trees=100, contamination=0.05)

    assert result["status"] == "ok"
    assert result["total"] == 201
    assert result["anomaly_count"] > 0
    extreme = next(item for item in result["results"] if item["id"] == 999)
    assert extreme["is_anomaly"] is True


def test_insufficient_data_is_reported():
    result = detect_anomalies([{"value": 1}, {"value": 2}])
    assert result["status"] == "insufficient_data"
    assert result["anomaly_count"] == 0


def test_invalid_values_are_ignored():
    records = [{"value": float(i)} for i in range(10)]
    records.extend([{"value": "invalid"}, {"other": 1}])
    result = detect_anomalies(records)
    assert result["total"] == 10


def test_invalid_contamination_is_rejected():
    try:
        detect_anomalies([{"value": i} for i in range(10)], contamination=0.9)
        assert False, "Esperava ValueError"
    except ValueError:
        pass
