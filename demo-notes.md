# AI Message Triage OpenShift Demo Notes

> **Presentation TODO:** Remake [this slide](https://docs.google.com/presentation/d/17zENrpUrlTxNr5vtdki8NuR-nx2lkzMlCMk42AXgklI/edit?slide=id.g304b894139c_3_0#slide=id.g304b894139c_3_0) for the OpenShift version of the demo.

## Prerequisites

- Log in to the OpenShift cluster with `oc`.
- Use an account that can install AMQ Streams and create workloads in
  `message-triage`.
- Run all commands from the repository root:

```bash
cd /Users/burrsuter/ai-projects/modernize/ai-message-triage
```

Confirm the cluster connection without changing your active project:

```bash
oc whoami
oc whoami --show-server
oc get serviceaccount default -n message-triage
```

## Configure the MaaS API key

[Request a MaaS virtual key from the Red Hat Demo Platform](https://catalog.demo.redhat.com/catalog/babylon-catalog-dev?item=babylon-catalog-dev/openshift-cnv.litemaas-virt-key-usage-example-cnv.dev&utm_source=webapp&utm_medium=share-link).

The agents share this MaaS configuration:

```text
URL:   https://maas-rhdp.apps.maas.redhatworkshops.io/v1
Model: qwen3-235b
```

Store the API key in OpenShift without putting it in shell history or a file:

```bash
read -s MESSAGE_TRIAGE_MAAS_KEY
echo
oc create secret generic message-triage-model-credentials \
  -n message-triage \
  --from-literal="API_KEY=${MESSAGE_TRIAGE_MAAS_KEY}" \
  --dry-run=client -o yaml \
  | oc apply -n message-triage -f -
unset MESSAGE_TRIAGE_MAAS_KEY
```

The current key exposes one model: `qwen3-235b`.

## Install or update the complete demo

Make the scripts executable if this is a fresh checkout:

```bash
chmod +x openshift/deploy.sh
chmod +x openshift/reset-demo.sh
chmod +x openshift/e2e-test.sh
chmod +x openshift/kafka/install.sh
chmod +x openshift/backend/deploy.sh
chmod +x openshift/backend/uninstall.sh
chmod +x openshift/backend/deploy-review-to-sales.sh
chmod +x openshift/backend/uninstall-review-to-sales.sh
chmod +x openshift/intake/deploy.sh
chmod +x openshift/intake/uninstall.sh
chmod +x openshift/deploy-dashboard.sh
chmod +x openshift/uninstall-dashboard.sh
chmod +x send.sh
```

Deploy Kafka, the independent backend agents, tool APIs, HTTP intake, and the
dashboard:

```bash
./openshift/deploy.sh
```

The script leaves an existing `message-triage-kafka` cluster in place. All
namespaced `oc` operations explicitly use `-n message-triage`; the script does
not change your active OpenShift project.

## Verify the installation

```bash
oc get kafka,kafkanodepool,kafkatopic -n message-triage
oc get deployments,pods,services,routes -n message-triage
```

The main application should have one pod for each independent agent:

```text
message-triage-structure       intake     -> structured
message-triage-guardian        structured -> cleared or review
message-triage-customer        cleared    -> ready or review
message-triage-router          ready      -> support, finance, website, or review
message-triage-support         support    -> outflow or review
message-triage-finance         finance    -> outflow or review
message-triage-website         website    -> outflow or review
```

The finance and website tool APIs run in their own pods:

```text
message-triage-finance-api
message-triage-website-api
```

At this point, exceptions remain visibly parked on the `review` topic. The
review-to-sales exception handler is intentionally not part of the initial
installation.

## Open the dashboard

Print the dashboard URL:

```bash
echo "https://$(oc get route message-triage-dashboard \
  -n message-triage -o jsonpath='{.spec.host}')"
```

On macOS, open it directly:

```bash
open "https://$(oc get route message-triage-dashboard \
  -n message-triage -o jsonpath='{.spec.host}')"
```

## Send sample messages

List all included samples:

```bash
./send.sh --list
```

Enable sample-name tab completion in the current iTerm2/zsh tab:

```bash
autoload -Uz compinit && compinit
source ./completions/send.zsh
```

Now type a partial sample name and press Tab:

```bash
./send.sh hr/job-
```

It completes to `hr/job-applicant-1.txt`. To enable this in every new iTerm2
tab, add the following line to `~/.zshrc`, then open a new tab:

```bash
source /Users/burrsuter/ai-projects/modernize/ai-message-triage/completions/send.zsh
```

Send a finance message:

```bash
./send.sh finance/duplicate-charge-1.txt
```

Other examples:

```bash
./send.sh finance/missing-invoice.txt
./send.sh support/technical-support-1.txt
./send.sh website/help-password-1.txt
./send.sh bad/bad-message-1.txt
```

An accepted message is published to Kafka and preserved inside the intake pod
as `/data/intake/done/<filename>.done`. Reusing that filename returns HTTP 409
until the intake pod is reset.

## Run the complete end-to-end test

Run every included sample through the OpenShift pipeline, validate the Kafka
topics visited by each filename, test the late review-to-sales agent, and save a
timestamped report:

```bash
./openshift/e2e-test.sh
```

The test resets the demo before it starts and always runs
`./openshift/reset-demo.sh` again before it exits, including after failures or
interruptions. The final reset clears Kafka records and intake `.done` files and
removes review-to-sales, leaving the initial demo topology ready. The dashboard
clears its browser-local cards when it reconnects to the restarted dashboard
pod; refresh it or click **Clear All Messages** if it was manually disconnected.

Results are written under `test-results/e2e-<UTC timestamp>/`. Open
`summary.md` for the pass/fail table; `results.json`, `results.tsv`, raw topic
captures, service logs, submissions, and reset logs are preserved alongside it.
Duplicates are counted but do not fail this demo-oriented test.

The full run makes many MaaS calls and can take several minutes. The default
timeout for each processing phase is 40 minutes; override it when needed:

```bash
E2E_TIMEOUT_SECONDS=3600 ./openshift/e2e-test.sh
```

## Add review-to-sales later

Before adding the exception handler, send a sales prospect and show it stopping
on the dashboard's `review` topic:

```bash
./send.sh sales/prospect-bulk-order-1.txt
```

Then dynamically add the new agent:

```bash
./openshift/backend/deploy-review-to-sales.sh
```

Watch it consume existing exceptions and route sales opportunities:

```bash
oc logs -n message-triage -f deployment/message-triage-review-to-sales
```

The new flow is:

```text
message-triage-review-to-sales     review -> sales
```

It has its own consumer group and uses an LLM classification decision. The
OpenShift mode does not execute generated Python code. To repeat this part of
the demonstration, remove only the late-added agent:

```bash
./openshift/backend/uninstall-review-to-sales.sh
```

## Stream service logs

Stream all event-driven agents together:

```bash
oc logs -n message-triage \
  -f \
  -l app.kubernetes.io/component=agent \
  --all-containers=true \
  --prefix=true \
  --max-log-requests=8
```

Stream individual services in the dashboard's left-to-right, top-to-bottom
topic order. A comment names the dashboard card associated with each command:

```bash
# intake (hide OpenShift readiness and liveness probe requests)
oc logs -n message-triage \
  -f deployment/message-triage-http-intake | \
  grep -vE 'GET /(readyz|healthz)'

# structured
oc logs -n message-triage -f deployment/message-triage-structure

# cleared
oc logs -n message-triage -f deployment/message-triage-guardian

# ready
oc logs -n message-triage -f deployment/message-triage-customer

# support, finance, website, or review routing
oc logs -n message-triage -f deployment/message-triage-router

# support -> outflow or review
oc logs -n message-triage -f deployment/message-triage-support

# finance -> outflow or review
oc logs -n message-triage -f deployment/message-triage-finance
oc logs -n message-triage -f deployment/message-triage-finance-api

# website -> outflow or review
oc logs -n message-triage -f deployment/message-triage-website
oc logs -n message-triage -f deployment/message-triage-website-api

# outflow has no separate pod; support, finance, and website publish to it

# review topic records
oc exec -n message-triage -it \
  message-triage-kafka-kafka-dual-role-0 -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server message-triage-kafka-kafka-bootstrap:9092 \
  --topic review \
  --property print.timestamp=true

# review -> sales agent (available after the late-demo deployment)
oc logs -n message-triage -f deployment/message-triage-review-to-sales

# sales topic records
oc exec -n message-triage -it \
  message-triage-kafka-kafka-dual-role-0 -- \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server message-triage-kafka-kafka-bootstrap:9092 \
  --topic sales \
  --property print.timestamp=true
```

The intake filter removes repetitive `/readyz` and `/healthz` access entries
while preserving `POST /intake`, Kafka publication, and application errors.

Run the `review` and `sales` topic consumers in separate terminals before
sending the sample message. Add `--from-beginning` to either consumer to replay
records already stored in that topic. Kafka broker `oc logs` output contains
broker operations, not the topic record payloads.

To demonstrate the guardian with the shared `qwen3-235b` model, stream its logs
and send the policy samples from separate terminals:

```bash
oc logs -n message-triage -f deployment/message-triage-guardian

./send.sh bad/bad-message-1.txt  # social bias
./send.sh bad/bad-message-2.txt  # profanity
./send.sh bad/bad-message-3.txt  # violence/threat
./send.sh bad/bad-message-4.txt  # social bias only
./send.sh bad/bad-message-5.txt  # violence and profanity
```

Each unsafe sample should follow `intake -> structured -> review`, without
appearing in `cleared`. Guardian log entries include the category, structured
unsafe decision, and short reason.

Stream the dashboard itself:

```bash
oc logs -n message-triage -f deployment/message-triage-dashboard
```

Stream Kafka:

```bash
oc logs -n message-triage -f message-triage-kafka-kafka-dual-role-0
```

## Reset the complete OpenShift demo

Return the cluster demo to a clean initial state:

```bash
./openshift/reset-demo.sh
```

This deletes and recreates the twelve demo Kafka topics, clears the HTTP intake
pod's ephemeral `.done` files, removes the late-added review-to-sales Deployment,
and restarts the initial Kafka-facing services. It leaves Kafka itself, builds,
images, Routes, tool APIs, model configuration, and credentials installed.

The messages displayed by the dashboard are browser-local. The updated
dashboard clears them when it reconnects to the restarted dashboard pod. If it
was manually disconnected, refresh it or click **Clear All Messages**.

## Reset only the ephemeral HTTP intake files

Replacing the intake pod clears its pod-local `emptyDir`, including all `.done`
files. Kafka messages are unaffected:

```bash
oc delete pod -n message-triage \
  -l app.kubernetes.io/name=message-triage-http-intake
```

Wait for the replacement pod:

```bash
oc rollout status deployment/message-triage-http-intake \
  -n message-triage --timeout=300s
```

## Redeploy only one layer

```bash
./openshift/backend/deploy.sh
./openshift/intake/deploy.sh
./openshift/deploy-dashboard.sh
```

## Remove application layers

These commands leave Kafka installed:

```bash
./openshift/backend/uninstall.sh
./openshift/intake/uninstall.sh
./openshift/uninstall-dashboard.sh
```

Kafka teardown is documented separately in `OPENSHIFT.md` because it also
removes the namespace and persistent Kafka data.
