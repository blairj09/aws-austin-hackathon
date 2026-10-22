# Using Positron at the hackathon

[Positron](https://positron.posit.co/) is Posit's data science IDE for Python
and R. At this event you can run it **inside your AWS account on Amazon
SageMaker** (optional), and you can keep using it **free on your laptop**
afterwards.

## Set up Positron on SageMaker (start this early)

The setup takes **20–30 minutes**, so start it while your team is still
choosing an idea.

1. Sign in through Workshop Studio and open the workshop terminal (VS Code
   web). The [login walkthrough](https://atx.rahman.dev/hackathon-login.mp4)
   shows how.
2. Run the setup script:

   ```bash
   unset AWS_PROFILE   # use the workshop's pre-authenticated session
   curl -O https://atx.rahman.dev/setup_positron_sagemaker_from_private_ecr.py
   uv run setup_positron_sagemaker_from_private_ecr.py
   ```

   The script works in `us-east-1`. It creates (or reuses) a SageMaker domain
   called `positron-workshop`, a user called `participant`, and a JupyterLab
   Space called `positron-test` on `ml.t3.xlarge` with the Positron image. It's
   safe to rerun if it stops partway.
3. Open the **Studio URL** it prints **within 5 minutes**, because the link
   expires. If it expires, rerun the script to get a new one. Treat the URL
   like a password.
4. The first start of the Space takes about 5–6 minutes while it pulls the
   image.

### Prompts you'll see (all expected)

| You see | Do this |
|---|---|
| An **Education License** banner | Dismiss it. The event uses a short-term license. |
| **"Trust Folder & Continue"** (Restricted Mode) | Click **Trust**. Until you do, the Python and R consoles and the terminal won't start, and the Welcome page says the extensions aren't available. |
| **"Create a virtual environment?"** for the Conda Python | Click **Not Now**, or let `uv sync` create `.venv` for this repo and select it as the interpreter. |

### Why use it here

- **No credential juggling.** Inside the Space, boto3, chatlas, ellmer, and
  the AWS CLI all use the Space's execution role. The workshop terminal's CLI
  credentials expire every 60 minutes, but the Space's don't.
- **Posit Assistant is already connected to Amazon Bedrock** through that same
  role, with no API keys to set up. Open it from the activity bar.
- **Python and R side by side,** with a Variables pane, Data Explorer, Plots
  pane, and Viewer for Shiny apps.

## Get this repo into Positron

In a Positron terminal:

```bash
git clone https://github.com/blairj09/aws-austin-hackathon.git
cd aws-austin-hackathon
uv sync
uv run python scripts/smoke_test.py
```

Then use **File → Open Folder** to open `aws-austin-hackathon`, and pick
`.venv` as the Python interpreter.

## Explore the data

- **Labs in the Data Explorer:** run
  `import pandas as pd; labs = pd.read_csv("data/sample/P001_labs.csv")` in the
  Python console, then click the table icon next to `labs` in the Variables
  pane. Sort by `flag`, or filter `panel == "BMP"`. In R, use
  `labs <- read.csv("data/sample/P001_labs.csv")`, then `View(labs)`.
- **EKG in the Plots pane:**

  ```python
  import pandas as pd, matplotlib.pyplot as plt
  ekg = pd.read_csv("data/sample/P001_ekg.csv")
  plt.plot(ekg.time_s, ekg.mv, lw=0.7); plt.xlabel("seconds"); plt.show()
  ```

- **Tool output without the model:**

  ```python
  from caregivers.patient import load_patient
  from caregivers.tools import ekg_summary, deterministic_red_flags
  p = load_patient("P001"); ekg_summary(p), deterministic_red_flags(p)
  ```

## Posit Assistant prompts to try for this track

- "Load `data/sample/P001_labs.csv` and show me which values are out of range,
  grouped by panel."
- "Plot the EKG in `data/sample/P001_ekg.csv`, detect R-peaks, and mark
  irregular RR intervals."
- "Add a new tool to `caregivers/tools.py` that computes eGFR from creatinine,
  age, and sex, and register it with the Lab Analyst."
- "Write a pytest for `deterministic_red_flags` that covers potassium 6.1 and
  SpO₂ 88."
- "Add a 'Patient voice' agent to `caregivers/orchestrator.py` that rewrites
  the summary at a 5th-grade reading level."
- "Make the handoff timeline in `app/app.py` look like a vertical stepper,
  with one color per persona."

## Run the Shiny app in Positron

Open `app/app.py` and click **Run App** (▶) in the editor toolbar. Or run this
in the terminal:

```bash
uv run shiny run app/app.py
```

The app opens in Positron's Viewer. On SageMaker, the Viewer goes through the
Space's proxy, so you don't need to open any ports.

## After the event: Positron Desktop

Positron is **free** for Windows, macOS, and Linux:
<https://positron.posit.co/download>. Everything in this repo runs the same way
on your laptop.

- For Bedrock from your laptop, sign in with your own AWS account
  (`aws configure sso` or `aws sso login`) and set `AWS_PROFILE` and
  `AWS_REGION`. chatlas and ellmer use the standard AWS credential chain.
- Without AWS, change `make_chat()` in `caregivers/config.py` to another
  chatlas provider (for example `ChatAnthropic`, `ChatOpenAI`, or `ChatOllama`
  for local models). In R, use the matching `ellmer::chat_*()` function.
