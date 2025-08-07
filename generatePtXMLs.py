# script: generate_patient_xmls.py

import json
import numpy as np
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import timedelta, datetime

# Corrected METRICS definition
METRICS = {
    'HKQuantityTypeIdentifierWalkingSpeed': ('Walking Speed (m/s)', 0.8, 'low'),
    'HKQuantityTypeIdentifierStepLength': ('Step Length (m)', 0.6, 'low'),
    'HKQuantityTypeIdentifierWalkingAsymmetryPercentage': ('Walking Asymmetry (%)', 10, 'high'),
    'HKQuantityTypeIdentifierWalkingDoubleSupportPercentage': ('Double Support Time (%)', 30, 'high'),
}

BASE_SPEED = {
    "healthy": 1.4,
    "ms": 1.0,
    "diabetes": 1.1
}
SD_SPEED = 0.1

STEP_LENGTH_BASE = {
    "healthy": 0.75,
    "ms": 0.6,
    "diabetes": 0.65
}
SD_STEP = 0.05

def simulate_series(start, end, baseline, sd, flares, med_timeline, direction="low"):
    dates = pd.date_range(start, end)
    values = []

    # Convert flare periods to datetime.date
    flare_ranges = []
    for fs, fe in flares:
        fs_date = pd.to_datetime(fs).date()
        fe_date = pd.to_datetime(fe).date()
        flare_ranges.append((fs_date, fe_date))

    for d in dates:
        val = np.random.normal(baseline, sd)
        for fs, fe in flare_ranges:
            if fs <= d.date() <= fe:
                days = (d.date() - fs).days
                drop = sd * (2 - 0.3 * days)
                val -= max(drop, sd * 0.3)
        for ev in med_timeline:
            evd = pd.to_datetime(ev["date"]).date()
            if evd <= d.date() <= evd + timedelta(days=4):
                if direction == "low":
                    val += sd * 0.4
                else:
                    val -= sd * 0.4
        values.append(max(val, 0.2))
    return pd.DataFrame({"Date": dates, "Value": values})


def write_xml(patient, start, end, outfolder="outputs"):
    root = ET.Element("HealthData")

    if patient["has_ms"]:
        speed_baseline = BASE_SPEED["ms"]
        step_baseline = STEP_LENGTH_BASE["ms"]
    elif "diabetes" in patient["conditions"] or "hypertension" in patient["conditions"]:
        speed_baseline = BASE_SPEED["diabetes"]
        step_baseline = STEP_LENGTH_BASE["diabetes"]
    else:
        speed_baseline = BASE_SPEED["healthy"]
        step_baseline = STEP_LENGTH_BASE["healthy"]

    # Simulate each metric
    for metric, (label, default_value, direction) in METRICS.items():
        if metric == "HKQuantityTypeIdentifierWalkingSpeed":
            baseline = speed_baseline
            sd = SD_SPEED
        elif metric == "HKQuantityTypeIdentifierStepLength":
            baseline = step_baseline
            sd = SD_STEP
        else:
            # Use a constant baseline for other metrics
            baseline = default_value
            sd = default_value * 0.1

        df = simulate_series(start, end, baseline, sd, patient["flares"], patient["medications"], direction)

        for _, row in df.iterrows():
            rec = ET.SubElement(root, "Record")
            rec.set("type", metric)
            rec.set("unit", "count" if "%" in label else "m/s" if "Speed" in label else "m")
            rec.set("value", f"{row['Value']:.3f}")
            dt = row["Date"]
            rec.set("startDate", dt.strftime("%Y-%m-%dT09:00:00-0500"))
            rec.set("endDate", dt.strftime("%Y-%m-%dT09:05:00-0500"))
            rec.set("sourceName", "Simulated")
            rec.set("sourceVersion", "1.0")

    tree = ET.ElementTree(root)
    fname = f"{outfolder}/{patient['id']}.xml"
    tree.write(fname, encoding="utf-8", xml_declaration=True)


def main():
    with open("mock_patients.json") as f:
        pats = json.load(f)

    start = pd.to_datetime("2025-05-01")
    end = pd.to_datetime("2025-08-01")

    for p in pats:
        write_xml(p, start, end)

if __name__ == "__main__":
    main()
