from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from utils.entsoe.client import get_entsoe_client

DATA_DIR = Path("data/entsoe")
PRICES_DIR = DATA_DIR / "day_ahead_prices_NL"
GENERATION_DIR = DATA_DIR / "energy_generation_NL"


def _read_watermark(directory: Path) -> pd.Timestamp | None:
    """Read the watermark (latest fetched timestamp) from a data directory."""
    wm_file = directory / "watermark.json"
    if not wm_file.exists():
        return None
    with open(wm_file) as f:
        data = json.load(f)
    return pd.Timestamp(data["latest_utc"], tz="UTC")


def _write_watermark(directory: Path, latest_utc: pd.Timestamp) -> None:
    """Write the watermark (latest fetched timestamp) to a data directory."""
    wm_file = directory / "watermark.json"
    with open(wm_file, "w") as f:
        json.dump({"latest_utc": str(latest_utc)}, f, indent=2)


def _fetch_in_chunks(query_fn, start: pd.Timestamp, end: pd.Timestamp, **kwargs) -> pd.Series | pd.DataFrame:
    """Fetch data from ENTSOE in 3-month chunks to avoid API limits."""
    all_data = []
    current_start = start
    while current_start < end:
        current_end = min(current_start + pd.DateOffset(months=3), end)
        try:
            result = query_fn(start=current_start, end=current_end, **kwargs)
            all_data.append(result)
            print(f"  Fetched: {current_start.date()} to {current_end.date()}")
        except Exception as e:
            print(f"  Warning: {current_start.date()} to {current_end.date()}: {e}")
        current_start = current_end

    if not all_data:
        raise ValueError("No data could be fetched from ENTSOE")

    return pd.concat(all_data)


def fetch_day_ahead_prices(
    country_code: str = "NL",
    years: int = 3,
) -> pd.DataFrame:
    """
    Fetch day-ahead prices from ENTSOE API.

    Stores data in data/entsoe/day_ahead_prices_NL/ with a watermark tracking
    the latest timestamp fetched. On subsequent calls, only fetches new data
    and appends it to the existing dataset.

    Returns:
        DataFrame with datetime_utc and price_eur_mwh columns.
    """
    data_dir = PRICES_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    data_file = data_dir / "data.parquet"

    client = get_entsoe_client()
    end = pd.Timestamp.now(tz="Europe/Amsterdam").floor("D")
    watermark = _read_watermark(data_dir)

    if watermark is not None:
        start = watermark.tz_convert("Europe/Amsterdam")
        # If watermark is recent enough, just return cached data
        if (end - start) < pd.Timedelta(hours=1) and data_file.exists():
            return pd.read_parquet(data_file)
    else:
        start = end - pd.DateOffset(years=years)

    print(f"Fetching day-ahead prices ({start.date()} to {end.date()})...")
    combined = _fetch_in_chunks(
        lambda start, end, **kw: client.query_day_ahead_prices(country_code, start=start, end=end),
        start, end,
    )
    combined = combined[~combined.index.duplicated(keep="first")]

    new_df = pd.DataFrame({
        "datetime_utc": combined.index.tz_convert("UTC"),
        "price_eur_mwh": combined.values,
    })
    new_df["datetime_utc"] = pd.to_datetime(new_df["datetime_utc"]).dt.tz_localize(None)

    # Merge with existing data if present
    if data_file.exists() and watermark is not None:
        existing = pd.read_parquet(data_file)
        merged = pd.concat([existing, new_df]).drop_duplicates(subset="datetime_utc", keep="last")
        merged = merged.sort_values("datetime_utc").reset_index(drop=True)
    else:
        merged = new_df.sort_values("datetime_utc").reset_index(drop=True)

    merged.to_parquet(data_file, index=False)
    _write_watermark(data_dir, pd.Timestamp(merged["datetime_utc"].max(), tz="UTC"))

    return merged


def fetch_solar_generation(
    country_code: str = "NL",
    years: int = 3,
) -> pd.DataFrame:
    """
    Fetch solar generation data from ENTSOE API.

    Stores data in data/entsoe/energy_generation_NL/ with a watermark tracking
    the latest timestamp fetched. On subsequent calls, only fetches new data
    and appends it to the existing dataset.

    Returns:
        DataFrame with datetime_utc and solar_generation_mw columns (hourly).
    """
    data_dir = GENERATION_DIR
    data_dir.mkdir(parents=True, exist_ok=True)
    data_file = data_dir / "data.parquet"

    client = get_entsoe_client()
    end = pd.Timestamp.now(tz="Europe/Amsterdam").floor("D")
    watermark = _read_watermark(data_dir)

    if watermark is not None:
        start = watermark.tz_convert("Europe/Amsterdam")
        if (end - start) < pd.Timedelta(hours=1) and data_file.exists():
            return pd.read_parquet(data_file)
    else:
        start = end - pd.DateOffset(years=years)

    print(f"Fetching solar generation ({start.date()} to {end.date()})...")
    combined = _fetch_in_chunks(
        lambda start, end, **kw: client.query_generation(country_code, start=start, end=end, psr_type="B16"),
        start, end,
    )

    # Handle MultiIndex columns from ENTSOE (Solar, Actual Aggregated)
    if isinstance(combined.columns, pd.MultiIndex):
        if ("Solar", "Actual Aggregated") in combined.columns:
            solar_series = combined[("Solar", "Actual Aggregated")]
        else:
            solar_series = combined.sum(axis=1)
    elif isinstance(combined, pd.DataFrame):
        solar_series = combined.sum(axis=1)
    else:
        solar_series = combined

    # Resample to hourly to match price data (solar is 15-min)
    solar_series = solar_series.resample("H").mean()

    new_df = pd.DataFrame({
        "datetime_utc": solar_series.index.tz_convert("UTC"),
        "solar_generation_mw": solar_series.values,
    })
    new_df["datetime_utc"] = pd.to_datetime(new_df["datetime_utc"]).dt.tz_localize(None)

    # Merge with existing data if present
    if data_file.exists() and watermark is not None:
        existing = pd.read_parquet(data_file)
        merged = pd.concat([existing, new_df]).drop_duplicates(subset="datetime_utc", keep="last")
        merged = merged.sort_values("datetime_utc").reset_index(drop=True)
    else:
        merged = new_df.sort_values("datetime_utc").reset_index(drop=True)

    merged.to_parquet(data_file, index=False)
    _write_watermark(data_dir, pd.Timestamp(merged["datetime_utc"].max(), tz="UTC"))

    return merged
