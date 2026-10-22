# Track 1 ideas

Every idea has to hit the demo checklist: **one patient scenario**, **at least
two specialist handoffs**, and a **clear patient-facing result**. It also has to
show provenance, uncertainty, and reasoning. The question the judges will ask:
*can five specialized perspectives become one answer a patient actually
understands?*

Difficulty: ★ = a few hours on top of this starter, ★★★ = the whole day.

## Best bets

### 1. "Care team in a room": visible multi-agent consult (recommended)

The starter already does most of this. Polish it into a strong demo.

- **Flow:** Intake routes labs and EKG to the Lab Analyst and the image to the
  Radiologist. The Doctor then consults the Nutritionist and the Physio *as
  tools* and writes the patient summary.
- **Data:** synthetic P001 (high potassium, irregular fast rhythm) plus one
  NIH ChestX-ray14 image.
- **AWS:** Bedrock (Converse), optionally deployed on AgentCore.
- **Front end:** the Shiny app, with a live handoff timeline, a provenance
  table, and follow-up chat.
- **Wow moment:** the timeline fills in live, "⚠ Needs clinician confirmation"
  appears *before* the model even answers (a code-side check), and the
  Physio's plan changes because of the Lab Analyst's potassium finding. That's
  a cross-specialist handoff the audience can see.
- **Difficulty:** ★ to reach a demo, ★★ with the radiology image and AgentCore.

### 2. "Explain it like I'm the patient": a reading-level and language toggle

Build on idea 1. Add a **Patient voice** agent that rewrites the final answer
for different audiences: 5th-grade reading level, Spanish, or a caregiver
(an adult child) instead of the patient. Then add a **"Why do you say
that?"** button that cites the exact lab row or tool result behind each
sentence.

- **Wow moment:** click a sentence and highlight the lab row it came from.
  That's provenance you can see.
- **Difficulty:** ★★

## More ideas

### 3. Disagreement and second opinion

Run two Radiologist agents on different models (for example GPT-5.6 Sol and
Claude), or a Radiologist plus a Lab Analyst, that might disagree. Then add a
**Doctor arbitration** step that states the disagreement and its effect on
confidence.

- **Handoffs:** Radiologist A, Radiologist B, and Doctor. **Data:** NIH
  ChestX-ray14 images with their labels as ground truth.
- **Wow moment:** a confidence meter that drops when specialists disagree,
  followed by "requesting human re-read".
- **Difficulty:** ★★

### 4. EKG triage agent with real signal processing

Give the Lab Analyst better tools: R-peak detection, HRV, and a rhythm
classifier on public PhysioNet-style traces, or traces we generate. The model
calls the tools and explains the result. It never "eyeballs" raw numbers.

- **Wow moment:** the Plots pane in Positron (or the app) shows the trace
  with the detected beats and the irregular intervals highlighted.
- **Difficulty:** ★★

### 5. Longitudinal patient: "what changed since last visit?"

Generate three visits for one synthetic patient. The Lab Analyst compares
trends, the Doctor explains what got better or worse, and the Nutritionist and
Physio adjust their plans.

- **Wow moment:** a sparkline per lab with the agent's one-line explanation
  next to it.
- **Difficulty:** ★★

### 6. Case-report retrieval (RAG over MultiCaRe)

Index a slice of [MultiCaRe](https://www.kaggle.com/datasets/mauronievasoffidani/multicare)
case reports. The Doctor agent gets a `similar_cases(query)` tool and cites the
two closest public cases, labeled as reference only.

- **Wow moment:** "Patients with a similar picture in the literature…"
  with links to the cases.
- **Difficulty:** ★★★ (indexing takes time; keep the slice small)

### 7. Caregiver handoff packet

The output is a one-page Quarto PDF or HTML for the caregiver: medication
questions, a shopping list from the Nutritionist, a week-one exercise card from
the Physio, and the red-flag symptoms on the back.

- **Wow moment:** one click renders a printable packet.
- **Difficulty:** ★ (Quarto is already in Positron)

### 8. Visual QA with PathVQA

The Radiologist answers structured image questions from
[PathVQA](https://huggingface.co/datasets/flant5/pathvqa). We score it against
the gold answers live, which shows uncertainty honestly.

- **Difficulty:** ★★

## Suggested plan for the day (team of 3–4)

| Who | Owns |
|---|---|
| **Agent lead** | `caregivers/`: persona prompts, tool quality, red-flag rules, model choice |
| **Data lead** | Get one real public chest X-ray working end to end, improve the EKG tool, and add the second visit (idea 5) if there's time |
| **App lead** | `app/app.py`: timeline polish, provenance view, and the Posit or AWS look of the demo |
| **Story lead** (or shared) | Demo script, AgentCore deploy, slides, and the "not medical advice" framing |

| Time | Milestone |
|---|---|
| First 30 min | Everyone runs `scripts/smoke_test.py`. Kick off the Positron on SageMaker setup (it takes 20–30 minutes). Pick idea 1 plus one add-on. |
| +1.5 h | The orchestrator runs end to end on the event account. The app shows the timeline. |
| +3 h | Radiologist works with a real image. The add-on (idea 2, 3, or 7) is wired in. |
| +4.5 h | Freeze features. Optional AgentCore deploy. Record a backup video of the demo. |
| Last hour | Rehearse the 3-minute story: patient → handoffs → patient answer → audit log. |

## Demo script (3 minutes)

1. "Meet Maria (synthetic): palpitations and fatigue." Show the labs and the
   EKG in the app.
2. Click **Run care team**. Narrate the timeline: Intake hands off to the Lab
   Analyst, which calls its tools. The red flag fires. The Doctor consults
   the Nutritionist and the Physio.
3. Show the patient-facing answer: the warning first, then the plan in plain
   language.
4. Show the provenance table and the JSONL audit log. Every claim traces back
   to an input.
5. Ask a follow-up question in the chat.
6. Close with: "Prototype, synthetic data, not medical advice. A clinician
   confirms every red flag."
