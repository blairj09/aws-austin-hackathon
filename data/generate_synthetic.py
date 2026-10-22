"""Generate deterministic synthetic patients: labs CSV, EKG CSV, profile JSON.

All values are made up. Nothing here is real patient data.

    uv run python data/generate_synthetic.py            # writes data/sample/
    uv run python data/generate_synthetic.py --out data/raw --seed 7
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FS = 250  # EKG sampling rate, Hz
SECONDS = 10

# test, panel, unit, ref_low, ref_high
REFERENCE = [
    ("hemoglobin", "CBC", "g/dL", 12.0, 16.0),
    ("wbc", "CBC", "10^3/uL", 4.0, 11.0),
    ("platelets", "CBC", "10^3/uL", 150, 400),
    ("sodium", "BMP", "mmol/L", 135, 145),
    ("potassium", "BMP", "mmol/L", 3.5, 5.0),
    ("creatinine", "BMP", "mg/dL", 0.6, 1.2),
    ("glucose", "BMP", "mg/dL", 70, 99),
    ("bun", "BMP", "mg/dL", 7, 20),
    ("total_cholesterol", "Lipids", "mg/dL", 0, 200),
    ("ldl", "Lipids", "mg/dL", 0, 100),
    ("hdl", "Lipids", "mg/dL", 40, 200),
    ("triglycerides", "Lipids", "mg/dL", 0, 150),
    ("hba1c", "Metabolic", "%", 4.0, 5.6),
    ("spo2", "Vitals", "%", 95, 100),
]

PATIENTS = {
    "P001": {
        "profile": {
            "patient_id": "P001",
            "name": "Maria (synthetic)",
            "age": 58,
            "sex": "F",
            "height_cm": 163,
            "weight_kg": 84,
            "history": ["type 2 diabetes (diet-controlled)", "hypertension"],
            "medications": ["lisinopril 10 mg daily"],
            "complaint": "Two weeks of palpitations and fatigue; mild shortness of breath on stairs.",
            "goals": "Wants to keep gardening and walking with her grandkids.",
            "imaging": {
                "chest_xray": None,
                "note": "Drop a public chest X-ray (e.g. NIH ChestX-ray14) at data/raw/P001_cxr.png to enable the Radiologist.",
            },
        },
        "labs": {
            "hemoglobin": 11.4, "wbc": 7.2, "platelets": 260, "sodium": 138,
            "potassium": 6.1, "creatinine": 1.4, "glucose": 162, "bun": 24,
            "total_cholesterol": 236, "ldl": 158, "hdl": 38, "triglycerides": 210,
            "hba1c": 7.4, "spo2": 94,
        },
        "ekg": {"rhythm": "afib", "mean_hr": 112},
    },
    "P002": {
        "profile": {
            "patient_id": "P002",
            "name": "Devon (synthetic)",
            "age": 34,
            "sex": "M",
            "height_cm": 180,
            "weight_kg": 77,
            "history": [],
            "medications": [],
            "complaint": "Annual physical; occasional knee pain after running.",
            "goals": "Train for a half marathon.",
            "imaging": {"chest_xray": None, "note": "No imaging ordered."},
        },
        "labs": {
            "hemoglobin": 14.8, "wbc": 6.1, "platelets": 240, "sodium": 140,
            "potassium": 4.2, "creatinine": 1.0, "glucose": 88, "bun": 14,
            "total_cholesterol": 182, "ldl": 104, "hdl": 52, "triglycerides": 96,
            "hba1c": 5.2, "spo2": 98,
        },
        "ekg": {"rhythm": "sinus", "mean_hr": 64},
    },
}


def labs_frame(patient_id: str, values: dict[str, float]) -> pd.DataFrame:
    rows = []
    for test, panel, unit, lo, hi in REFERENCE:
        v = values[test]
        flag = "L" if v < lo else "H" if v > hi else ""
        rows.append(dict(patient_id=patient_id, panel=panel, test=test, value=v,
                         unit=unit, ref_low=lo, ref_high=hi, flag=flag))
    return pd.DataFrame(rows)


def beat(t: np.ndarray, p_wave: bool = True) -> np.ndarray:
    """One PQRST complex as a sum of Gaussians, t in seconds from the R peak."""
    g = lambda mu, sd, a: a * np.exp(-((t - mu) ** 2) / (2 * sd**2))
    wave = g(0, 0.010, 1.2) + g(-0.025, 0.010, -0.15) + g(0.03, 0.012, -0.25) + g(0.25, 0.04, 0.3)
    if p_wave:
        wave += g(-0.18, 0.025, 0.12)
    return wave


def ekg_frame(patient_id: str, rhythm: str, mean_hr: float, rng: np.random.Generator) -> pd.DataFrame:
    n = FS * SECONDS
    t = np.arange(n) / FS
    rr_mean = 60 / mean_hr
    peaks, cur = [], 0.3
    while cur < SECONDS:
        peaks.append(cur)
        jitter = rng.uniform(-0.35, 0.35) if rhythm == "afib" else rng.normal(0, 0.02)
        cur += rr_mean * (1 + jitter)
    signal = np.zeros(n)
    for p in peaks:
        signal += beat(t - p, p_wave=(rhythm != "afib"))
    if rhythm == "afib":  # fibrillatory baseline instead of P waves
        signal += 0.04 * np.sin(2 * np.pi * 6.3 * t + rng.uniform(0, 6)) * rng.uniform(0.6, 1.0, n)
    signal += 0.05 * np.sin(2 * np.pi * 0.3 * t)  # baseline wander
    signal += rng.normal(0, 0.015, n)  # noise
    return pd.DataFrame({"patient_id": patient_id, "time_s": t.round(4), "mv": signal.round(4)})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(Path(__file__).parent / "sample"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)
    for pid, spec in PATIENTS.items():
        labs_frame(pid, spec["labs"]).to_csv(out / f"{pid}_labs.csv", index=False)
        ekg_frame(pid, spec["ekg"]["rhythm"], spec["ekg"]["mean_hr"], rng).to_csv(out / f"{pid}_ekg.csv", index=False)
        (out / f"{pid}_profile.json").write_text(json.dumps(spec["profile"], indent=2) + "\n")
        print(f"wrote {pid} -> {out}")


if __name__ == "__main__":
    main()
