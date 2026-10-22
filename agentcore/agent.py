"""Expose the care team as an Amazon Bedrock AgentCore Runtime.

Same handler shape as the event kit's agent.py
(https://atx.rahman.dev/hackathon-kit.zip). Payloads:

    {"patient_id": "P001"}                       # bundled synthetic patient
    {"profile": {...}, "labs": [...], "ekg": {"time_s": [...], "mv": [...]}}

Local test (no deploy):  uv run --extra agentcore python agentcore/agent.py --once P002
Deploy: see agentcore/README.md.
"""

import sys
from pathlib import Path

import pandas as pd
from bedrock_agentcore.runtime import BedrockAgentCoreApp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from caregivers.config import MODEL_ID  # noqa: E402
from caregivers.orchestrator import run_care_team  # noqa: E402
from caregivers.patient import Patient  # noqa: E402

app = BedrockAgentCoreApp()


def _patient_from_payload(payload: dict) -> Patient | None:
    if "labs" not in payload:
        return None
    profile = payload["profile"]
    return Patient(
        patient_id=profile.get("patient_id", "inline"),
        profile={**profile, "_dir": "payload"},
        labs=pd.DataFrame(payload["labs"]),
        ekg=pd.DataFrame(payload["ekg"]),
    )


@app.entrypoint
def invoke(payload):
    result = run_care_team(
        payload.get("patient_id", "P001"),
        log_path=None,  # the runtime filesystem is ephemeral; events are returned instead
        patient=_patient_from_payload(payload),
    )
    return {
        "model": MODEL_ID,
        "patient_id": result.patient.patient_id,
        "red_flags": result.red_flags,
        "summary_markdown": result.summary,
        "events": result.log.events,
    }


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--once":
        out = invoke({"patient_id": sys.argv[2]})
        print({k: v for k, v in out.items() if k != "events"} | {"events": len(out["events"])})
    else:
        app.run()
