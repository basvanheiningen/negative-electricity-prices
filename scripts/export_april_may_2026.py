"""
Compute data for the April/May 2026 extreme negative price case study.
"""

import json
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent
PRICES_PATH = BASE_DIR / "data/entsoe/day_ahead_prices_NL/data.parquet"
MIX_PATH = BASE_DIR / "data/entsoe/energy_generation_NL/full_mix.parquet"
KNMI_PATH = BASE_DIR / "data/knmi/uurgeg_260_2021-2030.txt"
OUTPUT_PATH = BASE_DIR / "web/public/data/april_may_2026.json"


def load_knmi() -> pd.DataFrame:
    with open(KNMI_PATH) as f:
        lines = f.readlines()

    header_idx = next(i for i, l in enumerate(lines) if l.strip().startswith("# STN") and "YYYYMMDD" in l)
    header = [c.strip() for c in lines[header_idx].replace("#", "").split(",")]

    rows_25, rows_7 = [], []
    for l in lines[header_idx + 1:]:
        if not l.strip() or l.strip().startswith("#"):
            continue
        vals = [v.strip() for v in l.split(",")]
        if len(vals) == len(header):
            rows_25.append(vals)
        elif len(vals) == 7:
            rows_7.append(vals)

    dfs = []
    if rows_25:
        df = pd.DataFrame(rows_25, columns=header)
        for c in df.columns: df[c] = pd.to_numeric(df[c], errors="coerce")
        df["datetime_utc"] = pd.to_datetime(df["YYYYMMDD"].astype(int).astype(str), format="%Y%m%d") + pd.to_timedelta(df["HH"].astype(int) - 1, unit="h")
        df["wind_ms"] = df["FH"] / 10; df["rad"] = df["Q"]; df["sun"] = df["SQ"].clip(lower=0) / 10
        dfs.append(df[["datetime_utc", "wind_ms", "rad", "sun"]])

    if rows_7:
        df7 = pd.DataFrame(rows_7, columns=["STN", "YYYYMMDD", "HH", "FH", "T", "SQ", "Q"])
        for c in df7.columns: df7[c] = pd.to_numeric(df7[c], errors="coerce")
        df7["datetime_utc"] = pd.to_datetime(df7["YYYYMMDD"].astype(int).astype(str), format="%Y%m%d") + pd.to_timedelta(df7["HH"].astype(int) - 1, unit="h")
        df7["wind_ms"] = df7["FH"] / 10; df7["rad"] = df7["Q"]; df7["sun"] = df7["SQ"].clip(lower=0) / 10
        dfs.append(df7[["datetime_utc", "wind_ms", "rad", "sun"]])

    return pd.concat(dfs).drop_duplicates("datetime_utc").sort_values("datetime_utc").reset_index(drop=True)


def day_stats(prices, mix, knmi, date_str, label):
    dt = pd.Timestamp(date_str)
    p = prices[prices.index.date == dt.date()]
    m = mix[mix.index.date == dt.date()]
    k = knmi[knmi["datetime_utc"].dt.date == dt.date()]

    wind_cols = [c for c in ["Wind Offshore", "Wind Onshore"] if c in m.columns]
    wind_mw = round(float(m[wind_cols].sum(axis=1).mean()), 0) if wind_cols else 0
    solar_mw = round(float(m["Solar"].mean()), 0) if "Solar" in m.columns else 0
    gas_mw = round(float(m["Fossil Gas"].mean()), 0) if "Fossil Gas" in m.columns else 0
    total_mw = round(float(m.sum(axis=1).mean()), 0) if len(m) else 0
    neg_hours = int((p["price_eur_mwh"] < 0).sum())
    min_price = round(float(p["price_eur_mwh"].min()), 1)
    avg_price = round(float(p["price_eur_mwh"].mean()), 1)
    radiation = round(float(k["rad"].sum()), 0) if len(k) else 0
    sunshine_h = round(float(k["sun"].sum()), 1) if len(k) else 0
    wind_ms = round(float(k["wind_ms"].mean()), 1) if len(k) else 0

    # Hourly price profile
    hourly = []
    for _, row in p.iterrows():
        hourly.append({"hour": row.name.hour, "price": round(float(row["price_eur_mwh"]), 1)})

    return {
        "date": date_str, "label": label,
        "neg_hours": neg_hours, "min_price": min_price, "avg_price": avg_price,
        "wind_mw": wind_mw, "solar_mw": solar_mw, "gas_mw": gas_mw, "total_mw": total_mw,
        "radiation_jcm2": radiation, "sunshine_hours": sunshine_h, "wind_ms": wind_ms,
        "hourly_prices": hourly,
    }


def main():
    prices = pd.read_parquet(PRICES_PATH)
    prices["datetime_utc"] = pd.to_datetime(prices["datetime_utc"])
    prices = prices.set_index("datetime_utc")

    mix = pd.read_parquet(MIX_PATH)
    mix["datetime_utc"] = pd.to_datetime(mix["datetime_utc"])
    mix = mix.set_index("datetime_utc")

    knmi = load_knmi()

    extreme_days = [
        ("2026-04-25", "25 apr 2026 (zat)"),
        ("2026-04-26", "26 apr 2026 (zon)"),
        ("2026-05-01", "1 mei 2026 (feestdag)"),
    ]
    reference_days = [
        ("2025-04-27", "27 apr 2025 (Koningsdag)"),
        ("2025-05-01", "1 mei 2025 (feestdag)"),
    ]

    extreme_stats = [day_stats(prices, mix, knmi, d, l) for d, l in extreme_days]
    reference_stats = [day_stats(prices, mix, knmi, d, l) for d, l in reference_days]

    # Key factor comparison: extreme (Apr 26 + May 1 average) vs reference
    def avg_stat(days_stats, key):
        return round(sum(d[key] for d in days_stats) / len(days_stats), 1)

    factors = [
        {
            "factor": "Windenergie",
            "extreme": avg_stat(extreme_stats, "wind_mw"),
            "reference": avg_stat(reference_stats, "wind_mw"),
            "unit": "MW",
        },
        {
            "factor": "Zonnestraling",
            "extreme": avg_stat(extreme_stats, "radiation_jcm2"),
            "reference": avg_stat(reference_stats, "radiation_jcm2"),
            "unit": "J/cm²",
        },
        {
            "factor": "Gasproductie",
            "extreme": avg_stat(extreme_stats, "gas_mw"),
            "reference": avg_stat(reference_stats, "gas_mw"),
            "unit": "MW",
        },
        {
            "factor": "Windsnelheid",
            "extreme": avg_stat(extreme_stats, "wind_ms"),
            "reference": avg_stat(reference_stats, "wind_ms"),
            "unit": "m/s",
        },
    ]
    for f in factors:
        ref = f["reference"]
        ext = f["extreme"]
        f["change_pct"] = round((ext - ref) / ref * 100, 1) if ref else 0

    result = {
        "extreme_days": extreme_stats,
        "reference_days": reference_stats,
        "key_factors": factors,
        "summary": {
            "worst_price": -498.4,
            "worst_date": "1 mei 2026",
            "total_extreme_neg_hours": sum(d["neg_hours"] for d in extreme_stats),
        },
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
