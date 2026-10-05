# AI Agent Model Configuration — Review & Matrix

A per-agent review of how each AI agent in `ai-message-triage` is wired to its
model and to other services, and what has to change to run on OpenShift. For the
OpenShift demo, all agents default to one MaaS endpoint and `qwen3-235b`.

Companion docs: [`OPENSHIFT.md`](OPENSHIFT.md) (Kafka), [`.env.openshift.example`](.env.openshift.example) (fill-in template).

## How config works (the pattern)

Every agent that calls an LLM uses the **OpenAI-compatible client**:

```python
from openai import OpenAI
llmclient = OpenAI(api_key=API_KEY, base_url=INFERENCE_SERVER_URL)
```

and resolves those three locals from an optional per-agent prefix, falling back
to the shared `API_KEY`, `INFERENCE_SERVER_URL`, and `MODEL_NAME`. Nothing about
the credentials is hardcoded in the pipeline.

> The shared settings are sufficient for the demo. Set prefixed variables such
> as `GUARDIAN_MODEL_NAME` only when an agent needs an override.

> ⚠️ **Always change `*_SERVER_URL` and `*_MODEL_NAME` together.** An Ollama model
> id (`qwen2.5-coder:14b-instruct-fp16`) is not valid on a vLLM/MaaS endpoint, and
> a vLLM id (`meta-llama/Llama-3.1-8B-Instruct`) is not valid on Ollama.

## Per-agent matrix

| Agent | Entry point | LLM env prefix | Model (local default) | Server style | Purpose of the model |
|-------|-------------|----------------|-----------------------|--------------|----------------------|
| intake | `intake.file-intake` | — | *(none)* | — | Watches a directory, produces to `intake` |
| structure | `structure.message-structure` | `STRUCTURE_*` | `qwen2.5-coder:14b-instruct-fp16` | **Ollama** | Turn raw text into structured JSON |
| guardian | `guardian.message-guardian` | `GUARDIAN_*` | `granite3-guardian:8b-fp16` | **Ollama** | Safety/guardrail check |
| customer | `customer.customer-lookup` | — | *(none)* | — | RDBMS enrichment (northwind) |
| router | `router.message-router` | `ROUTER_*` | `granite3.1-dense:8b-instruct-fp16` | **Ollama** | Classify → support/finance/website |
| support | `support.support-responder` | `SUPPORT_*` | `meta-llama/Llama-3.1-8B-Instruct` | MaaS/vLLM | RAG answer over tech KB |
| website | `website.website-support` | `WEBSITE_*` | `mistral-7b-instruct` | MaaS/vLLM | Tool/function calling (password reset) |
| finance | `finance.finance-responder` | `FINANCE_*` | `qwen2.5-coder:14b-instruct-fp16` | **Ollama** | Tool/function calling (orders/invoices) |
| opportunity | `opportunity.opportunity-finder` | `OPPORTUNITY_*` | `deepseek-r1-distill-qwen-14b` | **Ollama** | **Reasoning** → generates Python it then executes |

The local configuration used six distinct models, including several Ollama-tagged
models that do not exist in the OpenShift environment. The demo consolidates them
onto the shared MaaS `qwen3-235b` model. Guardian and opportunity can still be
overridden later if specialized guardrail or reasoning models become available.

The guardian supports both kinds of model. `GUARDIAN_MODE=auto` selects the
original category-based Yes/No protocol when the model name contains `guardian`
and selects explicit, structured policy prompts for general-purpose models.
`GUARDIAN_MODE=prompted`, used by the OpenShift deployment, makes that choice
explicit for `qwen3-235b`; `GUARDIAN_MODE=specialized` forces the original
protocol. The prompted path evaluates violence, social bias, and profanity
separately and sends indeterminate or failed classifications to `review`.

## Other `localhost` couplings (also break on OpenShift)

Beyond the models, these local dependencies must become in-cluster Services /
managed resources:

| Agent(s) | Dependency | Local value | OpenShift action |
|----------|-----------|-------------|------------------|
| customer | Postgres `northwind` | `localhost:5432` | Managed/in-cluster Postgres Service |
| support | Postgres + **pgvector** `pgvector_rag` | `localhost:5432` | Postgres w/ pgvector Service |
| support | HuggingFace `all-mpnet-base-v2` download at startup | pulls from HF | Bake into image or allow egress |
| website | password-reset tool API | `127.0.0.1:8001` | Deploy `website/api-runner.py` as a Service |
| finance | order/invoice/dispute/receipt tool API | `127.0.0.1:8002` | Deploy `finance/api-runner.py` as a Service |
| opportunity | executes LLM-generated Python via `subprocess` | local shell | Sandbox carefully in-cluster (see below) |
| intake | watches a directory | laptop path | Mounted volume (`WATCH_DIRECTORY=/data/intake`) |

## Bugs found & fixed in this pass

| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `.env.example` | `website-support.py` reads `WEBSITE_API_HOST/PORT` but the file defined `PASSWORD_API_HOST/PORT` → website crashed at startup (`int(None)`) | Renamed to `WEBSITE_API_HOST/PORT` |
| 2 | `website/website-support.py`, `finance/finance-responder.py` | `int(os.getenv("..._API_PORT"))` throws if the var is unset | Added defaults `8001` / `8002` and a host default |
| 3 | `opportunity/opportunity-finder.py` | Generated-code prompt hardcoded `bootstrap_servers='localhost:9092'` | Interpolate `'{KAFKA_BROKER}'` (prompt is already an f-string) |
| 4 | `.env.example` | Generic `INFERENCE_SERVER_URL/MODEL_NAME/API_KEY` looked authoritative but are unused by the pipeline | Added a clarifying comment |

### Known issues left as-is (out of scope, flagged for later)
- `finance/finance-responder.py:179,195` — `SyntaxWarning: invalid escape sequence` (`\g`, `\s`) in log f-strings. Harmless today; should become `\\` or raw strings.
- `opportunity` executes model-generated Python. `subprocess` + `RestrictedPython`
  is safer than `exec`, but running generated code in-cluster deserves a real
  sandbox (network policy, non-root, read-only FS, resource limits) before prod.
- `who-are-you.py:184` hardcodes `http://localhost:11434/v1` — diagnostic script only.

## Wiring it up on OpenShift

All model/service settings are environment variables, so on OpenShift the shared
URL and model belong in a **ConfigMap**, and the shared `API_KEY` belongs in a
**Secret**, mounted into each agent Deployment via `envFrom`. Start from
[`.env.openshift.example`](.env.openshift.example). Per-agent overrides remain
available when needed.

<a name="hosting-options"></a>
## Selected demo strategy

Use the hosted MaaS endpoint with `qwen3-235b` for all agents. This avoids an
in-cluster Ollama or GPU deployment and reduces the required model configuration
to one URL, model name, and API key.

## Alternatives for later

1. **Consolidate + self-host (vLLM via OpenShift AI / KServe).** Collapse the 6
   models toward: one general instruct model (structure/router/support/website/
   finance) + keep a guardrail (granite-guardian) + a reasoning model
   (opportunity). Most "modernized"; needs GPUs. The README itself notes "a single
   model could be used for most of these use cases."
2. **Self-host Ollama in-cluster.** Run an Ollama Deployment serving the existing
   tagged models; keep every `*_MODEL_NAME` unchanged and only swap `*_SERVER_URL`
   to the Ollama Service. Simplest lift-and-shift; still needs GPU/CPU capacity.
3. **Red Hat MaaS (hosted).** Point all agents at hosted endpoints (as the
   `.env.example` header suggests). No in-cluster GPUs; requires updating both
   URL and model id per agent, plus egress and API keys.
4. **Hybrid.** e.g. general agents on MaaS, guardrail/reasoning self-hosted.

Per-agent overrides require only `.env` / ConfigMap / Secret changes.
