# Deploy the care team to Amazon Bedrock AgentCore

`agent.py` uses the same `BedrockAgentCoreApp` entrypoint shape as the event
kit's `agent.py`. It accepts `{"patient_id": "P001"}` or an inline patient
(`profile`, `labs` rows, and `ekg` columns). It returns the summary, the red
flags, and the full event list.

**Test locally first.** This runs the whole pipeline once and doesn't deploy
anything:

```bash
uv sync --extra agentcore
uv run --extra agentcore python agentcore/agent.py --once P002
```

**Deploy.** Follow the event kit's README
(<https://atx.rahman.dev/hackathon-kit.zip>) to create the execution role with
`setup_agentcore_role.py`. Then run this from the repo root:

```bash
export AWS_REGION=us-east-1
export BEDROCK_MODEL_ID=${BEDROCK_MODEL_ID:-us.openai.gpt-5.6-luna}
uv run --extra agentcore agentcore configure \
  --entrypoint agentcore/agent.py \
  --name caregivers_team \
  --region "$AWS_REGION" \
  --deployment-type direct_code_deploy \
  --requirements-file agentcore/requirements.txt \
  --execution-role "$AGENTCORE_EXECUTION_ROLE_ARN" \
  --disable-otel --disable-memory --non-interactive
uv run --extra agentcore agentcore deploy --agent caregivers_team --env "BEDROCK_MODEL_ID=$BEDROCK_MODEL_ID"
uv run --extra agentcore agentcore invoke '{"patient_id":"P002"}' --agent caregivers_team
```

Notes:

- The kit's role only allows the inference profile you chose when you created
  it. If you change `BEDROCK_MODEL_ID`, recreate the role.
- The `{"patient_id": ...}` form needs `caregivers/` and `data/sample/` in the
  deployed bundle. If the toolkit packages only the entrypoint's folder, send an
  inline patient instead.
- A full run makes 4–5 model calls and takes about 1 minute. Runtimes cost
  money, so delete the runtime and its role when you're done.
