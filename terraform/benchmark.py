#!/usr/bin/env python3
"""
Lab 16 - LightGBM Benchmark on Credit Card Fraud Detection dataset
Default CPU track. Measures: load time, training time, metrics, inference latency/throughput.
"""
import json
import platform
import time

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

DATA_PATH = "/home/ubuntu/ml-benchmark/creditcard.csv"
OUT_PATH = "/home/ubuntu/ml-benchmark/benchmark_result.json"

results = {"instance_type": "t3.micro", "python": platform.python_version()}

# 1. Load dataset + measure load time
print("[1/5] Loading dataset ...")
t0 = time.perf_counter()
df = pd.read_csv(DATA_PATH)
# Downcast float64 -> float32 to fit on 1GB-RAM instance
for c in df.columns:
    if c != "Class":
        df[c] = df[c].astype(np.float32)
t_load = time.perf_counter() - t0
results["load_data_time_sec"] = round(t_load, 3)
results["rows"] = int(len(df))
results["cols"] = int(df.shape[1])
print(f"    Loaded {results['rows']} rows x {results['cols']} cols in {t_load:.3f}s")

X = df.drop(columns=["Class"])
y = df["Class"].astype(int)
del df

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

dtrain = lgb.Dataset(X_train, label=y_train)
dvalid = lgb.Dataset(X_test, label=y_test, reference=dtrain)

# 2. Train LightGBM + measure training time
print("[2/5] Training LightGBM ...")
params = {
    "objective": "binary",
    "metric": "auc",
    "boosting_type": "gbdt",
    "num_leaves": 31,
    "learning_rate": 0.05,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "verbose": -1,
    "num_threads": 2,
    "force_row_wise": True,
}
t0 = time.perf_counter()
model = lgb.train(
    params,
    dtrain,
    num_boost_round=1000,
    valid_sets=[dvalid],
    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
)
t_train = time.perf_counter() - t0
results["training_time_sec"] = round(t_train, 3)
results["best_iteration"] = int(model.best_iteration)
print(f"    Training done in {t_train:.3f}s, best_iteration={model.best_iteration}")

# 3-4. Evaluate
print("[3/5] Evaluating ...")
y_prob = model.predict(X_test, num_iteration=model.best_iteration)
y_pred = (y_prob >= 0.5).astype(int)
results["auc_roc"] = round(float(roc_auc_score(y_test, y_prob)), 6)
results["accuracy"] = round(float(accuracy_score(y_test, y_pred)), 6)
results["f1_score"] = round(float(f1_score(y_test, y_pred)), 6)
results["precision"] = round(float(precision_score(y_test, y_pred)), 6)
results["recall"] = round(float(recall_score(y_test, y_pred)), 6)

# 5. Inference latency (1 row, avg of 20) & throughput (1000 rows)
print("[4/5] Measuring inference ...")
sample1 = X_test.iloc[:1]
t0 = time.perf_counter()
for _ in range(20):
    model.predict(sample1, num_iteration=model.best_iteration)
lat_ms = (time.perf_counter() - t0) / 20 * 1000
results["inference_latency_1row_ms"] = round(lat_ms, 3)

batch = X_test.iloc[:1000]
t0 = time.perf_counter()
model.predict(batch, num_iteration=model.best_iteration)
thr = time.perf_counter() - t0
results["inference_throughput_1000rows_sec"] = round(thr, 4)
results["inference_throughput_rows_per_sec"] = round(1000 / thr, 1)

# 6. Save results
print("[5/5] Saving results ...")
print(json.dumps(results, indent=2))
with open(OUT_PATH, "w") as f:
    json.dump(results, f, indent=2)
print(f"DONE. Results saved to {OUT_PATH}")