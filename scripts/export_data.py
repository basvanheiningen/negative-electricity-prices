"""
Export ENTSOE data as JSON for the web frontend.
Computes negative price statistics and correlation data.
"""

import json
from pathlib import Path
import pandas as pd
import numpy as np

# Paths
BASE_DIR = Path(__file__).parent.parent
PRICES_PATH = BASE_DIR / "data/entsoe/day_ahead_prices_NL/data.parquet"
GENERATION_PATH = BASE_DIR / "data/entsoe/energy_generation_NL/data.parquet"
GENERATION_MIX_PATH = BASE_DIR / "data/entsoe/energy_generation_NL/full_mix.parquet"
KNMI_PATH = BASE_DIR / "data/knmi/uurgeg_260_2021-2030.txt"
OUTPUT_DIR = BASE_DIR / "web/public/data"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_data():
    """Load price and generation data."""
    prices = pd.read_parquet(PRICES_PATH)
    prices['datetime_utc'] = pd.to_datetime(prices['datetime_utc'])
    prices = prices.set_index('datetime_utc')

    generation = pd.read_parquet(GENERATION_PATH)
    generation['datetime_utc'] = pd.to_datetime(generation['datetime_utc'])
    generation = generation.set_index('datetime_utc')

    return prices, generation


def compute_negative_price_stats(prices: pd.DataFrame) -> dict:
    """Compute statistics about negative prices."""
    prices = prices.copy()
    prices['is_negative'] = prices['price_eur_mwh'] < 0
    prices['year'] = prices.index.year
    prices['month'] = prices.index.month
    prices['hour'] = prices.index.hour
    prices['year_month'] = prices.index.to_period('M').astype(str)

    # Monthly counts (for bar chart)
    monthly = prices.groupby('year_month')['is_negative'].sum().reset_index()
    monthly.columns = ['month', 'count']
    monthly_data = monthly.to_dict('records')

    # Monthly comparison data (for grouped bar chart comparing years)
    prices['month_num'] = prices.index.month
    monthly_by_year = prices.groupby(['year', 'month_num'])['is_negative'].sum().reset_index()
    monthly_by_year.columns = ['year', 'month', 'count']

    # Filter to recent years (2024, 2025, 2026)
    comparison_years = [2024, 2025, 2026]
    monthly_comparison = monthly_by_year[monthly_by_year['year'].isin(comparison_years)]
    monthly_comparison_data = {
        'years': comparison_years,
        'data': monthly_comparison.to_dict('records')
    }

    # Yearly counts (for line chart)
    yearly = prices.groupby('year')['is_negative'].sum().reset_index()
    yearly.columns = ['year', 'count']
    yearly['year'] = yearly['year'].astype(int)
    yearly['count'] = yearly['count'].astype(int)

    # Filter out years with less than 50% data coverage (except the last year which we extrapolate)
    hours_per_year = prices.groupby('year').size()
    min_hours = 365 * 24 * 0.5  # At least 50% of year
    last_year = yearly['year'].max()
    valid_years = hours_per_year[(hours_per_year >= min_hours) | (hours_per_year.index == last_year)].index
    yearly = yearly[yearly['year'].isin(valid_years)]

    # Check if the last year is incomplete and extrapolate based on trend
    last_year = yearly['year'].max()
    last_year_data = prices[prices['year'] == last_year]
    hours_in_last_year = len(last_year_data)
    total_hours_in_year = 365 * 24  # Approximate

    # Calculate trend-based extrapolation using linear regression on complete years
    complete_years = yearly[yearly['year'] < last_year]
    if len(complete_years) >= 2:
        # Simple linear regression: y = mx + b
        x = complete_years['year'].values
        y = complete_years['count'].values
        n = len(x)
        slope = (n * np.sum(x * y) - np.sum(x) * np.sum(y)) / (n * np.sum(x**2) - np.sum(x)**2)
        intercept = (np.sum(y) - slope * np.sum(x)) / n
        trend_extrapolation = int(slope * last_year + intercept)
    else:
        # Not enough data for trend, use last year's value
        trend_extrapolation = int(complete_years['count'].iloc[-1]) if len(complete_years) > 0 else 0

    yearly_data = []
    for _, row in yearly.iterrows():
        entry = {'year': int(row['year']), 'count': int(row['count']), 'extrapolated': False}
        if row['year'] == last_year and hours_in_last_year < total_hours_in_year * 0.9:
            # Less than 90% of year available, mark as extrapolated
            entry['count'] = int(row['count'])  # Actual count so far
            entry['extrapolated'] = True
            entry['extrapolated_count'] = max(0, trend_extrapolation)  # Trend-based extrapolation
            entry['coverage'] = round(hours_in_last_year / total_hours_in_year * 100, 1)
        yearly_data.append(entry)

    # Hour x Month heatmap (average frequency)
    heatmap = prices.groupby(['hour', 'month'])['is_negative'].mean().reset_index()
    heatmap.columns = ['hour', 'month', 'frequency']
    heatmap['frequency'] = (heatmap['frequency'] * 100).round(2)  # Convert to percentage
    heatmap_data = heatmap.to_dict('records')

    # Overall statistics
    total_hours = len(prices)
    negative_hours = int(prices['is_negative'].sum())
    percentage = round(negative_hours / total_hours * 100, 2)

    # Most negative price
    most_negative_idx = prices['price_eur_mwh'].idxmin()
    most_negative = {
        'price': float(prices.loc[most_negative_idx, 'price_eur_mwh']),
        'datetime': most_negative_idx.isoformat()
    }

    # Negative price distribution
    negative_prices = prices[prices['is_negative']]['price_eur_mwh']
    if len(negative_prices) > 0:
        price_distribution = {
            'min': float(negative_prices.min()),
            'max': float(negative_prices.max()),
            'mean': float(negative_prices.mean()),
            'median': float(negative_prices.median())
        }
    else:
        price_distribution = {'min': 0, 'max': 0, 'mean': 0, 'median': 0}

    return {
        'monthly': monthly_data,
        'monthly_comparison': monthly_comparison_data,
        'yearly': yearly_data,
        'heatmap': heatmap_data,
        'statistics': {
            'total_hours': total_hours,
            'negative_hours': negative_hours,
            'percentage': percentage,
            'most_negative': most_negative,
            'price_distribution': price_distribution,
            'date_range': {
                'start': prices.index.min().isoformat(),
                'end': prices.index.max().isoformat()
            }
        }
    }


def compute_correlation_data(prices: pd.DataFrame, generation: pd.DataFrame) -> dict:
    """Compute correlation between solar generation and price."""
    # Merge on datetime
    merged = prices.join(generation, how='inner')
    merged = merged.dropna()

    merged['hour'] = merged.index.hour
    merged['month'] = merged.index.month
    merged['is_weekend'] = merged.index.dayofweek >= 5
    merged['season'] = merged['month'].map({
        12: 'winter', 1: 'winter', 2: 'winter',
        3: 'lente', 4: 'lente', 5: 'lente',
        6: 'zomer', 7: 'zomer', 8: 'zomer',
        9: 'herfst', 10: 'herfst', 11: 'herfst'
    })

    # Overall correlation
    overall_corr = float(merged['price_eur_mwh'].corr(merged['solar_generation_mw']))

    # Scatter plot data (sample for performance)
    sample = merged.sample(min(2000, len(merged)), random_state=42)
    scatter_data = [
        {
            'solar': float(row['solar_generation_mw']),
            'price': float(row['price_eur_mwh']),
            'hour': int(row['hour'])
        }
        for _, row in sample.iterrows()
    ]

    # Correlation by hour
    hourly_corr = merged.groupby('hour').apply(
        lambda x: x['price_eur_mwh'].corr(x['solar_generation_mw'])
    ).reset_index()
    hourly_corr.columns = ['hour', 'correlation']
    hourly_corr['correlation'] = hourly_corr['correlation'].round(4)
    hourly_corr_data = hourly_corr.to_dict('records')

    # Correlation by season
    season_corr = merged.groupby('season').apply(
        lambda x: x['price_eur_mwh'].corr(x['solar_generation_mw'])
    ).round(4).to_dict()

    # Correlation by weekend/weekday
    weekend_corr = merged.groupby('is_weekend').apply(
        lambda x: x['price_eur_mwh'].corr(x['solar_generation_mw'])
    ).round(4).to_dict()
    weekend_corr = {
        'weekdag': float(weekend_corr.get(False, 0)),
        'weekend': float(weekend_corr.get(True, 0))
    }

    # Time series data for dual-axis chart (daily aggregates)
    daily = merged.resample('D').agg({
        'price_eur_mwh': 'mean',
        'solar_generation_mw': 'mean'
    }).reset_index()
    daily['datetime_utc'] = daily['datetime_utc'].dt.strftime('%Y-%m-%d')

    # Sample to reduce size (every 7th day for weekly view)
    timeseries_data = daily.iloc[::7].to_dict('records')

    return {
        'overall_correlation': round(overall_corr, 4),
        'scatter': scatter_data,
        'hourly_correlation': hourly_corr_data,
        'season_correlation': season_corr,
        'weekend_correlation': weekend_corr,
        'timeseries': timeseries_data,
        'statistics': {
            'n_observations': len(merged),
            'solar_range': {
                'min': float(merged['solar_generation_mw'].min()),
                'max': float(merged['solar_generation_mw'].max()),
                'mean': float(merged['solar_generation_mw'].mean())
            },
            'price_range': {
                'min': float(merged['price_eur_mwh'].min()),
                'max': float(merged['price_eur_mwh'].max()),
                'mean': float(merged['price_eur_mwh'].mean())
            }
        }
    }


def compute_energy_mix_data(prices: pd.DataFrame) -> dict:
    """Compute relationship between renewable share and negative prices."""
    if not GENERATION_MIX_PATH.exists():
        return {}

    mix = pd.read_parquet(GENERATION_MIX_PATH)
    mix['datetime_utc'] = pd.to_datetime(mix['datetime_utc'])
    mix = mix.set_index('datetime_utc')

    # Calculate renewable generation (solar + wind)
    renewable_cols = ['Solar', 'Wind Offshore', 'Wind Onshore']
    available_renewable = [c for c in renewable_cols if c in mix.columns]
    mix['renewable_mw'] = mix[available_renewable].sum(axis=1)

    # Calculate total generation
    gen_cols = [c for c in mix.columns if c not in ['renewable_mw']]
    mix['total_mw'] = mix[gen_cols].sum(axis=1)

    # Calculate renewable share
    mix['renewable_share'] = (mix['renewable_mw'] / mix['total_mw'] * 100).clip(0, 100)

    # Merge with prices
    prices_copy = prices.copy()
    prices_copy['is_negative'] = prices_copy['price_eur_mwh'] < 0

    merged = mix.join(prices_copy, how='inner')
    merged = merged.dropna(subset=['renewable_share', 'is_negative'])

    # Yearly statistics: renewable share vs negative hours
    merged['year'] = merged.index.year
    yearly_stats = merged.groupby('year').agg({
        'renewable_share': 'mean',
        'is_negative': 'sum',
        'renewable_mw': 'mean'
    }).reset_index()
    yearly_stats.columns = ['year', 'avg_renewable_share', 'negative_hours', 'avg_renewable_mw']

    # Filter to complete years (2020+)
    yearly_stats = yearly_stats[yearly_stats['year'] >= 2020]

    yearly_data = [
        {
            'year': int(row['year']),
            'renewable_share': round(float(row['avg_renewable_share']), 1),
            'negative_hours': int(row['negative_hours']),
            'renewable_mw': round(float(row['avg_renewable_mw']), 0)
        }
        for _, row in yearly_stats.iterrows()
    ]

    # Monthly statistics for more granular view
    merged['year_month'] = merged.index.to_period('M').astype(str)
    monthly_stats = merged.groupby('year_month').agg({
        'renewable_share': 'mean',
        'is_negative': 'sum',
        'renewable_mw': 'mean'
    }).reset_index()
    monthly_stats.columns = ['month', 'renewable_share', 'negative_hours', 'renewable_mw']

    # Filter to 2020+
    monthly_stats = monthly_stats[monthly_stats['month'] >= '2020-01']

    monthly_data = [
        {
            'month': row['month'],
            'renewable_share': round(float(row['renewable_share']), 1),
            'negative_hours': int(row['negative_hours']),
            'renewable_mw': round(float(row['renewable_mw']), 0)
        }
        for _, row in monthly_stats.iterrows()
    ]

    # Scatter plot: renewable share vs negative price occurrence (hourly data, sampled)
    sample = merged.sample(min(3000, len(merged)), random_state=42)
    scatter_data = [
        {
            'renewable_share': round(float(row['renewable_share']), 1),
            'price': round(float(row['price_eur_mwh']), 2),
            'is_negative': bool(row['is_negative'])
        }
        for _, row in sample.iterrows()
    ]

    # Correlation between renewable share and price
    correlation = float(merged['renewable_share'].corr(merged['price_eur_mwh']))

    # Negative price probability by renewable share bucket
    merged['renewable_bucket'] = pd.cut(
        merged['renewable_share'],
        bins=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        labels=['0-10%', '10-20%', '20-30%', '30-40%', '40-50%', '50-60%', '60-70%', '70-80%', '80-90%', '90-100%']
    )
    bucket_stats = merged.groupby('renewable_bucket', observed=True).agg({
        'is_negative': ['sum', 'count']
    })
    bucket_stats.columns = ['negative_hours', 'total_hours']
    bucket_stats['probability'] = (bucket_stats['negative_hours'] / bucket_stats['total_hours'] * 100)

    bucket_data = [
        {
            'bucket': str(bucket),
            'negative_hours': int(row['negative_hours']),
            'total_hours': int(row['total_hours']),
            'probability': round(float(row['probability']), 2)
        }
        for bucket, row in bucket_stats.iterrows()
    ]

    # Overall statistics
    total_renewable_share = float(merged['renewable_share'].mean())
    max_renewable_share = float(merged['renewable_share'].max())

    return {
        'yearly': yearly_data,
        'monthly': monthly_data,
        'scatter': scatter_data,
        'buckets': bucket_data,
        'correlation': round(correlation, 4),
        'statistics': {
            'avg_renewable_share': round(total_renewable_share, 1),
            'max_renewable_share': round(max_renewable_share, 1),
            'date_range': {
                'start': merged.index.min().isoformat(),
                'end': merged.index.max().isoformat()
            }
        }
    }


def load_knmi_data() -> pd.DataFrame:
    """Load KNMI weather data."""
    if not KNMI_PATH.exists():
        return pd.DataFrame()

    # Read the file, skipping header lines
    with open(KNMI_PATH, 'r') as f:
        lines = f.readlines()

    # Find the header line (starts with # STN)
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('# STN'):
            header_idx = i
            break

    if header_idx is None:
        return pd.DataFrame()

    # Parse header
    header = lines[header_idx].replace('#', '').strip().split(',')
    header = [h.strip() for h in header]

    # Read data
    data_lines = lines[header_idx + 1:]
    data = []
    for line in data_lines:
        if line.strip():
            values = [v.strip() for v in line.split(',')]
            if len(values) == len(header):
                data.append(values)

    df = pd.DataFrame(data, columns=header)

    # Convert to numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    # Create datetime column (KNMI uses UTC+1 for hour, we need to adjust)
    df['datetime_utc'] = pd.to_datetime(
        df['YYYYMMDD'].astype(int).astype(str), format='%Y%m%d'
    ) + pd.to_timedelta(df['HH'].astype(int) - 1, unit='h')

    # Convert units
    df['wind_speed_ms'] = df['FH'] / 10  # 0.1 m/s -> m/s
    df['global_radiation_jcm2'] = df['Q']  # J/cm2

    return df[['datetime_utc', 'wind_speed_ms', 'global_radiation_jcm2']].dropna()


def compute_weather_data(prices: pd.DataFrame) -> dict:
    """Compute relationship between weather and energy production/prices."""
    knmi = load_knmi_data()
    if knmi.empty:
        return {}

    # Load generation mix data
    if not GENERATION_MIX_PATH.exists():
        return {}

    mix = pd.read_parquet(GENERATION_MIX_PATH)
    mix['datetime_utc'] = pd.to_datetime(mix['datetime_utc'])
    mix = mix.set_index('datetime_utc')

    # Calculate total wind and solar
    wind_cols = ['Wind Offshore', 'Wind Onshore']
    available_wind = [c for c in wind_cols if c in mix.columns]
    mix['wind_mw'] = mix[available_wind].sum(axis=1) if available_wind else 0

    if 'Solar' in mix.columns:
        mix['solar_mw'] = mix['Solar']
    else:
        mix['solar_mw'] = 0

    # Merge weather with generation
    knmi = knmi.set_index('datetime_utc')
    merged = mix.join(knmi, how='inner')
    merged = merged.dropna(subset=['wind_speed_ms', 'global_radiation_jcm2', 'wind_mw', 'solar_mw'])

    # Add prices
    prices_copy = prices.copy()
    merged = merged.join(prices_copy, how='inner')
    merged = merged.dropna(subset=['price_eur_mwh'])
    merged['is_negative'] = merged['price_eur_mwh'] < 0

    # Scatter data: radiation vs solar production (sampled)
    sample = merged.sample(min(2000, len(merged)), random_state=42)
    solar_scatter = [
        {
            'radiation': round(float(row['global_radiation_jcm2']), 1),
            'solar_mw': round(float(row['solar_mw']), 0),
            'is_negative': bool(row['is_negative'])
        }
        for _, row in sample.iterrows()
    ]

    # Scatter data: wind speed vs wind production (sampled)
    wind_scatter = [
        {
            'wind_speed': round(float(row['wind_speed_ms']), 1),
            'wind_mw': round(float(row['wind_mw']), 0),
            'is_negative': bool(row['is_negative'])
        }
        for _, row in sample.iterrows()
    ]

    # Correlations
    solar_corr = float(merged['global_radiation_jcm2'].corr(merged['solar_mw']))
    wind_corr = float(merged['wind_speed_ms'].corr(merged['wind_mw']))
    solar_price_corr = float(merged['global_radiation_jcm2'].corr(merged['price_eur_mwh']))
    wind_price_corr = float(merged['wind_speed_ms'].corr(merged['price_eur_mwh']))

    # Negative price probability by radiation bucket
    merged['radiation_bucket'] = pd.cut(
        merged['global_radiation_jcm2'],
        bins=[0, 50, 100, 200, 300, 500, 1000, 2000, 3000],
        labels=['0-50', '50-100', '100-200', '200-300', '300-500', '500-1000', '1000-2000', '2000+']
    )
    radiation_buckets = merged.groupby('radiation_bucket', observed=True).agg({
        'is_negative': ['sum', 'count', 'mean'],
        'solar_mw': 'mean'
    })
    radiation_buckets.columns = ['negative_hours', 'total_hours', 'probability', 'avg_solar_mw']

    radiation_bucket_data = [
        {
            'bucket': str(bucket),
            'negative_hours': int(row['negative_hours']),
            'total_hours': int(row['total_hours']),
            'probability': round(float(row['probability']) * 100, 2),
            'avg_solar_mw': round(float(row['avg_solar_mw']), 0)
        }
        for bucket, row in radiation_buckets.iterrows()
    ]

    # Negative price probability by wind speed bucket
    merged['wind_bucket'] = pd.cut(
        merged['wind_speed_ms'],
        bins=[0, 2, 4, 6, 8, 10, 15, 25],
        labels=['0-2', '2-4', '4-6', '6-8', '8-10', '10-15', '15+']
    )
    wind_buckets = merged.groupby('wind_bucket', observed=True).agg({
        'is_negative': ['sum', 'count', 'mean'],
        'wind_mw': 'mean'
    })
    wind_buckets.columns = ['negative_hours', 'total_hours', 'probability', 'avg_wind_mw']

    wind_bucket_data = [
        {
            'bucket': str(bucket),
            'negative_hours': int(row['negative_hours']),
            'total_hours': int(row['total_hours']),
            'probability': round(float(row['probability']) * 100, 2),
            'avg_wind_mw': round(float(row['avg_wind_mw']), 0)
        }
        for bucket, row in wind_buckets.iterrows()
    ]

    return {
        'solar_scatter': solar_scatter,
        'wind_scatter': wind_scatter,
        'radiation_buckets': radiation_bucket_data,
        'wind_buckets': wind_bucket_data,
        'correlations': {
            'radiation_solar': round(solar_corr, 3),
            'wind_speed_wind': round(wind_corr, 3),
            'radiation_price': round(solar_price_corr, 3),
            'wind_speed_price': round(wind_price_corr, 3)
        },
        'statistics': {
            'n_observations': len(merged),
            'date_range': {
                'start': merged.index.min().isoformat(),
                'end': merged.index.max().isoformat()
            }
        }
    }


def compute_demand_data(prices: pd.DataFrame) -> dict:
    """Compute relationship between low demand periods and negative prices."""
    prices = prices.copy()
    prices['is_negative'] = prices['price_eur_mwh'] < 0
    prices['hour'] = prices.index.hour
    prices['dayofweek'] = prices.index.dayofweek
    prices['is_weekend'] = prices['dayofweek'] >= 5
    prices['month'] = prices.index.month
    prices['year'] = prices.index.year
    prices['date'] = prices.index.date

    # Dutch public holidays (approximate - major ones)
    dutch_holidays = [
        # 2020
        '2020-01-01', '2020-04-12', '2020-04-13', '2020-04-27', '2020-05-05',
        '2020-05-21', '2020-05-31', '2020-06-01', '2020-12-25', '2020-12-26',
        # 2021
        '2021-01-01', '2021-04-04', '2021-04-05', '2021-04-27', '2021-05-05',
        '2021-05-13', '2021-05-23', '2021-05-24', '2021-12-25', '2021-12-26',
        # 2022
        '2022-01-01', '2022-04-17', '2022-04-18', '2022-04-27', '2022-05-05',
        '2022-05-26', '2022-06-05', '2022-06-06', '2022-12-25', '2022-12-26',
        # 2023
        '2023-01-01', '2023-04-09', '2023-04-10', '2023-04-27', '2023-05-05',
        '2023-05-18', '2023-05-28', '2023-05-29', '2023-12-25', '2023-12-26',
        # 2024
        '2024-01-01', '2024-03-31', '2024-04-01', '2024-04-27', '2024-05-05',
        '2024-05-09', '2024-05-19', '2024-05-20', '2024-12-25', '2024-12-26',
        # 2025
        '2025-01-01', '2025-04-20', '2025-04-21', '2025-04-27', '2025-05-05',
        '2025-05-29', '2025-06-08', '2025-06-09', '2025-12-25', '2025-12-26',
    ]
    holiday_dates = set(pd.to_datetime(dutch_holidays).date)
    prices['is_holiday'] = prices['date'].apply(lambda x: x in holiday_dates)
    prices['is_low_demand'] = prices['is_weekend'] | prices['is_holiday']

    # Day of week statistics
    dow_names = ['Maandag', 'Dinsdag', 'Woensdag', 'Donderdag', 'Vrijdag', 'Zaterdag', 'Zondag']
    dow_stats = prices.groupby('dayofweek').agg({
        'is_negative': ['sum', 'count'],
        'price_eur_mwh': 'mean'
    })
    dow_stats.columns = ['negative_hours', 'total_hours', 'avg_price']
    dow_stats['probability'] = dow_stats['negative_hours'] / dow_stats['total_hours'] * 100

    dayofweek_data = [
        {
            'day': dow_names[i],
            'day_num': i,
            'negative_hours': int(row['negative_hours']),
            'total_hours': int(row['total_hours']),
            'probability': round(float(row['probability']), 2),
            'avg_price': round(float(row['avg_price']), 2),
            'is_weekend': i >= 5
        }
        for i, row in dow_stats.iterrows()
    ]

    # Hour of day statistics (weekday vs weekend vs holiday)
    hourly_weekday = prices[(~prices['is_weekend']) & (~prices['is_holiday'])].groupby('hour').agg({
        'is_negative': 'mean',
        'price_eur_mwh': 'mean'
    })
    hourly_weekend = prices[prices['is_weekend'] & (~prices['is_holiday'])].groupby('hour').agg({
        'is_negative': 'mean',
        'price_eur_mwh': 'mean'
    })
    hourly_holiday = prices[prices['is_holiday']].groupby('hour').agg({
        'is_negative': 'mean',
        'price_eur_mwh': 'mean'
    })

    hourly_comparison = {
        'hours': list(range(24)),
        'weekday': {
            'negative_probability': [round(float(v) * 100, 2) for v in hourly_weekday['is_negative'].values],
            'avg_price': [round(float(v), 2) for v in hourly_weekday['price_eur_mwh'].values]
        },
        'weekend': {
            'negative_probability': [round(float(v) * 100, 2) for v in hourly_weekend['is_negative'].values],
            'avg_price': [round(float(v), 2) for v in hourly_weekend['price_eur_mwh'].values]
        },
        'holiday': {
            'negative_probability': [round(float(v) * 100, 2) for v in hourly_holiday['is_negative'].values],
            'avg_price': [round(float(v), 2) for v in hourly_holiday['price_eur_mwh'].values]
        }
    }

    # Weekend vs weekday overall comparison
    weekend_stats = prices.groupby('is_weekend').agg({
        'is_negative': ['sum', 'count', 'mean'],
        'price_eur_mwh': 'mean'
    })
    weekend_stats.columns = ['negative_hours', 'total_hours', 'probability', 'avg_price']

    weekend_comparison = {
        'weekday': {
            'negative_hours': int(weekend_stats.loc[False, 'negative_hours']),
            'total_hours': int(weekend_stats.loc[False, 'total_hours']),
            'probability': round(float(weekend_stats.loc[False, 'probability']) * 100, 2),
            'avg_price': round(float(weekend_stats.loc[False, 'avg_price']), 2)
        },
        'weekend': {
            'negative_hours': int(weekend_stats.loc[True, 'negative_hours']),
            'total_hours': int(weekend_stats.loc[True, 'total_hours']),
            'probability': round(float(weekend_stats.loc[True, 'probability']) * 100, 2),
            'avg_price': round(float(weekend_stats.loc[True, 'avg_price']), 2)
        }
    }

    # Holiday statistics
    holiday_prices = prices[prices['is_holiday']]
    non_holiday_prices = prices[~prices['is_holiday']]

    holiday_stats = {
        'holiday': {
            'negative_hours': int(holiday_prices['is_negative'].sum()),
            'total_hours': int(len(holiday_prices)),
            'probability': round(float(holiday_prices['is_negative'].mean()) * 100, 2) if len(holiday_prices) > 0 else 0,
            'avg_price': round(float(holiday_prices['price_eur_mwh'].mean()), 2) if len(holiday_prices) > 0 else 0
        },
        'non_holiday': {
            'negative_hours': int(non_holiday_prices['is_negative'].sum()),
            'total_hours': int(len(non_holiday_prices)),
            'probability': round(float(non_holiday_prices['is_negative'].mean()) * 100, 2),
            'avg_price': round(float(non_holiday_prices['price_eur_mwh'].mean()), 2)
        }
    }

    # Monthly heatmap by day of week (for 2024-2025)
    recent = prices[prices['year'] >= 2024]
    heatmap = recent.groupby(['month', 'dayofweek'])['is_negative'].mean().reset_index()
    heatmap['probability'] = heatmap['is_negative'] * 100
    heatmap_data = [
        {
            'month': int(row['month']),
            'dayofweek': int(row['dayofweek']),
            'probability': round(float(row['probability']), 2)
        }
        for _, row in heatmap.iterrows()
    ]

    return {
        'dayofweek': dayofweek_data,
        'hourly_comparison': hourly_comparison,
        'weekend_comparison': weekend_comparison,
        'holiday_stats': holiday_stats,
        'heatmap': heatmap_data,
        'statistics': {
            'weekend_factor': round(
                weekend_comparison['weekend']['probability'] / weekend_comparison['weekday']['probability'], 2
            ) if weekend_comparison['weekday']['probability'] > 0 else 0
        }
    }


def main():
    print("Loading data...")
    prices, generation = load_data()

    print(f"Prices: {len(prices)} records from {prices.index.min()} to {prices.index.max()}")
    print(f"Generation: {len(generation)} records from {generation.index.min()} to {generation.index.max()}")

    print("\nComputing negative price statistics...")
    negative_stats = compute_negative_price_stats(prices)

    print("\nComputing correlation data...")
    correlation_data = compute_correlation_data(prices, generation)

    print("\nComputing energy mix data...")
    energy_mix_data = compute_energy_mix_data(prices)

    print("\nComputing demand data...")
    demand_data = compute_demand_data(prices)

    print("\nComputing weather data...")
    weather_data = compute_weather_data(prices)

    # Save JSON files
    negative_prices_path = OUTPUT_DIR / "negative_prices.json"
    with open(negative_prices_path, 'w') as f:
        json.dump(negative_stats, f, indent=2)
    print(f"\nSaved: {negative_prices_path}")

    correlation_path = OUTPUT_DIR / "correlation.json"
    with open(correlation_path, 'w') as f:
        json.dump(correlation_data, f, indent=2)
    print(f"Saved: {correlation_path}")

    if energy_mix_data:
        energy_mix_path = OUTPUT_DIR / "energy_mix.json"
        with open(energy_mix_path, 'w') as f:
            json.dump(energy_mix_data, f, indent=2)
        print(f"Saved: {energy_mix_path}")

    demand_path = OUTPUT_DIR / "demand.json"
    with open(demand_path, 'w') as f:
        json.dump(demand_data, f, indent=2)
    print(f"Saved: {demand_path}")

    if weather_data:
        weather_path = OUTPUT_DIR / "weather.json"
        with open(weather_path, 'w') as f:
            json.dump(weather_data, f, indent=2)
        print(f"Saved: {weather_path}")

    # Print summary
    print(f"\n=== Summary ===")
    print(f"Total hours analyzed: {negative_stats['statistics']['total_hours']}")
    print(f"Negative price hours: {negative_stats['statistics']['negative_hours']}")
    print(f"Percentage: {negative_stats['statistics']['percentage']}%")
    print(f"Most negative price: €{negative_stats['statistics']['most_negative']['price']}/MWh")
    print(f"Solar-price correlation: {correlation_data['overall_correlation']}")


if __name__ == "__main__":
    main()
