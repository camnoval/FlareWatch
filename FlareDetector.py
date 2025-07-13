import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# === Config ===
XML_PATH = r"C:\Users\camer\Documents\Coding\MSAppleWatch\ms_patient_extended_export_v2.xml" # Use path to your export

GAIT_METRICS = {
    'HKQuantityTypeIdentifierWalkingSpeed': ('Walking Speed (m/s)', 0.8, 'low'),
    'HKQuantityTypeIdentifierStepLength': ('Step Length (m)', 0.6, 'low'),
    'HKQuantityTypeIdentifierWalkingAsymmetryPercentage': ('Walking Asymmetry (%)', 10, 'high'),
    'HKQuantityTypeIdentifierWalkingDoubleSupportPercentage': ('Double Support Time (%)', 30, 'high'),
}

FLARE_DATES = [
    ("2025-06-26", "2025-06-28"),
    ("2025-07-10", "2025-07-12"),
]

# === Parser ===
@st.cache_data
def parse_apple_health_xml(path):
    tree = ET.parse(path)
    root = tree.getroot()

    records = []
    for record in root.findall('Record'):
        rtype = record.get('type')
        if rtype not in GAIT_METRICS:
            continue
        try:
            value = float(record.get('value'))
            date = pd.to_datetime(record.get('startDate')).date()
            unit = record.get('unit')
        except:
            continue
        records.append({
            'Metric': GAIT_METRICS[rtype][0],
            'Date': date,
            'Value': value,
            'Unit': unit,
            'TypeID': rtype
        })

    df = pd.DataFrame(records)
    return df

# === Flare Region Generator ===
def get_flare_shapes(ymin, ymax):
    shapes = []
    for start_str, end_str in FLARE_DATES:
        shapes.append({
            "type": "rect",
            "xref": "x",
            "yref": "y",
            "x0": pd.to_datetime(start_str),
            "x1": pd.to_datetime(end_str),
            "y0": ymin,
            "y1": ymax,
            "fillcolor": "rgba(255,0,0,0.1)",
            "line": {"width": 0}
        })
    return shapes

# === Chart Builder ===
def build_chart(df, label, pop_thresh, direction):
    df = df.sort_values("Date")
    df["Smoothed"] = df["Value"].rolling(window=7, min_periods=1).mean()

    baseline = df["Value"].mean()
    std = df["Value"].std()
    low_thresh = baseline - 2 * std
    warn_thresh = baseline - 1 * std

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Value"], name="Raw", mode="lines"))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["Smoothed"], name="Smoothed", mode="lines"))

    # Personal thresholds
    fig.add_trace(go.Scatter(
        x=df["Date"], y=[warn_thresh]*len(df), name="Personal Caution (−1σ)",
        line=dict(dash="dot", color="orange")
    ))
    fig.add_trace(go.Scatter(
        x=df["Date"], y=[low_thresh]*len(df), name="Personal Alert (−2σ)",
        line=dict(dash="dash", color="red")
    ))

    # Population threshold
    if pop_thresh is not None:
        fig.add_trace(go.Scatter(
            x=df["Date"], y=[pop_thresh]*len(df),
            name="Population Threshold", line=dict(dash="dot", color="green")
        ))

    # Flare region overlays
    shapes = get_flare_shapes(df["Value"].min(), df["Value"].max())
    fig.update_layout(
        title=f"{label} Over Time",
        yaxis_title=df["Unit"].iloc[0],
        xaxis_title="Date",
        legend_title="Legend",
        shapes=shapes
    )

    return fig, df, baseline, std, pop_thresh, direction

# === Streamlit UI ===
st.set_page_config(page_title="MS Gait Tracker", layout="wide")
st.title("🦿 MS Gait Tracker Dashboard")
st.caption("Multi-metric flare-up detection from Apple Watch gait data")

with st.spinner("Parsing XML export..."):
    df_all = parse_apple_health_xml(XML_PATH)

if df_all.empty:
    st.error("No gait-related records found.")
    st.stop()

# === Tabs for Each Metric ===
tabs = st.tabs([GAIT_METRICS[key][0] for key in GAIT_METRICS])

for i, key in enumerate(GAIT_METRICS):
    label, pop_thresh, direction = GAIT_METRICS[key]
    with tabs[i]:
        df_metric = df_all[df_all["TypeID"] == key].copy()
        if df_metric.empty:
            st.warning(f"No data found for {label}")
            continue

        fig, df_metric, baseline, std, pop_thresh, direction = build_chart(df_metric, label, pop_thresh, direction)
        st.plotly_chart(fig, use_container_width=True)

        latest = df_metric["Value"].iloc[-1]
        if direction == "low":
            if latest < pop_thresh:
                st.error("🔴 Latest value is below population threshold.")
            elif latest < baseline - 2 * std:
                st.warning("⚠️ Latest value is well below personal baseline.")
            elif latest < baseline - 1 * std:
                st.info("📉 Value drifting below baseline.")
            else:
                st.success("✅ Within normal range.")
        elif direction == "high":
            if latest > pop_thresh:
                st.error("🔴 Latest value is above population threshold.")
            elif latest > baseline + 2 * std:
                st.warning("⚠️ Latest value is well above personal baseline.")
            elif latest > baseline + 1 * std:
                st.info("📈 Value drifting above baseline.")
            else:
                st.success("✅ Within normal range.")

        st.subheader("Recent Entries")
        st.dataframe(df_metric.sort_values("Date", ascending=False).head(10))
