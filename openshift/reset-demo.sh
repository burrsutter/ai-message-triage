#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAMESPACE="message-triage"
TOPICS_MANIFEST="${ROOT_DIR}/openshift/kafka/05-kafka-topics.yaml"
REVIEW_TO_SALES_MANIFEST="${ROOT_DIR}/openshift/backend/05-review-to-sales.yaml"

# Only deployments that read from or write to Kafka need to stop while topics
# are recreated. Scaling HTTP intake to zero also discards its emptyDir and all
# preserved .done files. Tool API deployments contain no demo message state.
BASE_DEPLOYMENTS=(
  message-triage-structure
  message-triage-guardian
  message-triage-customer
  message-triage-router
  message-triage-support
  message-triage-finance
  message-triage-website
  message-triage-http-intake
  message-triage-dashboard
)

existing_deployments=()

echo "==> Verifying the message-triage Kafka cluster"
oc get kafka message-triage-kafka -n "${NAMESPACE}" >/dev/null

for deployment in "${BASE_DEPLOYMENTS[@]}"; do
  if oc get "deployment/${deployment}" -n "${NAMESPACE}" >/dev/null 2>&1; then
    existing_deployments+=("${deployment}")
  fi
done

echo "==> Returning the demo to its initial topology"
oc delete -n "${NAMESPACE}" \
  -f "${REVIEW_TO_SALES_MANIFEST}" \
  --ignore-not-found \
  --wait=true

echo "==> Stopping Kafka-facing demo services"
for deployment in "${existing_deployments[@]}"; do
  oc scale "deployment/${deployment}" --replicas=0 -n "${NAMESPACE}"
done
for deployment in "${existing_deployments[@]}"; do
  oc rollout status "deployment/${deployment}" -n "${NAMESPACE}" --timeout=300s
done

echo "==> Deleting all retained demo topic records"
oc delete -n "${NAMESPACE}" \
  -f "${TOPICS_MANIFEST}" \
  --ignore-not-found \
  --wait=true \
  --timeout=300s

echo "==> Recreating empty Kafka topics"
oc apply -n "${NAMESPACE}" -f "${TOPICS_MANIFEST}"
oc wait -n "${NAMESPACE}" \
  --for=condition=Ready \
  kafkatopic \
  -l strimzi.io/cluster=message-triage-kafka \
  --timeout=300s

echo "==> Restarting the initial demo services"
for deployment in "${existing_deployments[@]}"; do
  oc scale "deployment/${deployment}" --replicas=1 -n "${NAMESPACE}"
done
for deployment in "${existing_deployments[@]}"; do
  oc rollout status "deployment/${deployment}" -n "${NAMESPACE}" --timeout=300s
done

echo "==> Reset complete"
echo "Kafka topics are empty, intake .done files are gone, and review-to-sales is absent."
echo "The updated dashboard clears browser-local cards when it reconnects; refresh or click 'Clear All Messages' if cards remain."
