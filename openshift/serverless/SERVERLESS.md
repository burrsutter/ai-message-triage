# OpenShift Serverless (Knative) on this cluster

Installs **Red Hat OpenShift Serverless** — Knative **Serving** (scale-to-zero,
request-driven containers, revisions, autoscaling) and Knative **Eventing**
(Brokers, Triggers, Sources, Channels) via the OpenShift Serverless operator.

| Thing | Value |
|-------|-------|
| Operator | `serverless-operator` (Red Hat), channel `stable` → **v1.37.1** |
| Knative version | **1.17** |
| Install mode | AllNamespaces only → operator in its own `openshift-serverless` ns |
| Serving ns | `knative-serving` (activator, autoscaler, controller, webhook) |
| Eventing ns | `knative-eventing` (eventing-controller, mt-broker-*, imc-*, job-sink) |

## Manifests (`openshift/serverless/`)

| File | Creates |
|------|---------|
| `01-operator.yaml` | `openshift-serverless` ns + OperatorGroup (AllNamespaces) + Subscription |
| `02-knative-serving.yaml` | `knative-serving` ns + `KnativeServing/knative-serving` |
| `03-knative-eventing.yaml` | `knative-eventing` ns + `KnativeEventing/knative-eventing` |
| `install.sh` / `uninstall.sh` | apply/teardown with readiness waits |

## Install / verify / teardown

```bash
cd openshift/serverless
./install.sh

oc get knativeserving  -n knative-serving      # READY True
oc get knativeeventing -n knative-eventing     # READY True
oc get pods -n knative-serving
oc get pods -n knative-eventing

./uninstall.sh          # remove control planes
./uninstall.sh --all    # also remove the operator
```

## API surface after install

**Serving** (`serving.knative.dev/v1`): `Service` (ksvc), `Revision`, `Route`,
`Configuration`, `DomainMapping`.
**Eventing** (`eventing.knative.dev/v1`): `Broker`, `Trigger`, `EventType`, …

Deploy a serverless app (scales to zero when idle):

```bash
oc new-project demo
oc apply -f - <<'EOF'
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hello
  namespace: demo
spec:
  template:
    spec:
      containers:
        - image: quay.io/openshift-knative/showcase:latest
EOF
oc get ksvc hello -n demo -o jsonpath='{.status.url}{"\n"}'
```

## Kafka integration (not installed — recommended for this app)

The Serverless operator also ships **`KnativeKafka`**
(`operator.serverless.openshift.io/v1alpha1`), which adds:

- **KafkaSource** — read from a Kafka topic and deliver each record as a
  CloudEvent to a sink (a ksvc, a Broker, etc.).
- **KafkaSink** — send CloudEvents from Eventing back out to a Kafka topic.
- **Kafka Broker / Channel** — use the existing AMQ Streams cluster as the
  Eventing transport instead of the in-memory channel (`imc`).

This lines up directly with the triage app's Kafka backbone
(`my-cluster-kafka-bootstrap.kafka.svc:9092`): a `KafkaSource` per input topic
could drive scale-to-zero agents as Knative Services. Ask if you want a
`04-knative-kafka.yaml` wired to the `kafka` namespace's bootstrap.
