"""Fetch new data from ENTSOE and update local parquet files."""

from pathlib import Path
import pandas as pd
from utils.entsoe.fetch import fetch_day_ahead_prices, fetch_solar_generation
from utils.entsoe.client import get_entsoe_client

BASE_DIR = Path(__file__).parent.parent
GENERATION_MIX_PATH = BASE_DIR / "data/entsoe/energy_generation_NL/full_mix.parquet"


def _fetch_in_chunks(query_fn, start, end):
    all_data = []
    current_start = start
    while current_start < end:
        current_end = min(current_start + pd.DateOffset(months=3), end)
        try:
            result = query_fn(start=current_start, end=current_end)
            all_data.append(result)
            print(f"  Fetched: {current_start.date()} to {current_end.date()}")
        except Exception as e:
            print(f"  Warning: {current_start.date()} to {current_end.date()}: {e}")
        current_start = current_end
    if not all_data:
        raise ValueError("No data fetched")
    return pd.concat(all_data)


def update_full_mix():
    existing = pd.read_parquet(GENERATION_MIX_PATH)
    existing["datetime_utc"] = pd.to_datetime(existing["datetime_utc"])
    latest = existing["datetime_utc"].max().tz_localize("UTC")
    end = pd.Timestamp.now(tz="Europe/Amsterdam").floor("D").tz_convert("UTC")

    print(f"Fetching full generation mix ({latest.date()} to {end.date()})...")
    client = get_entsoe_client()

    combined = _fetch_in_chunks(
        lambda start, end: client.query_generation("NL", start=start, end=end),
        latest, end,
    )

    if isinstance(combined.columns, pd.MultiIndex):
        # Keep only "Actual Aggregated" columns; drop "Actual Consumption"
        agg_cols = [col for col in combined.columns if col[1] == "Actual Aggregated"]
        combined = combined[agg_cols]
        combined.columns = [src for src, _ in combined.columns]

    combined = combined.resample("H").mean()
    combined.index = combined.index.tz_convert("UTC")

    new_df = combined.reset_index()
    new_df.columns = ["datetime_utc"] + list(new_df.columns[1:])
    new_df["datetime_utc"] = new_df["datetime_utc"].dt.tz_localize(None)

    # Align columns
    for col in existing.columns[1:]:
        if col not in new_df.columns:
            new_df[col] = float("nan")
    new_df = new_df[[c for c in existing.columns if c in new_df.columns]]

    merged = pd.concat([existing, new_df]).drop_duplicates(subset="datetime_utc", keep="last")
    merged = merged.sort_values("datetime_utc").reset_index(drop=True)
    merged.to_parquet(GENERATION_MIX_PATH, index=False)
    print(f"  Full mix updated. Latest: {merged['datetime_utc'].max()}")


if __name__ == "__main__":
    print("=== Updating day-ahead prices ===")
    prices = fetch_day_ahead_prices()
    print(f"  Latest price: {prices['datetime_utc'].max()}")

    print("\n=== Updating solar generation ===")
    solar = fetch_solar_generation()
    print(f"  Latest solar: {solar['datetime_utc'].max()}")

    print("\n=== Updating full generation mix ===")
    update_full_mix()

    print("\nDone. Run scripts/export_data.py to regenerate web data.")
