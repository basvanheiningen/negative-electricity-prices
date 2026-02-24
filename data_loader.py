from __future__ import annotations

import pandas as pd
from pathlib import Path

from utils.entsoe import fetch_day_ahead_prices, fetch_solar_generation


def fetch_solar_and_prices(
    country_code: str = "NL",
    years: int = 3,
) -> pd.DataFrame:
    """
    Fetch and merge solar generation and price data for analysis.

    Returns:
        DataFrame with datetime, solar generation, and prices aligned by hour
    """
    solar_df = fetch_solar_generation(country_code, years)
    prices_df = fetch_day_ahead_prices(country_code, years)

    # Merge on datetime
    merged = pd.merge(
        solar_df,
        prices_df,
        on="datetime_utc",
        how="inner",
    )

    # Add useful time features for analysis
    merged["hour"] = merged["datetime_utc"].dt.hour
    merged["month"] = merged["datetime_utc"].dt.month
    merged["year"] = merged["datetime_utc"].dt.year
    merged["dayofweek"] = merged["datetime_utc"].dt.dayofweek
    merged["is_weekend"] = merged["dayofweek"].isin([5, 6])

    return merged.sort_values("datetime_utc").reset_index(drop=True)


def load_entsoe_prices(data_dir: str = "data/entsoe/prices") -> pd.DataFrame:
    """Load all ENTSO-E price CSV files and return a combined DataFrame."""
    data_path = Path(data_dir)
    csv_files = sorted(data_path.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")

    dfs = []
    for csv_file in csv_files:
        df = pd.read_csv(
            csv_file,
            sep="\t",
            usecols=[
                "DateTime(UTC)",
                "AreaDisplayName",
                "MapCode",
                "Price[Currency/MWh]",
                "Currency",
            ],
        )
        dfs.append(df)

    combined = pd.concat(dfs, ignore_index=True)

    # Clean up column names
    combined = combined.rename(columns={
        "DateTime(UTC)": "datetime_utc",
        "AreaDisplayName": "area_name",
        "MapCode": "area_code",
        "Price[Currency/MWh]": "price",
        "Currency": "currency",
    })

    # Parse datetime
    combined["datetime_utc"] = pd.to_datetime(combined["datetime_utc"])

    # Sort by area and time
    combined = combined.sort_values(["area_code", "datetime_utc"]).reset_index(drop=True)

    return combined


def get_available_areas(df: pd.DataFrame) -> list[str]:
    """Get list of available areas sorted alphabetically."""
    return sorted(df["area_code"].unique().tolist())


def get_date_range(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Get the min and max dates in the dataset."""
    return df["datetime_utc"].min(), df["datetime_utc"].max()


def filter_data(
    df: pd.DataFrame,
    areas: list[str],
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    """Filter data by areas and date range."""
    mask = (
        (df["area_code"].isin(areas))
        & (df["datetime_utc"] >= start_date)
        & (df["datetime_utc"] <= end_date)
    )
    return df[mask].copy()
