#!/usr/bin/env bash
#
# Installs AMQ Streams + a single-node Kafka cluster + topics for ai-message-triage.
# Idempotent: safe to re-run. Requires an oc session logged in as cluster-admin.
#
# Usage:  ./install.sh
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Using cluster: $(oc whoami --show-server)  as  $(oc whoami)"

echo "==> 1/5 Installing AMQ Streams operator (Subscription in openshift-operators)"
oc apply -n openshift-operators -f "${HERE}/01-subscription.yaml"

echo "==> Waiting for the Kafka CRD to be registered by the operator (up to 5 min)..."
for i in $(seq 1 60); do
  if oc get crd kafkas.kafka.strimzi.io >/dev/null 2>&1; then
    echo "    Kafka CRD present."
    break
  fi
  sleep 5
  [ "$i" = "60" ] && { echo "ERROR: Kafka CRD did not appear. Check the operator install (oc get csv -n openshift-operators)."; exit 1; }
done
# Give the operator's webhook/deployment a moment to become ready
oc -n openshift-operators rollout status deploy/amq-streams-cluster-operator-v3.2.1-x 2>/dev/null || \
  oc -n openshift-operators wait --for=condition=Available deploy -l app=strimzi --timeout=180s 2>/dev/null || true

echo "==> 2/5 Creating namespace 'message-triage'"
oc apply -f "${HERE}/02-namespace.yaml"

echo "==> 3/5 Creating KafkaNodePool 'kafka-dual-role'"
oc apply -n message-triage -f "${HERE}/03-kafka-node-pool.yaml"

echo "==> 4/5 Creating Kafka cluster 'message-triage-kafka'"
oc apply -n message-triage -f "${HERE}/04-kafka-cluster.yaml"

echo "==> Waiting for Kafka cluster to become Ready (up to 10 min)..."
oc wait kafka/message-triage-kafka -n message-triage --for=condition=Ready --timeout=600s

echo "==> 5/5 Creating topics"
oc apply -n message-triage -f "${HERE}/05-kafka-topics.yaml"

echo ""
echo "==> Done. Cluster status:"
oc get kafka,kafkanodepool -n message-triage
echo ""
oc get kafkatopic -n message-triage
echo ""
echo "Internal (in-cluster) bootstrap:  message-triage-kafka-kafka-bootstrap.message-triage.svc:9092"
echo -n "External (route/TLS) bootstrap:   "
oc get kafka message-triage-kafka -n message-triage -o jsonpath='{.status.listeners[?(@.name=="external")].bootstrapServers}{"\n"}' 2>/dev/null || echo "(not ready yet)"
