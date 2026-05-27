"""
Train updated negative price prediction model.
Training: Jan 2024 - Oct 2025
Test: Nov 2025 - May 2026
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

BASE_DIR = Path(__file__).parent.parent
PRICES_PATH = BASE_DIR / "data/entsoe/day_ahead_prices_NL/data.parquet"
KNMI_PATH = BASE_DIR / "data/knmi/uurgeg_260_2021-2030.txt"
OUTPUT_PATH = BASE_DIR / "web/public/data/model_results_2026_05.json"

TRAIN_START = pd.Timestamp("2024-01-01")
TRAIN_END = pd.Timestamp("2025-06-30 23:00:00")
TEST_START = pd.Timestamp("2025-07-01")
TEST_END = pd.Timestamp("2026-05-27")

# Dutch public holidays — includes Labour Day (May 1)
DUTCH_HOLIDAYS = [
    # 2024
    "2024-01-01", "2024-03-31", "2024-04-01", "2024-04-27", "2024-05-01",
    "2024-05-05", "2024-05-09", "2024-05-19", "2024-05-20",
    "2024-12-25", "2024-12-26",
    # 2025
    "2025-01-01", "2025-04-18", "2025-04-19", "2025-04-20", "2025-04-21",
    "2025-04-27", "2025-05-01", "2025-05-05", "2025-05-29",
    "2025-06-08", "2025-06-09", "2025-12-25", "2025-12-26",
    # 2026
    "2026-01-01", "2026-04-03", "2026-04-05", "2026-04-06",
    "2026-04-27", "2026-05-01", "2026-05-05", "2026-05-14",
    "2026-05-24", "2026-05-25", "2026-12-25", "2026-12-26",
]
HOLIDAY_DATES = set(pd.to_datetime(DUTCH_HOLIDAYS).date)


def _parse_knmi_text(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    header_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("# STN") and "YYYYMMDD" in l)
    header = [h.strip() for h in lines[header_idx].replace("#", "").split(",")]
    data = [
        [v.strip() for v in l.split(",")]
        for l in lines[header_idx + 1:]
        if l.strip() and len(l.split(",")) == len(header)
    ]
    df = pd.DataFrame(data, columns=header)
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["datetime_utc"] = (
        pd.to_datetime(df["YYYYMMDD"].astype(int).astype(str), format="%Y%m%d")
        + pd.to_timedelta(df["HH"].astype(int) - 1, unit="h")
    )
    df["wind_speed_ms"] = df["FH"] / 10
    df["global_radiation_jcm2"] = df["Q"]
    df["temperature_c"] = df["T"] / 10
    df["sunshine_hours"] = df["SQ"] / 10
    return df[["datetime_utc", "wind_speed_ms", "global_radiation_jcm2", "temperature_c", "sunshine_hours"]].dropna()


def load_knmi() -> pd.DataFrame:
    import requests

    with open(KNMI_PATH) as f:
        base = _parse_knmi_text(f.read())

    latest = base["datetime_utc"].max()
    fetch_start = (latest + pd.Timedelta(hours=1)).strftime("%Y%m%d%H")
    fetch_end = pd.Timestamp.now().strftime("%Y%m%d%H")

    if fetch_start < fetch_end:
        url = (
            f"https://www.daggegevens.knmi.nl/klimatologie/uurgegevens"
            f"?stns=260&vars=FH:T:SQ:Q&start={fetch_start[:8]}&end={fetch_end[:8]}"
        )
        try:
            resp = requests.get(url, timeout=30)
            if resp.ok and resp.text.strip():
                extra = _parse_knmi_text(resp.text)
                base = pd.concat([base, extra]).drop_duplicates("datetime_utc").sort_values("datetime_utc")
                print(f"  KNMI extended to {base['datetime_utc'].max()}")
        except Exception as e:
            print(f"  Warning: could not fetch recent KNMI data: {e}")

    return base.reset_index(drop=True)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["hour"] = df["datetime_utc"].dt.hour
    df["month"] = df["datetime_utc"].dt.month
    df["dayofweek"] = df["datetime_utc"].dt.dayofweek
    df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
    df["is_holiday"] = df["datetime_utc"].dt.date.map(lambda d: int(d in HOLIDAY_DATES))
    df["is_hot"] = (df["temperature_c"] > 25).astype(int)
    return df


def main():
    print("Loading prices...")
    prices = pd.read_parquet(PRICES_PATH)
    prices["datetime_utc"] = pd.to_datetime(prices["datetime_utc"])
    prices["is_negative"] = (prices["price_eur_mwh"] < 0).astype(int)

    print("Loading KNMI weather data...")
    knmi = load_knmi()

    merged = prices.merge(knmi, on="datetime_utc", how="inner")
    merged = build_features(merged)
    merged = merged.dropna()

    FEATURES = [
        "global_radiation_jcm2", "temperature_c", "is_weekend",
        "wind_speed_ms", "hour", "month", "is_holiday",
        "sunshine_hours", "is_hot",
    ]
    FEATURE_LABELS = [
        "Zonnestraling", "Temperatuur", "Weekend",
        "Windsnelheid", "Uur", "Maand", "Feestdag",
        "Zonne-uur", "Heet (>25°C)",
    ]

    train = merged[(merged["datetime_utc"] >= TRAIN_START) & (merged["datetime_utc"] <= TRAIN_END)]
    test = merged[(merged["datetime_utc"] >= TEST_START) & (merged["datetime_utc"] < TEST_END)]

    print(f"Training: {TRAIN_START.date()} – {TRAIN_END.date()} ({len(train)} uren)")
    print(f"Test:     {TEST_START.date()} – {TEST_END.date()} ({len(test)} uren)")
    print(f"Train negatief: {train['is_negative'].sum()} uur ({train['is_negative'].mean()*100:.1f}%)")
    print(f"Test  negatief: {test['is_negative'].sum()} uur ({test['is_negative'].mean()*100:.1f}%)")

    X_train, y_train = train[FEATURES].values, train["is_negative"].values
    X_test, y_test = test[FEATURES].values, test["is_negative"].values

    print("Training model...")
    model = GradientBoostingClassifier(n_estimators=200, max_depth=4, learning_rate=0.05, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)

    print(f"Accuracy:  {acc:.3f}")
    print(f"Precision: {prec:.3f}")
    print(f"Recall:    {rec:.3f}")
    print(f"F1:        {f1:.3f}")

    # Feature importance
    importances = model.feature_importances_
    feature_importance = [
        {"feature": FEATURE_LABELS[i], "importance": round(float(importances[i]), 4)}
        for i in range(len(FEATURES))
    ]
    feature_importance.sort(key=lambda x: x["importance"], reverse=True)

    # Monthly comparison (test period only)
    test = test.copy()
    test["predicted"] = y_pred
    test["year_month"] = test["datetime_utc"].dt.to_period("M").astype(str)

    MONTH_NL = {
        1: "Jan", 2: "Feb", 3: "Mrt", 4: "Apr", 5: "Mei", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec",
    }

    monthly = []
    for ym, grp in test.groupby("year_month"):
        yr, mo = int(ym.split("-")[0]), int(ym.split("-")[1])
        actual = int(grp["is_negative"].sum())
        predicted = int(grp["predicted"].sum())
        correct = int(((grp["is_negative"] == 1) & (grp["predicted"] == 1)).sum())
        monthly.append({
            "month": ym,
            "month_label": f"{MONTH_NL[mo]} {yr}",
            "actual": actual,
            "predicted": predicted,
            "correct": correct,
        })

    # Distribution shift: May 1 (Labour Day) analysis
    labour_day_hours = test[test["datetime_utc"].dt.date.map(
        lambda d: d.month == 5 and d.day == 1
    )]
    labour_day_neg = int(labour_day_hours["is_negative"].sum())
    labour_day_pred = int(labour_day_hours["predicted"].sum())

    # Hot hours analysis
    train_hot = train[train["is_hot"] == 1]
    test_hot = test[test["is_hot"] == 1]

    result = {
        "model_info": {
            "name": "Gradient Boosting (Uurlijks) — Update 2026-05",
            "type": "classification",
            "train_period": "Jan 2024 – Jun 2025",
            "test_period": "Jul 2025 – Mei 2026",
            "train_hours": len(train),
            "test_hours": len(test),
            "train_negative_pct": round(float(train["is_negative"].mean()) * 100, 1),
            "test_negative_pct": round(float(test["is_negative"].mean()) * 100, 1),
        },
        "metrics": {
            "accuracy": round(acc, 3),
            "precision": round(prec, 3),
            "recall": round(rec, 3),
            "f1": round(f1, 3),
        },
        "confusion_matrix": {
            "true_negatives": int(((y_test == 0) & (y_pred == 0)).sum()),
            "false_positives": int(((y_test == 0) & (y_pred == 1)).sum()),
            "false_negatives": int(((y_test == 1) & (y_pred == 0)).sum()),
            "true_positives": int(((y_test == 1) & (y_pred == 1)).sum()),
        },
        "feature_importance": feature_importance,
        "monthly_comparison": monthly,
        "labour_day": {
            "actual_negative_hours": labour_day_neg,
            "predicted_negative_hours": labour_day_pred,
            "total_hours": len(labour_day_hours),
        },
        "distribution_shift": {
            "description": "Verhouding hete uren (>25°C) met negatieve prijs",
            "train_hot_hours": len(train_hot),
            "train_neg_rate": round(float(train_hot["is_negative"].mean()) * 100, 1) if len(train_hot) > 0 else 0,
            "test_hot_hours": len(test_hot),
            "test_neg_rate": round(float(test_hot["is_negative"].mean()) * 100, 1) if len(test_hot) > 0 else 0,
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
