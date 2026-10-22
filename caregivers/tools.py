"""Deterministic tools the personas call. The model reasons; code does the math.

Each `make_*` function binds tools to one patient so the model never handles
file paths or raw arrays.
"""

from __future__ import annotations

import json

import numpy as np
from scipy.signal import find_peaks

from .patient import Patient

# Values that need a human before any care action. Thresholds are illustrative.
CRITICAL = {
    "potassium": (3.0, 6.0),
    "sodium": (125, 155),
    "glucose": (54, 400),
    "hemoglobin": (7.0, None),
    "spo2": (90, None),  # below 90% = significant hypoxia
    "heart_rate": (40, 130),
}


def red_flags_for(name: str, value: float) -> str | None:
    lo, hi = CRITICAL.get(name, (None, None))
    if lo is not None and value < lo:
        return f"{name}={value} is critically low (< {lo})"
    if hi is not None and value >= hi:
        return f"{name}={value} is critically high (>= {hi})"
    return None


def ekg_summary(patient: Patient) -> dict:
    """Heart rate and rhythm regularity from the raw EKG trace."""
    fs = 1 / float(np.median(np.diff(patient.ekg["time_s"])))
    x = patient.ekg["mv"].to_numpy()
    x = x - np.convolve(x, np.ones(int(fs)) / int(fs), mode="same")  # remove baseline wander
    peaks, _ = find_peaks(x, height=0.5 * np.max(x), distance=int(0.25 * fs))
    rr = np.diff(peaks) / fs
    hr = 60 / rr.mean() if len(rr) else float("nan")
    cv = rr.std() / rr.mean() if len(rr) > 1 else float("nan")
    rmssd = float(np.sqrt(np.mean(np.diff(rr) ** 2)) * 1000) if len(rr) > 2 else float("nan")
    return {
        "sampling_hz": round(fs),
        "duration_s": round(len(x) / fs, 1),
        "beats_detected": int(len(peaks)),
        "mean_heart_rate_bpm": float(round(hr, 1)),
        "rr_interval_cv": float(round(cv, 3)),
        "rmssd_ms": round(rmssd, 1),
        "rhythm_hint": "irregular (possible atrial fibrillation)" if cv > 0.12 else "regular",
        "note": "Computed from a synthetic trace with a simple peak detector; not a diagnostic read.",
    }


def make_lab_tools(patient: Patient):
    def lab_results(panel: str = "all") -> str:
        """Return the patient's lab results with units, reference ranges, and H/L flags.

        Parameters
        ----------
        panel
            One of "all", "CBC", "BMP", "Lipids", "Metabolic", "Vitals".
        """
        df = patient.labs
        if panel != "all":
            df = df[df["panel"].str.lower() == panel.lower()]
        cols = ["panel", "test", "value", "unit", "ref_low", "ref_high", "flag"]
        return df[cols].to_csv(index=False)

    def ekg_features() -> str:
        """Compute heart rate, RR-interval variability, and a rhythm hint from the patient's EKG trace."""
        return json.dumps(ekg_summary(patient))

    def red_flag_check(test: str, value: float) -> str:
        """Check whether a value crosses a critical threshold that needs clinician confirmation.

        Parameters
        ----------
        test
            Lab or vital name, e.g. "potassium", "spo2", "glucose", "heart_rate".
        value
            The measured value in the lab's units.
        """
        return red_flags_for(test, value) or f"{test}={value}: no critical threshold crossed"

    return [lab_results, ekg_features, red_flag_check]


def make_profile_tool(patient: Patient):
    def patient_profile() -> str:
        """Return the patient's age, sex, height, weight, BMI, history, medications, and goals."""
        p = {k: v for k, v in patient.profile.items() if not k.startswith("_") and k != "imaging"}
        p["bmi"] = round(p["weight_kg"] / (p["height_cm"] / 100) ** 2, 1)
        return json.dumps(p)

    return patient_profile


def deterministic_red_flags(patient: Patient) -> list[str]:
    """Code-side red-flag scan, independent of the model."""
    flags = [
        f for test, value in zip(patient.labs["test"], patient.labs["value"])
        if (f := red_flags_for(test, float(value)))
    ]
    hr = ekg_summary(patient)["mean_heart_rate_bpm"]
    if (f := red_flags_for("heart_rate", hr)):
        flags.append(f)
    return flags
