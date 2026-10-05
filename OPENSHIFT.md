# Running Kafka for ai-message-triage on OpenShift

This document explains how to stand up the Kafka backbone that `ai-message-triage`
needs, using the **Red Hat AMQ Streams** operator (the productized
[Strimzi](https://strimzi.io/)) on an OpenShift cluster.

It was written against, and validated for the environment of, this cluster:

| Thing | Value |
|-------|-------|
| Cluster API | `https://api.cluster-2qv42.dyn.redhatworkshops.io:6443` |
| OpenShift | 4.22 |
| Apps domain | `apps.cluster-2qv42.dyn.redhatworkshops.io` |
| Default StorageClass | `ocs-external-storagecluster-ceph-rbd` (Ceph RBD block) |
| AMQ Streams (`stable` channel) | **v3.2.1** — KRaft-only, no ZooKeeper, `KafkaNodePool` required |

All the manifests referenced here live in [`openshift/kafka/`](openshift/kafka/).

---

## 1. What this project needs from Kafka

Researched from the codebase (`.env.example`, `reset.sh`, and the `kafka-python`
usage in each agent):

### Kafka client
- Library: **`kafka-python==2.0.6`** (`from kafka import KafkaConsumer, KafkaProducer`).
- Every agent reads a single env var **`KAFKA_BROKER`** and passes it as
  `bootstrap_servers`. Locally this is `localhost:9092`.
- **No authentication or TLS** is configured anywhere in the code — the clients
  speak **PLAINTEXT**. This is the single most important fact for the OpenShift
  design (see [§5](#5-wiring-the-app-to-kafka)).

### Topics
The pipeline uses **12 topics**, each created locally with `--partitions 1
--replication-factor 1` (see `reset.sh`). We reproduce exactly that:

| Topic | Role in the pipeline |
|-------|----------------------|
| `intake` | raw messages dropped in by `intake/file-intake.py` |
| `structured` | after `structure/message-structure.py` |
| `cleared` | after `guardian/message-guardian.py` (safety check) |
| `ready` | after `customer/customer-lookup.py` (customer enrichment) |
| `support` | routed by `router/message-router.py` → `support/` |
| `finance` | routed → `finance/` |
| `website` | routed → `website/` |
| `sales` | opportunities found by `opportunity/opportunity-finder.py` |
| `outflow` | final responses from the responder agents |
| `review` | messages needing human/opportunity attention |
| `input` | legacy/test entry topic |
| `output` | legacy/test exit topic |

Flow:

```
intake → structured → cleared → ready ─┬→ support ─┐
                                       ├→ finance ─┼→ outflow
                                       └→ website ─┘
ready/review → sales        (opportunity finder)
```

### Consumer groups
Two are set explicitly in code — `customer_lookup` (customer-lookup.py) and
`message_router` (message-router.py). The other agents currently run without a
`group_id` (kafka-python assigns a random one each run). No cluster-side setup is
needed for these; they are created on first connect. Worth normalizing later, but
out of scope for standing Kafka up.

---

## 2. Which operator, and why

`oc get packagemanifests | grep -i kafka` on this cluster offers several options
(AMQ Streams, community Strimzi, Cloudera, Stackable, AWS ACK…). We use
**AMQ Streams** because it is the Red Hat–supported build of Strimzi, ships in the
`redhat-operators` catalog already present here, and is the natural fit for a
"modernize onto OpenShift" exercise.

The `stable` channel resolves to **AMQ Streams 3.2.1**. Two consequences drive the
manifests:

1. **KRaft-only.** ZooKeeper has been removed. The cluster runs on the Kafka Raft
   metadata protocol.
2. **`KafkaNodePool` is required.** Broker/controller nodes and their storage are
   declared in a `KafkaNodePool` CR, not directly on the `Kafka` CR. The `Kafka`
   CR carries the annotations `strimzi.io/node-pools: enabled` and
   `strimzi.io/kraft: enabled`.

For this dev/demo we run a **single node playing both roles** (`controller` +
`broker`) with **replication factor 1**, matching the project's local footprint.
This is intentionally *not* production-grade (a real deployment wants ≥3 brokers,
RF=3, `min.insync.replicas=2`).

---

## 3. The manifests

Located in [`openshift/kafka/`](openshift/kafka/), applied in numeric order:

| File | Creates |
|------|---------|
| `01-subscription.yaml` | AMQ Streams operator `Subscription` in `openshift-operators` (uses the existing cluster-wide `global-operators` OperatorGroup → watches all namespaces) |
| `02-namespace.yaml` | `message-triage` namespace |
| `03-kafka-node-pool.yaml` | `KafkaNodePool` `kafka-dual-role`: 1 replica, roles `controller,broker`, 10Gi Ceph RBD PVC |
| `04-kafka-cluster.yaml` | `Kafka` `message-triage-kafka`: KRaft, 3 listeners (plain 9092 / tls 9093 / external route 9094), RF=1 config, Entity/Topic Operator |
| `05-kafka-topics.yaml` | 12 `kafka-*` `KafkaTopic` CRs that retain the application topic names above through `spec.topicName` |
| `install.sh` | applies 01–05 in order with readiness waits (idempotent) |
| `uninstall.sh` | tears the cluster (and optionally the operator) back down |

---

## 4. Install

Log in as a cluster-admin first (the operator install is cluster-scoped):

```bash
oc login --token=<...> --server=https://api.cluster-2qv42.dyn.redhatworkshops.io:6443
oc whoami            # should be a cluster-admin, e.g. admin
```

### Option 1 — one shot

```bash
cd openshift/kafka
./install.sh
```

### Option 2 — step by step (what the script does)

```bash
cd openshift/kafka

# 1. Operator
oc apply -f 01-subscription.yaml
#    wait until the operator has registered the CRDs + is running
oc wait --for=condition=Established crd/kafkas.kafka.strimzi.io --timeout=300s
oc get csv -n openshift-operators | grep amqstreams          # PHASE should be Succeeded

# 2. Namespace
oc apply -f 02-namespace.yaml

# 3. Node pool + 4. Kafka cluster
oc apply -f 03-kafka-node-pool.yaml
oc apply -f 04-kafka-cluster.yaml
oc wait kafka/message-triage-kafka -n message-triage --for=condition=Ready --timeout=600s

# 5. Topics
oc apply -f 05-kafka-topics.yaml
```

### Verify

```bash
oc get kafka,kafkanodepool,pods -n message-triage
oc get kafkatopic -n message-triage        # expect 12 topics, all Ready
```

You should see the `message-triage-kafka-kafka-dual-role-0` pod plus the entity-operator pod
running, and the internal bootstrap service:

```
message-triage-kafka-kafka-bootstrap.message-triage.svc:9092
```

---

## 5. Wiring the app to Kafka

The code speaks PLAINTEXT with no auth, so **where you run the agents decides which
listener you use.**

### Option A — run the agents *inside* OpenShift (recommended, zero code changes)

Use the internal PLAINTEXT bootstrap. In each agent's environment / `.env`:

```dotenv
KAFKA_BROKER=message-triage-kafka-kafka-bootstrap.message-triage.svc:9092
```

(If the agent Deployments live in the `message-triage` namespace, `message-triage-kafka-kafka-bootstrap:9092`
is enough; use the fully-qualified `.message-triage.svc` form when they run in another
namespace.) All topic env vars in `.env` stay exactly as they are — the topic
*names* are identical to the local setup. This is the clean modernization path and
needs no change to the Python.

### Option B — run the agents on your laptop against the cluster (needs a code change)

The nodes on this cluster have no external IP, so a NodePort listener is not
reachable. External access therefore goes through the **route** listener, and
OpenShift routes are **always TLS**. `kafka-python` will not connect to it as-is.

1. Get the external bootstrap host (port 443):

   ```bash
   oc get kafka message-triage-kafka -n message-triage \
     -o jsonpath='{.status.listeners[?(@.name=="external")].bootstrapServers}{"\n"}'
   # e.g. message-triage-kafka-kafka-bootstrap-message-triage.apps.cluster-2qv42.dyn.redhatworkshops.io:443
   ```

2. Extract the cluster CA certificate:

   ```bash
   oc get secret message-triage-kafka-cluster-ca-cert -n message-triage \
     -o jsonpath='{.data.ca\.crt}' | base64 -d > ca.crt
   ```

3. Point `.env` at it:

   ```dotenv
   KAFKA_BROKER=message-triage-kafka-kafka-bootstrap-message-triage.apps.cluster-2qv42.dyn.redhatworkshops.io:443
   ```

4. Add TLS to the `KafkaConsumer` / `KafkaProducer` calls. Every agent builds them
   the same way, so the cleanest change is to centralize the kwargs, e.g.:

   ```python
   import os
   kafka_kwargs = dict(bootstrap_servers=KAFKA_BROKER)
   if os.getenv("KAFKA_TLS", "false").lower() == "true":
       kafka_kwargs.update(
           security_protocol="SSL",
           ssl_cafile=os.getenv("KAFKA_CA_CERT", "ca.crt"),
       )
   producer = KafkaProducer(**kafka_kwargs)
   consumer = KafkaConsumer(topic, **kafka_kwargs)
   ```

   then set `KAFKA_TLS=true` and `KAFKA_CA_CERT=./ca.crt`. Option A avoids all of
   this, which is why it's preferred.

---

## 6. Smoke test

Produce/consume without touching the app, using the broker pod's built-in tools:

```bash
# consume (leave running in one terminal)
oc -n message-triage exec -it message-triage-kafka-kafka-dual-role-0 -- \
  bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 \
  --topic intake --from-beginning

# produce (another terminal)
oc -n message-triage exec -it message-triage-kafka-kafka-dual-role-0 -- \
  bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic intake
> {"hello":"world"}
```

List topics:

```bash
oc -n message-triage exec -it message-triage-kafka-kafka-dual-role-0 -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

`reset.sh` / `kcat-clear.sh` from the repo work too once `KAFKA_BROKER` points at
the cluster and (for Option B) TLS is configured; against the in-cluster broker,
prefer `oc exec` as above or re-apply/patch the `KafkaTopic` CRs.

---

## 7. Event-driven backend agents

Run the complete deployment from the repository root:

```bash
./openshift/deploy.sh
```

The script leaves an existing Kafka cluster intact, builds the current local
source, and creates the initial set of independently deployable backend services.
The final row is intentionally added later:

| Deployment | Kafka input | Kafka output |
|---|---|---|
| `message-triage-structure` | `intake` | `structured` |
| `message-triage-guardian` | `structured` | `cleared` or `review` |
| `message-triage-customer` | `cleared` | `ready` or `review` |
| `message-triage-router` | `ready` | `support`, `finance`, `website`, or `review` |
| `message-triage-support` | `support` | `outflow` or `review` |
| `message-triage-finance` | `finance` | `outflow` or `review` |
| `message-triage-website` | `website` | `outflow` or `review` |
| `message-triage-review-to-sales` | `review` | `sales` (added later) |

Every agent has a unique consumer group, its own ConfigMap containing only its
topic contract, and one replica. They share the Kafka bootstrap address and the
single MaaS configuration (`qwen3-235b`) through the common ConfigMap and API-key
Secret. `message-triage-finance-api` and `message-triage-website-api` are separate
internal HTTP tool pods invoked by their corresponding agents.

The OpenShift demo deliberately sets `CUSTOMER_LOOKUP_MODE=passthrough` and
`SUPPORT_RAG_ENABLED=false`; localhost keeps the original database-backed modes.
It sets `GUARDIAN_MODE=prompted`, which gives the shared `qwen3-235b` model
explicit structured policies for violence, social bias, and profanity. A local
guardian-specific model continues to use its original category protocol through
the default `GUARDIAN_MODE=auto`. The demo also disables execution of
LLM-generated opportunity code. These choices make the demo self-contained
without silently changing local behavior.

The initial install deliberately does **not** create the review-to-sales pod.
Messages that the main flow cannot handle accumulate on `review`, making the
exception visible on the dashboard. Later in the demo, dynamically add the new
agent:

```bash
./openshift/backend/deploy-review-to-sales.sh
oc logs -n message-triage -f deployment/message-triage-review-to-sales
```

The agent joins with its own consumer group, reads the existing `review` events,
asks the shared MaaS model whether each is a sales opportunity, and publishes
matching messages to `sales`. It does not execute LLM-generated code. Remove it
to repeat that part of the story:

```bash
./openshift/backend/uninstall-review-to-sales.sh
```

---

## 8. HTTP intake

The original `python -m intake.file-intake` directory watcher remains the local
demo path. For OpenShift, `openshift/intake/` deploys a small HTTP service that
uses the exact same file processor and Kafka message envelope.

```bash
chmod +x openshift/intake/deploy.sh openshift/intake/uninstall.sh
./openshift/intake/deploy.sh
```

The script builds from the current local source, deploys into `message-triage`,
and prints the TLS Route. Every namespaced `oc` operation in the script includes
`-n message-triage`; it never changes your current project. Submit plain UTF-8
text with a filename:

```bash
INTAKE_URL="https://$(oc get route message-triage-http-intake \
  -n message-triage -o jsonpath='{.spec.host}')"

curl -fsS -X POST "${INTAKE_URL}/intake?filename=demo-message.txt" \
  -H 'Content-Type: text/plain' \
  --data-binary 'I was charged twice for order 1234.'
```

The endpoint also accepts JSON shaped as `{"filename":"...","content":"..."}`
and multipart uploads with a `file` field. On successful Kafka publication, the
source is moved to `/data/intake/done/<filename>.done`. That directory is backed
by an `emptyDir`: it survives for the life of the current pod, but deliberately
resets whenever the pod is deleted or replaced. The Deployment stays at one
replica so all `.done` artifacts are visible in one pod.

For the included demo messages, stay in the repository root and use `send.sh`:

```bash
./send.sh --list
./send.sh finance/missing-invoice.txt
```

The parameter is the path beneath `data/sample/`. The script discovers the
Route with an explicitly scoped `oc get ... -n message-triage` command and then
uses `curl` to upload the selected file. A sample cannot be sent twice during
the same pod lifetime because its `.done` file is preserved; reset the pod as
shown below before repeating that filename.

Inspect the preserved files:

```bash
oc exec -n message-triage deployment/message-triage-http-intake -- \
  find /data/intake/done -maxdepth 1 -type f -print
```

Reset only HTTP intake files (Kafka messages are unaffected) by replacing its pod:

```bash
oc delete pod -n message-triage \
  -l app.kubernetes.io/name=message-triage-http-intake
```

Reset the entire demo to its initial state while keeping the cluster and
application installed:

```bash
./openshift/reset-demo.sh
```

This recreates all twelve Kafka topics, clears the intake pod's ephemeral files,
removes the optional review-to-sales Deployment, and restarts the initial
Kafka-facing services. Refresh the dashboard browser afterward to clear its
browser-local message display.

Remove the HTTP intake resources with `./openshift/intake/uninstall.sh`.

---

## 9. Teardown

```bash
cd openshift/kafka
./uninstall.sh          # removes topics, Kafka cluster, node pool, namespace (+PVC)
./uninstall.sh --all    # also removes the AMQ Streams operator
```

---

## 10. Design decisions & caveats

- **Single-node, RF=1** mirrors the project's local dev setup. Not HA. For
  production use ≥3 broker nodes, `default.replication.factor: 3`,
  `min.insync.replicas: 2`, and separate controller/broker node pools.
- **Persistent storage (10Gi Ceph RBD)** with `deleteClaim: true`. Switch the node
  pool volume to `type: ephemeral` if you want a throwaway cluster whose data is
  gone on pod restart.
- **Kafka version is not pinned** in the `Kafka` CR — the operator applies its
  default for AMQ Streams 3.2.1. Pin `spec.kafka.version` / `metadataVersion` if
  you need reproducibility across operator upgrades.
- **Topic names are unchanged** from local, so no `.env` topic edits are needed —
  only `KAFKA_BROKER`.
- The operator is installed cluster-wide (AllNamespaces) via the pre-existing
  `global-operators` OperatorGroup. If you'd rather scope it to just `kafka`,
  install namespaced with its own OperatorGroup instead.
