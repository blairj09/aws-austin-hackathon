"""Care-team pipeline: route inputs to specialists, then the Doctor combines them.

    uv run python -m caregivers.orchestrator P001

Flow (every step is written to logs/<run>.jsonl):

    intake ─┬─ labs + EKG ─> Lab Analyst  (tools: lab_results, ekg_features, red_flag_check)
            └─ image ──────> Radiologist  (vision; skipped with a re-evaluation request if no image)
                                  │
                                  v
                               Doctor ──> consult_nutritionist ─> Nutritionist
                                  │   └─> consult_physio ───────> Physio
                                  v
                      patient-facing summary + provenance + disclaimer
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from chatlas import content_image_file

from . import personas
from .audit import AuditLog
from .config import MODEL_ID, make_chat
from .patient import ROOT, Patient, load_patient
from .tools import deterministic_red_flags, make_lab_tools, make_profile_tool

DISCLAIMER = (
    "_Hackathon prototype built on synthetic data. This is not medical advice "
    "and not a clinical system. A licensed clinician must review every finding._"
)


@dataclass
class Finding:
    persona: str
    inputs: list[str]
    text: str
    confidence: str = "unknown"
    red_flags: list[str] = field(default_factory=list)
    ok: bool = True


@dataclass
class RunResult:
    patient: Patient
    findings: dict[str, Finding]
    red_flags: list[str]
    summary: str
    log: AuditLog
    cost_usd: float | None = None


def _parse(persona: str, inputs: list[str], text: str) -> Finding:
    conf = re.search(r"CONFIDENCE:\s*(low|medium|high)", text, re.I)
    flags = re.search(r"RED_FLAGS:\s*(.+)", text, re.I)
    red = [] if not flags or flags.group(1).strip().lower().startswith("none") else [
        s.strip() for s in flags.group(1).split(",") if s.strip()
    ]
    body = re.sub(r"\n?(CONFIDENCE|RED_FLAGS):.*", "", text, flags=re.I).strip()
    return Finding(persona, inputs, body, conf.group(1).lower() if conf else "unknown", red)


def _context(p: Patient) -> str:
    prof = {k: v for k, v in p.profile.items() if not k.startswith("_")}
    return f"Patient {p.patient_id}: {prof['age']}{prof['sex']}. Complaint: {prof['complaint']} History: {', '.join(prof['history']) or 'none'}."


def run_lab_analyst(p: Patient, log: AuditLog) -> Finding:
    inputs = ["labs", "ekg"]
    log.log("handoff", "Intake", to="Lab Analyst", inputs=[p.sources[i] for i in inputs])
    chat = make_chat(personas.LAB_ANALYST)
    for fn in make_lab_tools(p):
        chat.register_tool(fn)
    log.watch(chat, "Lab Analyst")
    try:
        text = chat.chat(_context(p) + " Review the labs and EKG.", echo="none").get_content()
    except Exception as e:  # never crash the pipeline on one specialist
        log.log("error", "Lab Analyst", error=str(e), action="request clinical re-evaluation")
        return Finding("Lab Analyst", inputs, "Lab review failed. Request clinical re-evaluation of labs and EKG.", ok=False)
    f = _parse("Lab Analyst", inputs, text)
    log.log("finding", "Lab Analyst", confidence=f.confidence, red_flags=f.red_flags, text=f.text)
    return f


def run_radiologist(p: Patient, log: AuditLog) -> Finding:
    if not p.image_path:
        msg = "No image was provided. Radiology review skipped; request imaging if clinically indicated."
        log.log("handoff", "Intake", to="Radiologist", inputs=[], skipped=True, reason="no image")
        log.log("finding", "Radiologist", confidence="n/a", red_flags=[], text=msg)
        return Finding("Radiologist", [], msg, confidence="n/a", ok=False)
    log.log("handoff", "Intake", to="Radiologist", inputs=[str(p.image_path)])
    chat = make_chat(personas.RADIOLOGIST)
    try:
        text = chat.chat(_context(p) + " Review this image.", content_image_file(str(p.image_path), resize="high"), echo="none").get_content()
    except Exception as e:  # e.g. the model has no vision support
        log.log("error", "Radiologist", error=str(e), action="request clinical re-evaluation")
        return Finding("Radiologist", ["image"], "Image review failed. Request clinical re-evaluation by a radiologist.", ok=False)
    f = _parse("Radiologist", ["image"], text)
    log.log("finding", "Radiologist", confidence=f.confidence, red_flags=f.red_flags, text=f.text)
    return f


def _consult(name: str, system_prompt: str, p: Patient, log: AuditLog):
    """Build a tool that hands a question to another specialist agent."""

    def consult(question: str) -> str:
        log.log("handoff", "Doctor", to=name, question=question)
        chat = make_chat(system_prompt)
        chat.register_tool(make_profile_tool(p))
        log.watch(chat, name)
        try:
            text = chat.chat(_context(p) + "\n\nDoctor's question: " + question, echo="none").get_content()
        except Exception as e:
            log.log("error", name, error=str(e), action="request clinical re-evaluation")
            return f"{name} was unavailable. Recommend an in-person {name.lower()} review."
        log.log("finding", name, text=text)
        return text

    return consult


def run_doctor(p: Patient, findings: dict[str, Finding], red_flags: list[str], log: AuditLog) -> str:
    chat = make_chat(personas.DOCTOR)

    def consult_nutritionist(question: str) -> str:
        """Ask the Nutritionist for an eating plan. Include any lab constraints in the question."""
        return _consult("Nutritionist", personas.NUTRITIONIST, p, log)(question)

    def consult_physio(question: str) -> str:
        """Ask the Physiotherapist for an exercise plan. Include any safety limits in the question."""
        return _consult("Physio", personas.PHYSIO, p, log)(question)

    chat.register_tool(consult_nutritionist)
    chat.register_tool(consult_physio)
    log.watch(chat, "Doctor")

    report = "\n\n".join(
        f"## {f.persona} (confidence: {f.confidence})\nRed flags: {', '.join(f.red_flags) or 'none'}\n\n{f.text}"
        for f in findings.values()
    )
    flags = "\n".join(f"- {r}" for r in red_flags) or "- none"
    prompt = (
        f"{_context(p)}\nGoals: {p.profile.get('goals', '')}\n\n"
        f"Specialist findings:\n\n{report}\n\n"
        f"Red flags from the code-side safety check (always honor these):\n{flags}"
    )
    try:
        return chat.chat(prompt, echo="none").get_content()
    except Exception as e:
        log.log("error", "Doctor", error=str(e), action="request clinical re-evaluation")
        return "The care team could not finish this review. Please request a clinical re-evaluation."


def provenance_table(p: Patient, findings: dict[str, Finding]) -> str:
    rows = ["| Persona | Inputs reviewed | Confidence | Status |", "|---|---|---|---|"]
    for f in findings.values():
        srcs = ", ".join(f"`{p.sources.get(i, i)}`" for i in f.inputs) or "none"
        rows.append(f"| {f.persona} | {srcs} | {f.confidence} | {'done' if f.ok else 'skipped: no input' if not f.inputs else 'needs re-evaluation'} |")
    rows.append("| Nutritionist, Physio | patient profile + Doctor's question | n/a | consulted by Doctor |")
    return "\n".join(rows)


def run_care_team(
    patient_id: str = "P001",
    log_path: Path | str | None = "auto",
    listeners=None,
    image=None,
    patient: Patient | None = None,
) -> RunResult:
    p = patient or load_patient(patient_id, image=image)
    patient_id = p.patient_id
    if log_path == "auto":
        log_path = ROOT / "logs" / f"{patient_id}-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    log = AuditLog(Path(log_path) if log_path else None, listeners=list(listeners or []))
    log.log("start", "Intake", patient=patient_id, model=MODEL_ID, sources=p.sources)

    red_flags = deterministic_red_flags(p)
    for r in red_flags:
        log.log("red_flag", "Safety check", flag=r, action="requires clinician confirmation")

    findings = {
        "Lab Analyst": run_lab_analyst(p, log),
        "Radiologist": run_radiologist(p, log),
    }
    log.log("handoff", "Intake", to="Doctor", inputs=list(findings))
    answer = run_doctor(p, findings, red_flags, log)

    banner = ""
    if red_flags:
        banner = "> **⚠ Needs clinician confirmation:** " + "; ".join(red_flags) + "\n\n"
    summary = (
        f"{banner}{answer}\n\n### Who looked at what\n\n{provenance_table(p, findings)}\n\n{DISCLAIMER}\n"
    )
    log.log("final", "Doctor", chars=len(summary))
    return RunResult(p, findings, red_flags, summary, log)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run the Track 1 care team on one synthetic patient.")
    ap.add_argument("patient_id", nargs="?", default="P001")
    ap.add_argument("--image", help="Optional path to a public chest X-ray for the Radiologist")
    ap.add_argument("--out", help="Also write the patient-facing summary to this markdown file")
    args = ap.parse_args()

    def show(e: dict) -> None:
        detail = e.get("to") or e.get("tool") or e.get("flag") or e.get("error") or ""
        print(f"[{e['t']:>6.1f}s] {e['kind']:<11} {e['actor']:<13} {detail}")

    result = run_care_team(args.patient_id, listeners=[show], image=args.image)
    print("\n" + result.summary)
    print(f"Audit log: {result.log.path}")
    if args.out:
        Path(args.out).write_text(result.summary)


if __name__ == "__main__":
    main()
