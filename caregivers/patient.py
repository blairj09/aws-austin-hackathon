"""Load one synthetic patient: profile JSON, labs CSV, EKG CSV, optional image."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "data" / "sample"
RAW_DIR = ROOT / "data" / "raw"


@dataclass
class Patient:
    patient_id: str
    profile: dict
    labs: pd.DataFrame
    ekg: pd.DataFrame
    image_path: Path | None = None

    @property
    def sources(self) -> dict[str, str]:
        """Provenance: where each input came from."""
        d = self.profile.get("_dir", str(SAMPLE_DIR))
        out = {
            "profile": f"{d}/{self.patient_id}_profile.json",
            "labs": f"{d}/{self.patient_id}_labs.csv",
            "ekg": f"{d}/{self.patient_id}_ekg.csv",
        }
        if self.image_path:
            out["image"] = str(self.image_path)
        return out


def load_patient(patient_id: str, data_dir: Path | str = SAMPLE_DIR, image: Path | str | None = None) -> Patient:
    data_dir = Path(data_dir)
    profile = json.loads((data_dir / f"{patient_id}_profile.json").read_text())
    profile["_dir"] = str(data_dir.relative_to(ROOT)) if data_dir.is_relative_to(ROOT) else str(data_dir)
    labs = pd.read_csv(data_dir / f"{patient_id}_labs.csv")
    ekg = pd.read_csv(data_dir / f"{patient_id}_ekg.csv")
    if image is None:
        for ext in ("png", "jpg", "jpeg"):
            cand = RAW_DIR / f"{patient_id}_cxr.{ext}"
            if cand.exists():
                image = cand
                break
    return Patient(patient_id, profile, labs, ekg, Path(image) if image else None)


def list_patients(data_dir: Path | str = SAMPLE_DIR) -> list[str]:
    return sorted(p.name.split("_")[0] for p in Path(data_dir).glob("*_profile.json"))
