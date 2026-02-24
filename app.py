import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from data_loader import (
    load_entsoe_prices,
    get_available_areas,
    get_date_range,
    filter_data,
    fetch_solar_and_prices,
)

st.set_page_config(
    page_title="ENTSO-E Energy Dashboard",
    page_icon="⚡",
    layout="wide",
)

st.title("⚡ ENTSO-E Energy Dashboard")

# Create tabs for different views
tab_prices, tab_solar = st.tabs(["Price Dashboard", "Solar vs Price Analysis (NL)"])


@st.cache_data
def load_data():
    return load_entsoe_prices()


@st.cache_data(ttl=86400)  # Cache for 24 hours
def load_solar_price_data():
    return fetch_solar_and_prices(country_code="NL", years=3)


# ============================================================
# TAB 1: Price Dashboard (existing functionality)
# ============================================================
with tab_prices:
    # Load data
    with st.spinner("Loading price data..."):
        df = load_data()

    # Get available areas and date range
    areas = get_available_areas(df)
    min_date, max_date = get_date_range(df)

    # Sidebar filters
    st.sidebar.header("Price Dashboard Filters")

    selected_areas = st.sidebar.multiselect(
        "Select areas",
        options=areas,
        default=["NL"],  # Default to Netherlands
        help="Select one or more price areas to compare",
    )

    date_range = st.sidebar.date_input(
        "Date range",
        value=(min_date.date(), max_date.date()),
        min_value=min_date.date(),
        max_value=max_date.date(),
    )

    # Handle single date selection
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = end_date = date_range

    # Convert to datetime
    start_dt = pd.Timestamp(start_date)
    end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    # Filter data
    if selected_areas:
        filtered_df = filter_data(df, selected_areas, start_dt, end_dt)
    else:
        st.warning("Please select at least one area.")
        st.stop()

    if filtered_df.empty:
        st.warning("No data available for the selected filters.")
        st.stop()

    # Main content
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_price = filtered_df["price"].mean()
        st.metric("Average Price", f"€{avg_price:.2f}/MWh")

    with col2:
        min_price = filtered_df["price"].min()
        st.metric("Min Price", f"€{min_price:.2f}/MWh")

    with col3:
        max_price = filtered_df["price"].max()
        st.metric("Max Price", f"€{max_price:.2f}/MWh")

    with col4:
        std_price = filtered_df["price"].std()
        st.metric("Std Dev", f"€{std_price:.2f}")

    st.divider()

    # Time series chart
    st.subheader("Price Over Time")

    fig = px.line(
        filtered_df,
        x="datetime_utc",
        y="price",
        color="area_code",
        labels={
            "datetime_utc": "Date",
            "price": "Price (EUR/MWh)",
            "area_code": "Area",
        },
    )
    fig.update_layout(
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Additional charts in columns
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Price Distribution")
        fig_hist = px.histogram(
            filtered_df,
            x="price",
            color="area_code",
            nbins=50,
            labels={"price": "Price (EUR/MWh)", "area_code": "Area"},
            opacity=0.7,
        )
        fig_hist.update_layout(barmode="overlay")
        st.plotly_chart(fig_hist, use_container_width=True)

    with col_right:
        st.subheader("Average Price by Hour of Day")
        hourly_avg = filtered_df.copy()
        hourly_avg["hour"] = hourly_avg["datetime_utc"].dt.hour
        hourly_avg = hourly_avg.groupby(["hour", "area_code"])["price"].mean().reset_index()

        fig_hourly = px.line(
            hourly_avg,
            x="hour",
            y="price",
            color="area_code",
            labels={"hour": "Hour of Day", "price": "Avg Price (EUR/MWh)", "area_code": "Area"},
            markers=True,
        )
        fig_hourly.update_layout(xaxis=dict(tickmode="linear", dtick=2))
        st.plotly_chart(fig_hourly, use_container_width=True)

    # Monthly averages
    st.subheader("Monthly Average Prices")
    monthly_avg = filtered_df.copy()
    monthly_avg["month"] = monthly_avg["datetime_utc"].dt.to_period("M").astype(str)
    monthly_avg = monthly_avg.groupby(["month", "area_code"])["price"].mean().reset_index()

    fig_monthly = px.bar(
        monthly_avg,
        x="month",
        y="price",
        color="area_code",
        barmode="group",
        labels={"month": "Month", "price": "Avg Price (EUR/MWh)", "area_code": "Area"},
    )
    fig_monthly.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_monthly, use_container_width=True)

    # Data table
    with st.expander("View Raw Data"):
        st.dataframe(
            filtered_df.sort_values("datetime_utc", ascending=False),
            use_container_width=True,
            height=400,
        )

    # Footer
    st.divider()
    st.caption(f"Data range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} | Total records: {len(df):,}")


# ============================================================
# TAB 2: Solar vs Price Analysis
# ============================================================
with tab_solar:
    st.header("Solar Generation vs Electricity Price - Netherlands")
    st.markdown("""
    Analyzing the relationship between solar generation and day-ahead electricity prices
    in the Netherlands over the past 3 years. Data fetched from ENTSO-E Transparency Platform.
    """)

    # Load solar and price data
    with st.spinner("Fetching solar and price data from ENTSO-E API (this may take a moment on first load)..."):
        try:
            solar_price_df = load_solar_price_data()
            data_loaded = True
        except Exception as e:
            st.error(f"Error loading data: {e}")
            data_loaded = False

    if data_loaded and not solar_price_df.empty:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            correlation = solar_price_df["solar_generation_mw"].corr(solar_price_df["price_eur_mwh"])
            st.metric("Correlation", f"{correlation:.3f}")

        with col2:
            avg_solar = solar_price_df["solar_generation_mw"].mean()
            st.metric("Avg Solar Gen", f"{avg_solar:.0f} MW")

        with col3:
            avg_price = solar_price_df["price_eur_mwh"].mean()
            st.metric("Avg Price", f"€{avg_price:.2f}/MWh")

        with col4:
            data_points = len(solar_price_df)
            st.metric("Data Points", f"{data_points:,}")

        st.divider()

        # Scatter plot: Solar vs Price
        st.subheader("Solar Generation vs Price")
        fig_scatter = px.scatter(
            solar_price_df,
            x="solar_generation_mw",
            y="price_eur_mwh",
            opacity=0.3,
            labels={
                "solar_generation_mw": "Solar Generation (MW)",
                "price_eur_mwh": "Price (EUR/MWh)",
            },
            trendline="ols",
        )
        fig_scatter.update_layout(
            title=f"Correlation: {correlation:.3f}",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # Time series comparison
        st.subheader("Time Series Comparison")

        # Resample to daily for cleaner visualization
        daily_df = solar_price_df.set_index("datetime_utc").resample("D").agg({
            "solar_generation_mw": "mean",
            "price_eur_mwh": "mean",
        }).reset_index()

        fig_ts = go.Figure()
        fig_ts.add_trace(go.Scatter(
            x=daily_df["datetime_utc"],
            y=daily_df["solar_generation_mw"],
            name="Solar Generation (MW)",
            yaxis="y",
        ))
        fig_ts.add_trace(go.Scatter(
            x=daily_df["datetime_utc"],
            y=daily_df["price_eur_mwh"],
            name="Price (EUR/MWh)",
            yaxis="y2",
        ))
        fig_ts.update_layout(
            yaxis=dict(title="Solar Generation (MW)", side="left"),
            yaxis2=dict(title="Price (EUR/MWh)", side="right", overlaying="y"),
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_ts, use_container_width=True)

        # Analysis by hour
        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("Average by Hour of Day")
            hourly = solar_price_df.groupby("hour").agg({
                "solar_generation_mw": "mean",
                "price_eur_mwh": "mean",
            }).reset_index()

            fig_hourly = go.Figure()
            fig_hourly.add_trace(go.Bar(
                x=hourly["hour"],
                y=hourly["solar_generation_mw"],
                name="Solar (MW)",
                yaxis="y",
            ))
            fig_hourly.add_trace(go.Scatter(
                x=hourly["hour"],
                y=hourly["price_eur_mwh"],
                name="Price (EUR/MWh)",
                yaxis="y2",
                mode="lines+markers",
            ))
            fig_hourly.update_layout(
                xaxis=dict(title="Hour of Day", tickmode="linear", dtick=2),
                yaxis=dict(title="Solar Generation (MW)", side="left"),
                yaxis2=dict(title="Price (EUR/MWh)", side="right", overlaying="y"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_hourly, use_container_width=True)

        with col_right:
            st.subheader("Average by Month")
            monthly = solar_price_df.groupby("month").agg({
                "solar_generation_mw": "mean",
                "price_eur_mwh": "mean",
            }).reset_index()

            fig_monthly = go.Figure()
            fig_monthly.add_trace(go.Bar(
                x=monthly["month"],
                y=monthly["solar_generation_mw"],
                name="Solar (MW)",
                yaxis="y",
            ))
            fig_monthly.add_trace(go.Scatter(
                x=monthly["month"],
                y=monthly["price_eur_mwh"],
                name="Price (EUR/MWh)",
                yaxis="y2",
                mode="lines+markers",
            ))
            fig_monthly.update_layout(
                xaxis=dict(title="Month", tickmode="linear", dtick=1),
                yaxis=dict(title="Solar Generation (MW)", side="left"),
                yaxis2=dict(title="Price (EUR/MWh)", side="right", overlaying="y"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            )
            st.plotly_chart(fig_monthly, use_container_width=True)

        # Correlation by different time periods
        st.subheader("Correlation Analysis by Time Period")

        col1, col2, col3 = st.columns(3)

        with col1:
            # Correlation by year
            yearly_corr = solar_price_df.groupby("year").apply(
                lambda x: x["solar_generation_mw"].corr(x["price_eur_mwh"])
            ).reset_index(name="correlation")
            st.markdown("**By Year**")
            st.dataframe(yearly_corr, use_container_width=True, hide_index=True)

        with col2:
            # Correlation by season
            solar_price_df["season"] = solar_price_df["month"].map({
                12: "Winter", 1: "Winter", 2: "Winter",
                3: "Spring", 4: "Spring", 5: "Spring",
                6: "Summer", 7: "Summer", 8: "Summer",
                9: "Autumn", 10: "Autumn", 11: "Autumn",
            })
            seasonal_corr = solar_price_df.groupby("season").apply(
                lambda x: x["solar_generation_mw"].corr(x["price_eur_mwh"])
            ).reset_index(name="correlation")
            st.markdown("**By Season**")
            st.dataframe(seasonal_corr, use_container_width=True, hide_index=True)

        with col3:
            # Correlation weekday vs weekend
            weekend_corr = solar_price_df.groupby("is_weekend").apply(
                lambda x: x["solar_generation_mw"].corr(x["price_eur_mwh"])
            ).reset_index(name="correlation")
            weekend_corr["is_weekend"] = weekend_corr["is_weekend"].map({True: "Weekend", False: "Weekday"})
            st.markdown("**Weekday vs Weekend**")
            st.dataframe(weekend_corr, use_container_width=True, hide_index=True)

        # Raw data
        with st.expander("View Raw Data"):
            st.dataframe(
                solar_price_df.sort_values("datetime_utc", ascending=False),
                use_container_width=True,
                height=400,
            )

        # Summary insights
        st.divider()
        st.subheader("Key Insights")
        st.markdown(f"""
        - **Overall correlation**: {correlation:.3f} - {'Negative' if correlation < 0 else 'Positive'} relationship
          {'(higher solar = lower prices)' if correlation < 0 else '(higher solar = higher prices)'}
        - **Data range**: {solar_price_df['datetime_utc'].min().strftime('%Y-%m-%d')} to {solar_price_df['datetime_utc'].max().strftime('%Y-%m-%d')}
        - **Peak solar hours**: Midday (10:00-15:00) shows highest solar generation
        - **Price pattern**: Prices typically dip during high solar generation periods
        """)
