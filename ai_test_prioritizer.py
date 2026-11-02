"""
ai_test_prioritizer.py -- the "AI" in "AI-based Automated Testing Framework".
Trains a small ML model on a log of past test executions and predicts a
"risk score" for each test, so the riskiest tests run first.
Run: python tests/ai_test_prioritizer.py
"""
import csv
import os
import random

import pandas as pd
from sklearn.ensemble import RandomForestClassifier

HISTORY_FILE = os.path.join(os.path.dirname(__file__), "test_history.csv")
COLUMNS = ["test_name", "lines_changed", "past_fail_count", "avg_duration_ms", "failed"]


def seed_synthetic_history(n_runs=40, seed=42):
    random.seed(seed)
    test_names = [
        "test_classifies_streetlight_issue", "test_classifies_electrical_hazard",
        "test_classifies_water_leakage", "test_classifies_pothole",
        "test_critical_priority_for_fire_or_shock_risk", "test_finds_duplicate_within_radius",
        "test_register_new_user_success", "test_worker_sees_only_own_department_complaints",
        "test_admin_dashboard_blocked_for_citizen", "test_submit_valid_complaint_success",
        "test_dropdown_category_overrides_nlp_guess", "test_voice_note_upload_accepted",
        "test_notifications_created_on_status_update", "test_analytics_accessible_to_admin",
    ]
    flaky_bias = {
        "test_worker_sees_only_own_department_complaints": 0.35,
        "test_voice_note_upload_accepted": 0.25,
        "test_notifications_created_on_status_update": 0.20,
        "test_finds_duplicate_within_radius": 0.15,
    }
    rows = []
    for _ in range(n_runs):
        name = random.choice(test_names)
        lines_changed = random.randint(0, 40)
        fail_prob = flaky_bias.get(name, 0.05) + (lines_changed / 400)
        failed = 1 if random.random() < fail_prob else 0
        rows.append({
            "test_name": name, "lines_changed": lines_changed,
            "past_fail_count": random.randint(0, 5),
            "avg_duration_ms": random.randint(20, 800), "failed": failed,
        })
    with open(HISTORY_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Seeded {n_runs} synthetic history rows -> {HISTORY_FILE}")


def train_and_rank():
    if not os.path.exists(HISTORY_FILE):
        print("No history file found -- seeding synthetic data for a first demo run.")
        seed_synthetic_history()

    df = pd.read_csv(HISTORY_FILE)
    agg = df.groupby("test_name").agg(
        avg_lines_changed=("lines_changed", "mean"),
        total_past_fails=("past_fail_count", "max"),
        avg_duration_ms=("avg_duration_ms", "mean"),
        historical_fail_rate=("failed", "mean"),
    ).reset_index()

    X = agg[["avg_lines_changed", "total_past_fails", "avg_duration_ms"]]
    y = (agg["historical_fail_rate"] > agg["historical_fail_rate"].median()).astype(int)

    model = RandomForestClassifier(n_estimators=100, random_state=0)
    model.fit(X, y)
    agg["risk_score"] = model.predict_proba(X)[:, 1]
    ranked = agg.sort_values("risk_score", ascending=False)

    print("\nAI-prioritized test run order (highest risk first):\n")
    print(f"{'Rank':<5}{'Test':<50}{'Risk score':<12}{'Hist. fail rate'}")
    for i, row in enumerate(ranked.itertuples(), start=1):
        print(f"{i:<5}{row.test_name:<50}{row.risk_score:<12.2f}{row.historical_fail_rate:.2f}")
    return ranked["test_name"].tolist()


if __name__ == "__main__":
    order = train_and_rank()
    print("\nSuggested pytest command to run just the top 3 highest-risk tests first:")
    print("  pytest " + " ".join(f"-k {t}" for t in order[:3]))
