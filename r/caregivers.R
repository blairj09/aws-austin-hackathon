# Track 1 care team in R with ellmer, on Amazon Bedrock.
#
#   AWS_REGION=us-east-1 Rscript r/caregivers.R            # from the repo root
#   or open in Positron and source it line by line.
#
# Three personas: Lab Analyst (tools) -> Doctor -> Nutritionist (agent as a tool).
# Hackathon prototype on synthetic data. Not medical advice.

library(ellmer)
library(jsonlite)

model <- Sys.getenv("BEDROCK_MODEL_ID", "us.openai.gpt-5.6-luna")
if (Sys.getenv("AWS_REGION") == "") Sys.setenv(AWS_REGION = "us-east-1")

patient_id <- "P001"
labs <- read.csv(file.path("data", "sample", paste0(patient_id, "_labs.csv")))
profile <- fromJSON(file.path("data", "sample", paste0(patient_id, "_profile.json")))

safety <- "This is a hackathon prototype on synthetic data, not medical advice. Never invent values."
audit <- list()
log_event <- function(kind, actor, ...) {
  audit[[length(audit) + 1]] <<- list(kind = kind, actor = actor, ...)
  cat(sprintf("%-10s %-13s %s\n", kind, actor, paste(c(...), collapse = " ")))
}

# Tools return JSON strings (ellmer 0.5 deprecates returning plain R lists).
lab_results <- tool(
  function(panel = "all") {
    out <- if (panel == "all") labs else labs[labs$panel == panel, ]
    toJSON(out[, c("test", "value", "unit", "ref_low", "ref_high", "flag")])
  },
  name = "lab_results",
  description = "Return the patient's labs with reference ranges and H/L flags.",
  arguments = list(
    panel = type_enum(c("all", "CBC", "BMP", "Lipids", "Metabolic", "Vitals"), "Which panel", required = FALSE)
  )
)

critical <- list(potassium = c(3.0, 6.0), sodium = c(125, 155), glucose = c(54, 400), spo2 = c(90, Inf))
red_flag_check <- tool(
  function(test, value) {
    lim <- critical[[test]]
    flag <- !is.null(lim) && (value < lim[1] || value >= lim[2])
    toJSON(list(test = test, value = value, needs_clinician = flag), auto_unbox = TRUE)
  },
  name = "red_flag_check",
  description = "Check whether a lab value crosses a critical threshold that needs clinician confirmation.",
  arguments = list(test = type_string("Lab name, e.g. potassium"), value = type_number("Measured value"))
)

# 1. Lab Analyst ------------------------------------------------------------
log_event("handoff", "Intake", "-> Lab Analyst")
lab_analyst <- chat_aws_bedrock(
  model = model, echo = "none",
  system_prompt = paste(
    "You are the Lab Analyst on a care team. Call lab_results, then red_flag_check",
    "for each abnormal value. Report out-of-range values, patterns, and red flags",
    "in under 150 words. End with 'CONFIDENCE: low|medium|high'.", safety
  )
)
lab_analyst$register_tools(list(lab_results, red_flag_check))
lab_analyst$on_tool_request(function(request) log_event("tool_call", "Lab Analyst", request@name))
lab_findings <- lab_analyst$chat(paste("Patient complaint:", profile$complaint))

# 2. Nutritionist, exposed to the Doctor as a tool --------------------------
consult_nutritionist <- tool(
  function(question) {
    log_event("handoff", "Doctor", "-> Nutritionist")
    nutritionist <- chat_aws_bedrock(
      model = model, echo = "none",
      system_prompt = paste("You are a Nutritionist. Give at most 6 plain-language bullets.", safety)
    )
    nutritionist$chat(paste0("Patient goals: ", profile$goals, "\nDoctor's question: ", question))
  },
  name = "consult_nutritionist",
  description = "Ask the Nutritionist for an eating plan. Include lab constraints in the question.",
  arguments = list(question = type_string("A specific question for the Nutritionist"))
)

# 3. Doctor combines everything for the patient -------------------------------
log_event("handoff", "Intake", "-> Doctor")
doctor <- chat_aws_bedrock(
  model = model, echo = "none",
  system_prompt = paste(
    "You are the Doctor leading a care team. Call consult_nutritionist once, then write",
    "a short patient-friendly summary (8th-grade reading level) with: What we found,",
    "How sure we are, Food plan, When to get help. If there are red flags, start with",
    "a warning that a clinician must confirm them before any action.", safety
  )
)
doctor$register_tool(consult_nutritionist)
summary <- doctor$chat(paste("Lab Analyst findings:\n", lab_findings))

cat("\n", summary, "\n\n")
cat("_Hackathon prototype built on synthetic data. Not medical advice._\n")
dir.create("logs", showWarnings = FALSE)
write_json(audit, file.path("logs", paste0(patient_id, "-r-audit.json")), auto_unbox = TRUE, pretty = TRUE)
