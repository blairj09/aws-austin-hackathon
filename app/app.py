"""Care-team demo app: patient inputs, live handoff timeline, patient-facing summary.

    uv run shiny run app/app.py            # then open http://127.0.0.1:8000
In Positron: open this file and press the Run App button.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from shiny import App, reactive, render, ui
from shinychat import Chat, chat_ui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from caregivers import personas  # noqa: E402
from caregivers.config import MODEL_ID, make_chat  # noqa: E402
from caregivers.orchestrator import DISCLAIMER, run_care_team  # noqa: E402
from caregivers.patient import list_patients, load_patient  # noqa: E402

ICONS = {
    "start": "🩺", "handoff": "➡️", "tool_call": "🔧", "tool_result": "📎",
    "finding": "📝", "red_flag": "⚠️", "error": "❌", "final": "✅",
}

app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.input_select("patient", "Synthetic patient", choices=list_patients()),
        ui.input_task_button("run", "Run care team", label_busy="Care team working…"),
        ui.markdown(f"**Model:** `{MODEL_ID}`  \n**Region:** us-east-1"),
        ui.hr(),
        ui.markdown(DISCLAIMER),
        width=320,
    ),
    ui.layout_columns(
        ui.card(ui.card_header("Patient"), ui.output_ui("profile")),
        ui.card(ui.card_header("Labs (flagged values highlighted)"), ui.output_data_frame("labs")),
        ui.card(ui.card_header("EKG (10 s)"), ui.output_plot("ekg", height="220px")),
        col_widths=[3, 5, 4],
    ),
    ui.layout_columns(
        ui.card(ui.card_header("Handoff timeline"), ui.output_ui("timeline"), max_height="520px"),
        ui.card(ui.card_header("For the patient"), ui.output_ui("summary"), max_height="520px"),
        col_widths=[4, 8],
    ),
    ui.card(
        ui.card_header("Ask the care team a follow-up question"),
        chat_ui("followup", placeholder="e.g. Why does potassium matter for my heart?", height="300px"),
    ),
    title="Caregivers Challenge · care-team prototype",
    fillable=False,
)


def server(input, output, session):
    events: list[dict] = []
    followup = Chat("followup")
    doctor = reactive.value(None)

    @reactive.calc
    def patient():
        return load_patient(input.patient())

    @render.ui
    def profile():
        p = patient().profile
        return ui.markdown(
            f"**{p['name']}**, {p['age']}{p['sex']}  \n"
            f"**Complaint:** {p['complaint']}  \n"
            f"**History:** {', '.join(p['history']) or 'none'}  \n"
            f"**Medications:** {', '.join(p['medications']) or 'none'}  \n"
            f"**Goals:** {p.get('goals', '')}"
        )

    @render.data_frame
    def labs():
        df = patient().labs[["panel", "test", "value", "unit", "ref_low", "ref_high", "flag"]]
        flagged = df.index[df["flag"].fillna("") != ""].tolist()
        return render.DataGrid(
            df, height="260px",
            styles=[{"rows": flagged, "style": {"background-color": "#FBE3D8", "font-weight": "600"}}],
        )

    @render.plot
    def ekg():
        e = patient().ekg
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.plot(e["time_s"], e["mv"], lw=0.8, color="#447099")
        ax.set_xlabel("seconds")
        ax.set_ylabel("mV")
        ax.spines[["top", "right"]].set_visible(False)
        return fig

    @ui.bind_task_button(button_id="run")
    @reactive.extended_task
    async def care_team(pid: str):
        return await asyncio.to_thread(run_care_team, pid, listeners=[events.append])

    @reactive.effect
    @reactive.event(input.run)
    def _start():
        events.clear()
        care_team(input.patient())

    @render.ui
    def timeline():
        if care_team.status() == "running":
            reactive.invalidate_later(0.7)
        if not events:
            return ui.markdown("_Press **Run care team** to start._")
        items = []
        for e in list(events):
            if e["kind"] == "tool_result":
                continue
            detail = e.get("to") or e.get("tool") or e.get("flag") or e.get("error") or e.get("confidence") or ""
            items.append(
                ui.tags.li(
                    ui.tags.code(f"{e['t']:.0f}s"), " ", ICONS.get(e["kind"], "•"), " ",
                    ui.tags.b(e["actor"]), f" · {e['kind'].replace('_', ' ')} ", ui.tags.span(str(detail)),
                )
            )
        return ui.tags.ul(*items, style="list-style:none; padding-left:0; font-size:0.9em;")

    @render.ui
    def summary():
        if care_team.status() == "initial":
            return ui.markdown("_The patient-facing summary appears here._")
        if care_team.status() == "running":
            return ui.markdown("_The care team is reviewing the inputs…_")
        if care_team.status() == "error":
            return ui.markdown("The run failed. Please request a clinical re-evaluation. Check the console for details.")
        return ui.markdown(care_team.result().summary)

    @reactive.effect
    def _seed_followup():
        if care_team.status() != "success":
            return
        system = (
            "You are the Doctor who led this patient's care team. Answer the patient's "
            "follow-up questions in plain language, using only this summary:\n\n"
            + care_team.result().summary + personas.SAFETY
        )
        doctor.set(make_chat(system))

    @followup.on_user_submit
    async def _answer(user_input: str):
        chat = doctor()
        if chat is None:
            await followup.append_message("Run the care team first, then ask a follow-up.")
            return
        stream = await chat.stream_async(user_input)
        await followup.append_message_stream(stream)


app = App(app_ui, server)
