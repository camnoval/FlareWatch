import random
import uuid
from datetime import date, timedelta
import json

# Medication pools
MS_MEDS = ["Ocrevus", "Tysabri", "Tecfidera", "Aubagio"]
CHRONIC_MEDS = {
    "hypertension": ["Lisinopril", "Amlodipine", "Metoprolol", "Losartan"],
    "diabetes": ["Metformin", "Jardiance", "Insulin Glargine"],
    "depression": ["Sertraline", "Escitalopram", "Bupropion"],
    "hyperlipidemia": ["Atorvastatin", "Rosuvastatin"]
}
CONTROL_MEDS = ["Vitamin D", "Birth Control", "Melatonin", "Ibuprofen"]

def random_date(start, end):
    return start + timedelta(days=random.randint(0, (end - start).days))

def generate_med_timeline(start_date, conditions, is_control):
    timeline = []
    current_date = start_date

    if "ms" in conditions:
        drug = random.choice(MS_MEDS)
        timeline.append({"date": current_date, "drug": drug, "action": "start"})
        for _ in range(random.randint(1, 2)):
            current_date += timedelta(days=random.randint(15, 25))
            if random.random() < 0.5:
                timeline.append({"date": current_date, "drug": drug, "action": "increase dose"})
            else:
                new_drug = random.choice([d for d in MS_MEDS if d != drug])
                timeline.append({"date": current_date, "drug": new_drug, "action": "switch"})
                drug = new_drug
    else:
        # Controls or non-MS: 1-2 low-impact meds
        for _ in range(random.randint(1, 2)):
            timeline.append({
                "date": current_date,
                "drug": random.choice(CONTROL_MEDS),
                "action": "start"
            })

    # Add other chronic conditions
    for cond, meds in CHRONIC_MEDS.items():
        if cond in conditions:
            med = random.choice(meds)
            timeline.append({
                "date": current_date,
                "drug": med,
                "action": "start"
            })

    return timeline

def generate_flare_periods(start_date, has_ms):
    if not has_ms:
        return []

    flares = []
    for _ in range(random.randint(2, 3)):
        start = random_date(start_date, date(2025, 8, 1))
        end = start + timedelta(days=random.randint(2, 4))
        flares.append((start, end))
    return flares

def generate_conditions(has_ms, is_control):
    conditions = []

    if has_ms:
        conditions.append("ms")
    elif is_control:
        return conditions

    if random.random() < 0.5:
        conditions.append("hypertension")
    if random.random() < 0.3:
        conditions.append("diabetes")
    if random.random() < 0.4:
        conditions.append("depression")
    if random.random() < 0.4:
        conditions.append("hyperlipidemia")

    return conditions

def generate_patients(n=12):
    start_date = date(2025, 5, 1)
    patients = []

    for i in range(n):
        is_control = i >= n - 2
        has_ms = not is_control and random.random() < 0.8

        sex = random.choice(["Male", "Female"])
        height = random.randint(155, 190)
        weight = random.randint(50, 95)

        conditions = generate_conditions(has_ms, is_control)
        meds = generate_med_timeline(start_date, conditions, is_control)
        flares = generate_flare_periods(start_date, has_ms)

        patients.append({
            "id": f"patient_{str(i+1).zfill(3)}",
            "sex": sex,
            "height_cm": height,
            "weight_kg": weight,
            "has_ms": has_ms,
            "conditions": conditions,
            "medications": meds,
            "flares": flares
        })

    return patients

if __name__ == "__main__":
    patients = generate_patients()
    with open("mock_patients.json", "w") as f:
        json.dump(patients, f, indent=2, default=str)
