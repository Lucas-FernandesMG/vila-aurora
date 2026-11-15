import random
from central.analytics import detect_anomalies

rng = random.Random(7)

records = [
    {"id": i, "value": rng.gauss(20, 1), "expected": False}
    for i in range(1000)
]

records.extend(
    {"id": 1000 + i, "value": rng.uniform(35, 45), "expected": True}
    for i in range(50)
)

rng.shuffle(records)

result = detect_anomalies(
    records,
    trees=100,
    contamination=0.05,
    seed=42
)

tp = sum(r["expected"] and r["is_anomaly"] for r in result["results"])
fp = sum(not r["expected"] and r["is_anomaly"] for r in result["results"])
fn = sum(r["expected"] and not r["is_anomaly"] for r in result["results"])
tn = sum(not r["expected"] and not r["is_anomaly"] for r in result["results"])

precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
fpr = fp / (fp + tn) if fp + tn else 0

print("\n=== AVALIACAO RT-16 ===")
print(f"Total de registros: {result['total']}")
print(f"Anomalias identificadas: {result['anomaly_count']}")
print(f"TP: {tp} | FP: {fp} | FN: {fn} | TN: {tn}")
print(f"Precisao: {precision:.2%}")
print(f"Recall: {recall:.2%}")
print(f"F1-score: {f1:.2%}")
print(f"Taxa de falsos positivos: {fpr:.2%}")
